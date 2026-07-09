"""分身梦话定时 job：直接调 run_morning_dreams()，用可变 dict 推进「今天」。
参照 test_push_scheduler.py 的写法。"""

from datetime import date

import app.live_scheduler as live
from app.models import Event
from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    client.put("/avatars/mine", headers=ha, json={"name": "小恶魔", "persona": {"tone": "毒舌"}})
    client.put("/avatars/mine", headers=hb, json={"name": "狗蛋", "persona": {"tone": "憨憨"}})
    return ha, hb


def _dreams(client):
    db = client.session_factory()
    try:
        return db.query(Event).filter(Event.action_type == "dream").order_by(Event.id).all()
    finally:
        db.close()


def test_each_avatar_gets_its_own_dream(client, monkeypatch):
    _pair(client)
    monkeypatch.setattr(live, "_today", lambda: date(2026, 7, 9))
    live.run_morning_dreams()

    rows = _dreams(client)
    assert len(rows) == 2  # 两只镜像分身各做各的梦
    assert {r.kind for r in rows} == {"ai_reaction"}
    assert all(r.content for r in rows)
    # actor=subject（同 nudge）：梦话落在分身代表的那个人那一侧
    assert {r.actor_user_id for r in rows} == {1, 2}


def test_client_key_carries_the_avatar_id_so_both_avatars_fit(client, monkeypatch):
    """唯一约束是 (couple_id, client_key, kind)——两只分身同一天必须用不同的 key。"""
    _pair(client)
    monkeypatch.setattr(live, "_today", lambda: date(2026, 7, 9))
    live.run_morning_dreams()

    keys = {r.client_key for r in _dreams(client)}
    assert len(keys) == 2
    assert keys == {live.dream_client_key(1, date(2026, 7, 9)), live.dream_client_key(2, date(2026, 7, 9))}


def test_running_twice_the_same_day_does_not_duplicate(client, monkeypatch):
    _pair(client)
    monkeypatch.setattr(live, "_today", lambda: date(2026, 7, 9))
    live.run_morning_dreams()
    live.run_morning_dreams()
    assert len(_dreams(client)) == 2  # 幂等靠唯一约束兜住


def test_a_new_day_brings_new_dreams(client, monkeypatch):
    _pair(client)
    day = {"d": date(2026, 7, 9)}
    monkeypatch.setattr(live, "_today", lambda: day["d"])
    live.run_morning_dreams()
    day["d"] = date(2026, 7, 10)
    live.run_morning_dreams()
    assert len(_dreams(client)) == 4


def test_uncaptured_avatars_do_not_dream(client, monkeypatch):
    """只 alice 捏了分身；bob 还没捏 → 只该有一条梦话。"""
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    client.put("/avatars/mine", headers=ha, json={"name": "小恶魔"})

    monkeypatch.setattr(live, "_today", lambda: date(2026, 7, 9))
    live.run_morning_dreams()
    assert len(_dreams(client)) == 1


def test_pushes_the_keeper_not_the_subject(client, monkeypatch):
    """梦话是说给养它的人听的。"""
    _pair(client)
    monkeypatch.setattr(live, "_today", lambda: date(2026, 7, 9))
    sent = []
    monkeypatch.setattr(live.push_service, "send_to_user", lambda uid, p: sent.append((uid, p["tag"])))
    live.run_morning_dreams()

    rows = {r.actor_user_id: r for r in _dreams(client)}
    # alice(1) 的分身被 bob(2) 养着 → 推给 bob
    assert (2, "dream") in sent and (1, "dream") in sent
    assert rows[1].actor_user_id == 1  # subject=alice
    assert len(sent) == 2


def test_second_run_pushes_nothing(client, monkeypatch):
    _pair(client)
    monkeypatch.setattr(live, "_today", lambda: date(2026, 7, 9))
    live.run_morning_dreams()
    sent = []
    monkeypatch.setattr(live.push_service, "send_to_user", lambda uid, p: sent.append(uid))
    live.run_morning_dreams()
    assert sent == []  # 没新落梦话就不打扰


def test_never_raises_when_the_ai_layer_explodes(client, monkeypatch):
    _pair(client)
    monkeypatch.setattr(live, "_today", lambda: date(2026, 7, 9))
    monkeypatch.setattr(live, "generate_dream", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    live.run_morning_dreams()  # 不该抛
    assert _dreams(client) == []


def test_pet_endpoint_surfaces_todays_dream(client, monkeypatch):
    ha, hb = _pair(client)
    import app.routers.avatars as avatars_router

    monkeypatch.setattr(live, "_today", lambda: date(2026, 7, 9))
    monkeypatch.setattr(avatars_router, "_today", lambda: date(2026, 7, 9))

    assert client.get("/avatars/pet", headers=hb).json()["dream"] is None
    live.run_morning_dreams()
    dream = client.get("/avatars/pet", headers=hb).json()["dream"]
    assert dream is not None and dream["content"]
    assert dream["at"].endswith("Z")


def test_yesterdays_dream_does_not_leak_into_today(client, monkeypatch):
    ha, hb = _pair(client)
    import app.routers.avatars as avatars_router

    monkeypatch.setattr(live, "_today", lambda: date(2026, 7, 9))
    live.run_morning_dreams()
    monkeypatch.setattr(avatars_router, "_today", lambda: date(2026, 7, 10))
    assert client.get("/avatars/pet", headers=hb).json()["dream"] is None
