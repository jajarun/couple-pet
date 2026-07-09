"""离家出走：骂满 5 次当场就跑（无定时任务），哄完还得对方点头才回得来。

判据纯看饲养者自己的行为，三态纯从事件流派生（零新字段）。
"""

from datetime import timedelta

import app.push_service as ps
from app.models import Event
from app.rules.actions import LOCAL_REACTIONS
from app.rules.runaway import HOSTILE_THRESHOLD
from app.time_utils import utcnow
from tests.conftest import auth_headers, enable_ai_reply


def _pair(client):
    ha = auth_headers(client, "alice")  # alice = user 1
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")  # bob = user 2
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    client.put("/avatars/mine", headers=ha, json={"name": "小恶魔", "persona": {"tone": "毒舌"}})
    client.put("/avatars/mine", headers=hb, json={"name": "狗蛋", "persona": {"tone": "憨憨"}})
    return ha, hb


def _act(client, headers, action_type, key):
    return client.post(
        "/actions", headers=headers, json={"action_type": action_type, "content": "", "client_key": key}
    )


def _abuse(client, headers, times=HOSTILE_THRESHOLD, tag="x"):
    """骂满 times 次。最后一次落库的同一个事务里它就该跑了——没有定时任务可等。"""
    for i in range(times):
        assert _act(client, headers, "scold", f"{tag}{i}").status_code == 200


def _forgive(client, headers):
    return client.post("/runaway/forgive", headers=headers)


def _pet(client, headers):
    return client.get("/avatars/pet", headers=headers).json()


def _mine(client, headers):
    return client.get("/avatars/mine", headers=headers).json()


def _events(client, action_type):
    db = client.session_factory()
    try:
        return db.query(Event).filter(Event.action_type == action_type).order_by(Event.id).all()
    finally:
        db.close()


def _age_scolds(client, minutes):
    """把已有的骂推到 minutes 分钟前——用来把它们挤出 1 小时窗口。"""
    db = client.session_factory()
    try:
        then = utcnow() - timedelta(minutes=minutes)
        for ev in db.query(Event).filter(Event.action_type == "scold").all():
            ev.created_at = then
        db.commit()
    finally:
        db.close()


# ---------- 出走判据 ----------


def test_the_fifth_scold_makes_it_bolt_on_the_spot(client):
    ha, hb = _pair(client)
    assert _pet(client, hb)["is_away"] is False
    _abuse(client, hb)  # 第 5 次骂的响应还没返回，它已经走了

    pet = _pet(client, hb)
    assert pet["runaway_state"] == "away"
    assert pet["is_away"] is True
    assert pet["runaway_note"]  # 它留了张纸条


def test_four_scolds_are_not_enough(client):
    ha, hb = _pair(client)
    _abuse(client, hb, times=HOSTILE_THRESHOLD - 1)
    assert _pet(client, hb)["is_away"] is False


def test_the_bolting_scold_gets_no_reply(client):
    """它把纸条拍桌上就走了，没功夫回嘴——顺带省掉那次 AI 调用。"""
    ha, hb = _pair(client)
    enable_ai_reply(client, hb)
    _abuse(client, hb, times=HOSTILE_THRESHOLD - 1)
    bundle = _act(client, hb, "scold", "last").json()

    assert bundle["ran_away"] is True
    assert [e["kind"] for e in bundle["events"]] == ["action"]  # 没有 ai_reaction


def test_poking_never_drives_it_away(client):
    """首页点一下分身发的就是 poke。手滑十下不该把它逼走。"""
    ha, hb = _pair(client)
    for i in range(10):
        assert _act(client, hb, "poke", f"p{i}").status_code == 200
    assert _pet(client, hb)["is_away"] is False


def test_one_comforting_gesture_inside_the_window_keeps_it_home(client):
    ha, hb = _pair(client)
    _abuse(client, hb, times=HOSTILE_THRESHOLD - 1)
    _act(client, hb, "hug", "hug1")  # 骂到第 4 次时哄了一下 → 既往不咎
    assert _act(client, hb, "scold", "fifth").json()["ran_away"] is False
    assert _pet(client, hb)["is_away"] is False


def test_scolds_older_than_an_hour_fall_out_of_the_window(client):
    ha, hb = _pair(client)
    _abuse(client, hb, times=HOSTILE_THRESHOLD - 1)
    _age_scolds(client, minutes=61)
    assert _act(client, hb, "scold", "fresh").json()["ran_away"] is False
    assert _pet(client, hb)["is_away"] is False


def test_scolds_still_inside_the_window_do_count(client):
    ha, hb = _pair(client)
    _abuse(client, hb, times=HOSTILE_THRESHOLD - 1)
    _age_scolds(client, minutes=30)
    assert _act(client, hb, "scold", "fresh").json()["ran_away"] is True


def test_the_two_mirrored_avatars_run_away_independently(client):
    """共享数值会一起涨，但出走只看「谁欺负了谁的分身」。"""
    ha, hb = _pair(client)
    _abuse(client, hb)  # 只有 bob 在骂他养的那只
    assert _pet(client, hb)["is_away"] is True
    assert _pet(client, ha)["is_away"] is False  # alice 什么都没干，她的分身还在


def test_it_leaves_exactly_one_note(client):
    ha, hb = _pair(client)
    _abuse(client, hb)
    assert len(_events(client, "runaway")) == 1


def test_the_runaway_event_is_actored_by_the_keeper(client):
    """runaway / coax / forgive 都记 keeper，才能用同一把钥匙配对。"""
    ha, hb = _pair(client)
    _abuse(client, hb)
    ev = _events(client, "runaway")[0]
    assert ev.kind == "system"
    assert ev.actor_user_id == 2  # bob = keeper，不是 subject
    assert ev.parent_event_id is None


# ---------- 出走期间 ----------


def test_while_away_every_action_but_coax_is_blocked(client):
    ha, hb = _pair(client)
    _abuse(client, hb)

    for action in ("poke", "hug", "chat", "feed_dogfood", "scold"):
        r = _act(client, hb, action, f"blocked-{action}")
        assert r.status_code == 409
        assert r.json()["detail"] == "pet_away"


def test_a_partner_who_never_scolded_is_untouched_by_the_block(client):
    ha, hb = _pair(client)
    _abuse(client, hb)
    assert _act(client, ha, "poke", "alice-poke").status_code == 200


def test_the_avatar_stops_nudging_while_it_is_away(client):
    ha, hb = _pair(client)
    _abuse(client, hb)
    assert client.post("/nudge", headers=hb).json()["event"] is None


def test_replaying_a_blocked_action_key_still_returns_its_old_bundle(client):
    """幂等早返回排在拦截之前：跑之前发过的动作，重放不该变成 409。"""
    ha, hb = _pair(client)
    first = _act(client, hb, "poke", "before-bolt")
    assert first.status_code == 200
    _abuse(client, hb, tag="s")

    replay = _act(client, hb, "poke", "before-bolt")
    assert replay.status_code == 200
    assert [e["id"] for e in replay.json()["events"]] == [e["id"] for e in first.json()["events"]]


# ---------- 哄 → 等对方点头 ----------


def test_coaxing_only_gets_it_to_the_doorstep(client):
    """这次改动的核心：哄完是 pending，不是回家。钥匙在对方手里。"""
    ha, hb = _pair(client)
    _abuse(client, hb)
    assert _act(client, hb, "coax", "coax1").status_code == 200

    pet = _pet(client, hb)
    assert pet["runaway_state"] == "pending"
    assert pet["is_away"] is True  # 还没回来
    assert pet["runaway_note"]  # 纸条还贴在那儿


def test_while_pending_even_coaxing_again_is_blocked(client):
    """否则 coax 的「委屈 −30 / 亲密 +5」能在等待期里无限刷。"""
    ha, hb = _pair(client)
    _abuse(client, hb)
    _act(client, hb, "coax", "coax1")

    for action in ("coax", "poke", "hug"):
        r = _act(client, hb, action, f"pending-{action}")
        assert r.status_code == 409
        assert r.json()["detail"] == "awaiting_forgiveness"


def test_coming_home_it_speaks_when_replies_are_on(client):
    ha, hb = _pair(client)
    enable_ai_reply(client, hb)
    _abuse(client, hb)

    r = _act(client, hb, "coax", "coax1")
    reaction = next(e for e in r.json()["events"] if e["kind"] == "ai_reaction")
    assert reaction["content"] in LOCAL_REACTIONS["coax"]  # 面子还端着，脚已经迈进门了


def test_coming_home_stays_quiet_when_replies_are_off(client):
    """「分身回复」关掉就是彻底不接话，coax 不例外。"""
    ha, hb = _pair(client)  # 默认关
    _abuse(client, hb)
    kinds = [e["kind"] for e in _act(client, hb, "coax", "coax1").json()["events"]]
    assert kinds == ["action"]


def test_the_partner_sees_the_pending_request_on_their_own_avatar(client):
    """跑掉的是「代表 alice、养在 bob 那儿」的那只 → 点头的按钮在 alice 这边。"""
    ha, hb = _pair(client)
    assert _mine(client, ha)["runaway_state"] == "home"
    _abuse(client, hb)
    assert _mine(client, ha)["runaway_state"] == "away"
    _act(client, hb, "coax", "coax1")

    mine = _mine(client, ha)
    assert mine["runaway_state"] == "pending"
    assert mine["is_away"] is True
    assert mine["runaway_note"]


# ---------- 对方点头 ----------


def test_forgiving_brings_it_home(client):
    ha, hb = _pair(client)
    _abuse(client, hb)
    _act(client, hb, "coax", "coax1")

    assert _forgive(client, ha).json() == {"state": "home"}
    pet = _pet(client, hb)
    assert pet["runaway_state"] == "home"
    assert pet["is_away"] is False and pet["runaway_note"] is None
    assert _act(client, hb, "poke", "after-forgive").status_code == 200  # 又能玩了


def test_the_forgive_event_is_also_actored_by_the_keeper(client):
    """按按钮的是 alice，但事件记在 keeper(bob) 名下——它标记的是「这只分身的事」。"""
    ha, hb = _pair(client)
    _abuse(client, hb)
    _act(client, hb, "coax", "coax1")
    _forgive(client, ha)

    ev = _events(client, "forgive")[0]
    assert ev.kind == "system"
    assert ev.actor_user_id == 2
    assert "小恶魔" in ev.content and "alice" in ev.content  # 共读的一句话，只用昵称


def test_forgiving_twice_is_idempotent(client):
    ha, hb = _pair(client)
    _abuse(client, hb)
    _act(client, hb, "coax", "coax1")
    _forgive(client, ha)

    assert _forgive(client, ha).status_code == 200  # 连点/多端重放不报错
    assert len(_events(client, "forgive")) == 1


def test_you_cannot_forgive_before_being_coaxed(client):
    ha, hb = _pair(client)
    _abuse(client, hb)
    r = _forgive(client, ha)
    assert r.status_code == 409 and r.json()["detail"] == "not_pending"


def test_the_keeper_cannot_forgive_themselves(client):
    """bob 点头作用在「代表 bob、养在 alice 那儿」的那只上——那只好端端在家。"""
    ha, hb = _pair(client)
    _abuse(client, hb)
    _act(client, hb, "coax", "coax1")

    assert _forgive(client, hb).json() == {"state": "home"}  # 对 alice 养的那只是 no-op
    assert _pet(client, hb)["runaway_state"] == "pending"  # bob 养的那只还在门外
    assert _events(client, "forgive") == []


def test_forgiving_counts_as_showing_up_today(client):
    ha, hb = _pair(client)
    _abuse(client, hb)
    _act(client, hb, "coax", "coax1")
    _forgive(client, ha)
    assert client.get("/daily", headers=ha).json()["streak"]["i_did_today"] is True


def test_it_can_be_driven_away_again_after_coming_home(client):
    ha, hb = _pair(client)
    _abuse(client, hb, tag="first")
    _act(client, hb, "coax", "coax1")
    _forgive(client, ha)
    # coax 还在 1 小时窗口里 → soothe>0 → 骂再多也不跑（既往不咎）
    _abuse(client, hb, tag="again")
    assert _pet(client, hb)["is_away"] is False

    _age_scolds(client, minutes=61)  # 把 coax 和旧的骂一起挤出窗口
    db = client.session_factory()
    try:
        coax = db.query(Event).filter(Event.action_type == "coax").one()
        coax.created_at = utcnow() - timedelta(minutes=61)
        db.commit()
    finally:
        db.close()

    _abuse(client, hb, tag="third")
    assert _pet(client, hb)["runaway_state"] == "away"
    assert len(_events(client, "runaway")) == 2


# ---------- 推送 ----------


def test_bolting_pushes_the_partner_not_the_keeper(client, monkeypatch):
    """跑掉的那只代表 partner。keeper 正盯着屏幕，界面当场就换成空窝了。"""
    ha, hb = _pair(client)
    _abuse(client, hb, times=HOSTILE_THRESHOLD - 1)
    calls = []
    monkeypatch.setattr(ps, "send_to_user", lambda uid, p: calls.append((uid, p["tag"])))
    _act(client, hb, "scold", "last")
    assert calls == [(1, "runaway")]  # 只推给 alice


def test_coaxing_pushes_the_partner_to_decide(client, monkeypatch):
    ha, hb = _pair(client)
    _abuse(client, hb)
    calls = []
    monkeypatch.setattr(ps, "send_to_user", lambda uid, p: calls.append((uid, p["title"])))
    _act(client, hb, "coax", "coax1")
    assert calls == [(1, "🥺 TA 在哄你回家")]


def test_forgiving_pushes_the_keeper(client, monkeypatch):
    ha, hb = _pair(client)
    _abuse(client, hb)
    _act(client, hb, "coax", "coax1")
    calls = []
    monkeypatch.setattr(ps, "send_to_user", lambda uid, p: calls.append((uid, p["tag"])))
    _forgive(client, ha)
    assert calls == [(2, "runaway")]  # 分身回家了，告诉养它的 bob
