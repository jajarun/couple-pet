"""火苗定时提醒 job：直接调 remind_dying_streaks()，用可变 dict 推进「今天」，
断言只提醒该被提醒的人。参照 test_daily.py 里推进日期的写法。"""

from datetime import date

import app.push_scheduler as sched
import app.routers.daily as daily_router
import app.streak_service as ss
from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")  # alice=user 1
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")  # bob=user 2
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    return ha, hb


def _poke(client, headers, key):
    client.post("/actions", headers=headers, json={"action_type": "poke", "content": "", "client_key": key})


def _answer_daily(client, headers, key):
    r = client.post("/daily/answer", headers=headers, json={"content": "随便答两句", "client_key": key})
    assert r.status_code == 200
    return r


def test_reminds_only_lagging_user(client, monkeypatch):
    ha, hb = _pair(client)
    day = {"d": date(2026, 7, 7)}
    monkeypatch.setattr(ss, "_today", lambda: day["d"])
    monkeypatch.setattr(sched, "_today", lambda: day["d"])
    _poke(client, ha, "a0")  # 昨天双方齐 → 起火
    _poke(client, hb, "b0")
    day["d"] = date(2026, 7, 8)  # 今天：alice 打卡、bob 没
    _poke(client, ha, "a1")

    sent = []
    monkeypatch.setattr(sched.push_service, "send_to_user", lambda uid, p: sent.append((uid, p)))
    sched.remind_dying_streaks()
    assert [u for u, _ in sent] == [2]  # 只提醒没打卡的 bob
    assert sent[0][1]["tag"] == "streak"


def test_no_remind_when_both_done_today(client, monkeypatch):
    ha, hb = _pair(client)
    day = {"d": date(2026, 7, 8)}
    monkeypatch.setattr(ss, "_today", lambda: day["d"])
    monkeypatch.setattr(sched, "_today", lambda: day["d"])
    _poke(client, ha, "a1")
    _poke(client, hb, "b1")  # 今天双方齐 → 安全

    sent = []
    monkeypatch.setattr(sched.push_service, "send_to_user", lambda uid, p: sent.append((uid, p)))
    sched.remind_dying_streaks()
    assert sent == []


def test_reminds_both_when_rescuable(client, monkeypatch):
    ha, hb = _pair(client)
    day = {"d": date(2026, 7, 6)}
    monkeypatch.setattr(ss, "_today", lambda: day["d"])
    monkeypatch.setattr(sched, "_today", lambda: day["d"])
    _poke(client, ha, "a0")  # 前天双方齐
    _poke(client, hb, "b0")
    day["d"] = date(2026, 7, 8)  # 跳过昨天 → 漏正好一天 → 可救

    sent = []
    monkeypatch.setattr(sched.push_service, "send_to_user", lambda uid, p: sent.append((uid, p)))
    sched.remind_dying_streaks()
    assert sorted(u for u, _ in sent) == [1, 2]  # 可救时提醒双方
    assert all(p["tag"] == "streak" for _, p in sent)


def _fix_day(monkeypatch, d):
    """把每日一问的「今天」与 scheduler 的「今天」钉在同一天，避免跨零点抖动。"""
    monkeypatch.setattr(daily_router, "_today", lambda: d)
    monkeypatch.setattr(sched, "_today", lambda: d)


def test_daily_nudge_reminds_both_when_neither_answered(client, monkeypatch):
    ha, hb = _pair(client)
    _fix_day(monkeypatch, date(2026, 7, 8))  # 谁都没答，连题都还没生成

    sent = []
    monkeypatch.setattr(sched.push_service, "send_to_user", lambda uid, p: sent.append((uid, p)))
    sched.remind_unanswered_daily()
    assert sorted(u for u, _ in sent) == [1, 2]  # 两人都催
    assert all(p["tag"] == "daily" for _, p in sent)


def test_daily_nudge_reminds_only_the_one_who_hasnt(client, monkeypatch):
    ha, hb = _pair(client)
    _fix_day(monkeypatch, date(2026, 7, 8))
    _answer_daily(client, ha, "a1")  # alice 答了，bob 没

    sent = []
    monkeypatch.setattr(sched.push_service, "send_to_user", lambda uid, p: sent.append((uid, p)))
    sched.remind_unanswered_daily()
    assert [u for u, _ in sent] == [2]  # 只催没答的 bob


def test_daily_nudge_silent_when_both_answered(client, monkeypatch):
    ha, hb = _pair(client)
    _fix_day(monkeypatch, date(2026, 7, 8))
    _answer_daily(client, ha, "a1")
    _answer_daily(client, hb, "b1")  # 双方都答了 → 不催

    sent = []
    monkeypatch.setattr(sched.push_service, "send_to_user", lambda uid, p: sent.append((uid, p)))
    sched.remind_unanswered_daily()
    assert sent == []


def test_no_remind_for_long_dead_streak(client, monkeypatch):
    ha, hb = _pair(client)
    day = {"d": date(2026, 7, 1)}
    monkeypatch.setattr(ss, "_today", lambda: day["d"])
    monkeypatch.setattr(sched, "_today", lambda: day["d"])
    _poke(client, ha, "a0")  # 很久以前起过火
    _poke(client, hb, "b0")
    day["d"] = date(2026, 7, 8)  # 漏了好几天 → 救不回来，别打扰

    sent = []
    monkeypatch.setattr(sched.push_service, "send_to_user", lambda uid, p: sent.append((uid, p)))
    sched.remind_dying_streaks()
    assert sent == []
