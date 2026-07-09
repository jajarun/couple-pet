"""离家出走：判据纯看饲养者自己的行为，状态纯从事件流派生（零新字段）。"""

import app.live_scheduler as live
from app.models import Event
from app.rules.actions import LOCAL_REACTIONS
from app.rules.runaway import HOSTILE_THRESHOLD
from tests.conftest import auth_headers, enable_ai_reply


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    client.put("/avatars/mine", headers=ha, json={"name": "小恶魔", "persona": {"tone": "毒舌"}})
    client.put("/avatars/mine", headers=hb, json={"name": "狗蛋", "persona": {"tone": "憨憨"}})
    return ha, hb


def _act(client, headers, action_type, key):
    return client.post(
        "/actions", headers=headers, json={"action_type": action_type, "content": "", "client_key": key}
    )


def _abuse(client, headers, times=HOSTILE_THRESHOLD, tag="x"):
    for i in range(times):
        assert _act(client, headers, "scold", f"{tag}{i}").status_code == 200


def _pet(client, headers):
    return client.get("/avatars/pet", headers=headers).json()


def _runaway_events(client):
    db = client.session_factory()
    try:
        return db.query(Event).filter(Event.action_type == "runaway").all()
    finally:
        db.close()


def test_only_scolding_with_no_comfort_makes_it_leave(client):
    ha, hb = _pair(client)
    assert _pet(client, hb)["is_away"] is False
    _abuse(client, hb)
    live.detect_runaways()

    pet = _pet(client, hb)
    assert pet["is_away"] is True
    assert pet["runaway_note"]  # 它留了张纸条


def test_below_the_threshold_it_stays(client):
    ha, hb = _pair(client)
    _abuse(client, hb, times=HOSTILE_THRESHOLD - 1)
    live.detect_runaways()
    assert _pet(client, hb)["is_away"] is False


def test_one_comforting_gesture_keeps_it_home(client):
    ha, hb = _pair(client)
    _abuse(client, hb)
    _act(client, hb, "hug", "hug1")  # 骂完哄了一下
    live.detect_runaways()
    assert _pet(client, hb)["is_away"] is False


def test_the_two_mirrored_avatars_run_away_independently(client):
    """共享数值会一起涨，但出走只看「谁欺负了谁的分身」。"""
    ha, hb = _pair(client)
    _abuse(client, hb)  # 只有 bob 在骂他养的那只
    live.detect_runaways()
    assert _pet(client, hb)["is_away"] is True
    assert _pet(client, ha)["is_away"] is False  # alice 什么都没干，她的分身还在


def test_detecting_twice_does_not_leave_twice(client):
    ha, hb = _pair(client)
    _abuse(client, hb)
    live.detect_runaways()
    live.detect_runaways()
    assert len(_runaway_events(client)) == 1


def test_the_runaway_event_is_actored_by_the_keeper(client):
    """runaway 和 coax 都记 keeper，才能用同一把钥匙配对。"""
    ha, hb = _pair(client)
    _abuse(client, hb)
    live.detect_runaways()
    ev = _runaway_events(client)[0]
    assert ev.kind == "system"
    assert ev.actor_user_id == 2  # bob = keeper，不是 subject
    assert ev.parent_event_id is None


def test_while_away_every_action_but_coax_is_blocked(client):
    ha, hb = _pair(client)
    _abuse(client, hb)
    live.detect_runaways()

    for action in ("poke", "hug", "chat", "feed_dogfood"):
        r = _act(client, hb, action, f"blocked-{action}")
        assert r.status_code == 409
        assert r.json()["detail"] == "pet_away"


def test_coaxing_brings_it_home(client):
    ha, hb = _pair(client)
    _abuse(client, hb)
    live.detect_runaways()

    assert _act(client, hb, "coax", "coax1").status_code == 200
    pet = _pet(client, hb)
    assert pet["is_away"] is False and pet["runaway_note"] is None
    assert _act(client, hb, "poke", "after-coax").status_code == 200  # 又能玩了


def test_coming_home_it_speaks_when_replies_are_on(client):
    ha, hb = _pair(client)
    enable_ai_reply(client, hb)
    _abuse(client, hb)
    live.detect_runaways()

    r = _act(client, hb, "coax", "coax1")
    reaction = next(e for e in r.json()["events"] if e["kind"] == "ai_reaction")
    assert reaction["content"] in LOCAL_REACTIONS["coax"]  # 面子还端着，脚已经迈进门了


def test_coming_home_stays_quiet_when_replies_are_off(client):
    """「分身回复」关掉就是彻底不接话，coax 不例外——爽点是空窝变回分身本身。"""
    ha, hb = _pair(client)  # 默认关
    _abuse(client, hb)
    live.detect_runaways()
    kinds = [e["kind"] for e in _act(client, hb, "coax", "coax1").json()["events"]]
    assert kinds == ["action"]


def test_it_does_not_bolt_again_right_after_being_coaxed(client):
    """coax 本身是安抚动作，落库后窗口内 soothe>0，不该立刻二次出走。"""
    ha, hb = _pair(client)
    _abuse(client, hb)
    live.detect_runaways()
    _act(client, hb, "coax", "coax1")
    live.detect_runaways()
    assert _pet(client, hb)["is_away"] is False


def test_a_partner_who_never_scolded_is_untouched_by_the_block(client):
    ha, hb = _pair(client)
    _abuse(client, hb)
    live.detect_runaways()
    assert _act(client, ha, "poke", "alice-poke").status_code == 200


def test_the_avatar_stops_nudging_while_it_is_away(client):
    ha, hb = _pair(client)
    _abuse(client, hb)
    live.detect_runaways()
    assert client.post("/nudge", headers=hb).json()["event"] is None


def test_pushes_the_keeper_when_it_bolts(client, monkeypatch):
    ha, hb = _pair(client)
    _abuse(client, hb)
    sent = []
    monkeypatch.setattr(live.push_service, "send_to_user", lambda uid, p: sent.append((uid, p["tag"])))
    live.detect_runaways()
    assert sent == [(2, "runaway")]  # 只推给 bob（养它的人）


def test_never_raises_when_the_note_generator_explodes(client, monkeypatch):
    ha, hb = _pair(client)
    _abuse(client, hb)
    monkeypatch.setattr(live, "generate_runaway_note", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    live.detect_runaways()  # 不该抛
    assert _pet(client, hb)["is_away"] is False


def test_replaying_a_blocked_action_key_still_returns_its_old_bundle(client):
    """幂等早返回排在拦截之前：跑之前发过的动作，重放不该变成 409。"""
    ha, hb = _pair(client)
    first = _act(client, hb, "poke", "before-bolt")
    assert first.status_code == 200
    _abuse(client, hb, tag="s")
    live.detect_runaways()

    replay = _act(client, hb, "poke", "before-bolt")
    assert replay.status_code == 200
    assert [e["id"] for e in replay.json()["events"]] == [e["id"] for e in first.json()["events"]]
