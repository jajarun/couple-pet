import app.push_service as ps
from app.config import settings
from app.models import PushSubscription
from pywebpush import WebPushException


def _make_sub(session_factory, user_id, endpoint):
    with session_factory() as s:
        s.add(PushSubscription(user_id=user_id, endpoint=endpoint, p256dh="p", auth="a"))
        s.commit()


def test_no_key_is_noop(client, monkeypatch):
    monkeypatch.setattr(settings, "vapid_private_key", "")  # 无私钥 = 关闭推送
    calls = []
    monkeypatch.setattr(ps, "webpush", lambda **k: calls.append(k))
    _make_sub(client.session_factory, 1, "https://e/1")
    ps.send_to_user(1, {"title": "x"})
    assert calls == []  # 根本不发


def test_sends_only_to_target_user(client, monkeypatch):
    monkeypatch.setattr(settings, "vapid_private_key", "PRIV")
    sent = []
    monkeypatch.setattr(ps, "webpush", lambda **k: sent.append(k["subscription_info"]["endpoint"]))
    _make_sub(client.session_factory, 1, "https://e/u1")
    _make_sub(client.session_factory, 2, "https://e/u2")
    ps.send_to_user(1, {"title": "hi"})
    assert sent == ["https://e/u1"]  # 只发给 user 1，不碰 user 2


def test_sends_to_all_devices_of_user(client, monkeypatch):
    monkeypatch.setattr(settings, "vapid_private_key", "PRIV")
    sent = []
    monkeypatch.setattr(ps, "webpush", lambda **k: sent.append(k["subscription_info"]["endpoint"]))
    _make_sub(client.session_factory, 1, "https://e/dev1")
    _make_sub(client.session_factory, 1, "https://e/dev2")
    ps.send_to_user(1, {"title": "hi"})
    assert set(sent) == {"https://e/dev1", "https://e/dev2"}  # 多设备都发


def test_prunes_gone_subscription(client, monkeypatch):
    monkeypatch.setattr(settings, "vapid_private_key", "PRIV")

    class _Resp:
        status_code = 410

    def boom(**k):
        raise WebPushException("gone", response=_Resp())

    monkeypatch.setattr(ps, "webpush", boom)
    _make_sub(client.session_factory, 1, "https://e/dead")
    ps.send_to_user(1, {"title": "hi"})
    with client.session_factory() as s:
        assert s.query(PushSubscription).count() == 0  # 410 → 删掉失效订阅


def test_other_error_keeps_subscription_and_never_raises(client, monkeypatch):
    monkeypatch.setattr(settings, "vapid_private_key", "PRIV")

    def boom(**k):
        raise RuntimeError("network down")

    monkeypatch.setattr(ps, "webpush", boom)
    _make_sub(client.session_factory, 1, "https://e/keep")
    ps.send_to_user(1, {"title": "hi"})  # 不抛
    with client.session_factory() as s:
        assert s.query(PushSubscription).count() == 1  # 非 410 → 保留订阅
