from app.config import settings
from app.models import PushSubscription
from tests.conftest import auth_headers


def _sub_body(endpoint="https://push.example/abc", p="p_key", a="a_key"):
    return {"endpoint": endpoint, "keys": {"p256dh": p, "auth": a}}


def test_public_key_reports_config(client, monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", "PUBKEY123")
    assert client.get("/push/public-key").json()["key"] == "PUBKEY123"


def test_public_key_empty_when_unset(client):
    assert client.get("/push/public-key").json()["key"] == ""  # 默认空 = 前端隐藏开关


def test_subscribe_stores_row(client):
    h = auth_headers(client, "alice")
    r = client.post("/push/subscribe", headers=h, json=_sub_body())
    assert r.status_code == 204
    with client.session_factory() as s:
        rows = s.query(PushSubscription).all()
        assert len(rows) == 1
        assert rows[0].endpoint == "https://push.example/abc"


def test_subscribe_same_endpoint_upserts(client):
    h = auth_headers(client, "alice")
    client.post("/push/subscribe", headers=h, json=_sub_body())
    client.post("/push/subscribe", headers=h, json=_sub_body(p="p2", a="a2"))  # 同 endpoint
    with client.session_factory() as s:
        rows = s.query(PushSubscription).all()
        assert len(rows) == 1  # 不新增
        assert rows[0].p256dh == "p2"  # 密钥被更新


def test_unsubscribe_removes(client):
    h = auth_headers(client, "alice")
    client.post("/push/subscribe", headers=h, json=_sub_body())
    r = client.request(
        "DELETE", "/push/subscribe", headers=h, json={"endpoint": "https://push.example/abc"}
    )
    assert r.status_code == 204
    with client.session_factory() as s:
        assert s.query(PushSubscription).count() == 0


def test_subscribe_requires_auth(client):
    assert client.post("/push/subscribe", json=_sub_body()).status_code == 401
