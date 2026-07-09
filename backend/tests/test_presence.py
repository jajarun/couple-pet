"""在线心跳 + 同框 ×2 + 摸摸头。

心跳只由 POST /presence 写——这条不变式是整套设计的地基（GET /events 和 POST /actions
都只读），所以下面专门有一个用例钉死它。
"""

from datetime import datetime, timedelta

import app.routers.presence as presence_router
from app.models import User
from app.rules.actions import LOCAL_REACTIONS
from app.time_utils import utcnow
from tests.conftest import auth_headers, enable_ai_reply

T0 = datetime(2026, 7, 9, 12, 0, 0)


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    return ha, hb


def _ping(client, headers):
    return client.post("/presence", headers=headers).json()["partner_online"]


def _act(client, headers, action_type, key):
    return client.post(
        "/actions",
        headers=headers,
        json={"action_type": action_type, "content": "", "client_key": key},
    )


def _freeze(monkeypatch, when):
    """冻结 /presence 的时钟。心跳的写和读都走它，所以 TTL 判定完全确定。"""
    monkeypatch.setattr(presence_router, "_now", lambda: when)


def _walk_away(client, nickname):
    """把某人的心跳改旧，模拟 TA 切后台/关页面（/actions 读的是真实时钟）。"""
    with client.session_factory() as s:
        u = s.query(User).filter(User.nickname == nickname).one()
        u.last_seen_at = utcnow() - timedelta(hours=1)
        s.commit()


def test_heartbeat_records_last_seen_and_reports_partner_offline(client):
    ha, _hb = _pair(client)
    assert _ping(client, ha) is False  # bob 从没打过心跳
    with client.session_factory() as s:
        assert s.query(User).filter(User.nickname == "alice").one().last_seen_at is not None


def test_partner_is_online_once_they_beat(client):
    ha, hb = _pair(client)
    _ping(client, hb)
    assert _ping(client, ha) is True
    assert _ping(client, hb) is True  # 双向


def test_partner_goes_dark_after_the_ttl(client, monkeypatch):
    ha, hb = _pair(client)
    _freeze(monkeypatch, T0)
    _ping(client, hb)  # bob 在 12:00 打了一次心跳，然后切后台

    _freeze(monkeypatch, T0 + timedelta(seconds=20))
    assert _ping(client, ha) is True

    _freeze(monkeypatch, T0 + timedelta(seconds=30))  # 超过 presence_ttl_seconds=25
    assert _ping(client, ha) is False


def test_only_the_presence_endpoint_writes_the_heartbeat(client):
    """钉死不变式：发动作 / 拉时间线都不算「在线」。

    否则 tests/test_feed.py 里「alice 先 GET /events、bob 随后发动作」会让 bob 的数值被 ×2。
    """
    ha, hb = _pair(client)
    _act(client, ha, "poke", "k1")
    client.get("/events", headers=ha)
    assert _ping(client, hb) is False


def test_actions_double_when_both_are_watching(client):
    ha, hb = _pair(client)
    _ping(client, ha)  # alice 在线
    assert _act(client, hb, "scold", "k1").json()["stats"]["grievance"] == 30  # +15 → +30


def test_actions_stay_single_when_alone(client):
    _ha, hb = _pair(client)
    assert _act(client, hb, "scold", "k1").json()["stats"]["grievance"] == 15


def test_bundle_carries_the_together_flag(client):
    ha, hb = _pair(client)
    assert _act(client, hb, "poke", "k1").json()["together"] is False
    _ping(client, ha)
    assert _act(client, hb, "poke", "k2").json()["together"] is True


def test_being_together_does_not_double_the_care_that_drives_evolution(client):
    """数值翻倍，经验不翻倍——care 数的是「做了几次」，翻倍会把分支占比算歪。"""
    ha, hb = _pair(client)
    _ping(client, ha)
    body = _act(client, hb, "poke", "k1").json()
    assert body["together"] is True
    assert body["evolution"]["exp"] == 1  # poke 权重 1，不是 2


def test_headpat_needs_both_of_you_here(client):
    _ha, hb = _pair(client)
    r = _act(client, hb, "headpat", "k1")
    assert r.status_code == 409
    assert r.json()["detail"] == "not_together"


def test_headpat_lands_and_doubles_while_together(client):
    ha, hb = _pair(client)
    enable_ai_reply(client, hb)
    _ping(client, ha)
    body = _act(client, hb, "headpat", "k1").json()
    assert body["stats"]["intimacy"] == 6  # +3 → +6
    reaction = next(e for e in body["events"] if e["kind"] == "ai_reaction")
    assert reaction["content"] in LOCAL_REACTIONS["headpat"]


def test_a_headpat_replay_survives_the_partner_leaving(client):
    """同框时发出的那一下，重放时不该因为 TA 刚下线就被 409 打回。"""
    ha, hb = _pair(client)
    _ping(client, ha)
    first = _act(client, hb, "headpat", "same-key")
    assert first.status_code == 200

    _walk_away(client, "alice")
    second = _act(client, hb, "headpat", "same-key")
    assert second.status_code == 200
    assert [e["id"] for e in second.json()["events"]] == [e["id"] for e in first.json()["events"]]
    assert second.json()["stats"]["intimacy"] == first.json()["stats"]["intimacy"]  # 没重复加
    assert second.json()["together"] is False  # 但 together 反映的是「此刻」


def test_no_couple_yet_never_reports_anyone_online(client):
    ha = auth_headers(client, "solo")
    assert _ping(client, ha) is False
