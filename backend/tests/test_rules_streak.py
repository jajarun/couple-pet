from datetime import date, datetime, timedelta

from app.rules.streak import (
    today_for,
    empty_state,
    touch,
    view,
    can_rescue,
    rescue,
)

D = date(2026, 7, 8)          # "今天"
Y = D - timedelta(days=1)     # 昨天
DBY = D - timedelta(days=2)   # 前天


def test_today_for_applies_utc8_offset():
    # 2026-07-08 17:00 UTC = 2026-07-09 01:00 +08 → 落在 7/9
    assert today_for(datetime(2026, 7, 8, 17, 0, 0), 8) == date(2026, 7, 9)
    assert today_for(datetime(2026, 7, 8, 15, 0, 0), 8) == date(2026, 7, 8)


def test_empty_state_shape():
    s = empty_state()
    assert s == {
        "count": 0,
        "last_both_day": None,
        "a_active_day": None,
        "b_active_day": None,
        "rescue_day": None,
    }


def test_touch_one_side_does_not_advance():
    s = touch(empty_state(), "a", D)
    assert s["a_active_day"] == D
    assert s["count"] == 0            # 只有一方，火苗没起
    assert s["last_both_day"] is None


def test_touch_both_today_starts_at_one():
    s = touch(empty_state(), "a", D)
    s = touch(s, "b", D)
    assert s["count"] == 1
    assert s["last_both_day"] == D


def test_touch_continues_from_yesterday():
    s = {"count": 5, "last_both_day": Y, "a_active_day": Y, "b_active_day": Y, "rescue_day": None}
    s = touch(s, "a", D)
    s = touch(s, "b", D)
    assert s["count"] == 6            # 昨天完成→今天+1


def test_touch_resets_after_gap():
    s = {"count": 5, "last_both_day": DBY, "a_active_day": DBY, "b_active_day": DBY, "rescue_day": None}
    s = touch(s, "a", D)
    s = touch(s, "b", D)
    assert s["count"] == 1            # 断了→重新从 1 起


def test_touch_same_day_is_idempotent():
    s = touch(touch(empty_state(), "a", D), "b", D)
    again = touch(s, "a", D)         # 同一天再 touch 不重复 +1
    assert again["count"] == 1


def test_view_alive_and_both_done():
    s = touch(touch(empty_state(), "a", D), "b", D)
    v = view(s, "a", D)
    assert v == {
        "count": 1,
        "i_did_today": True,
        "partner_did_today": True,
        "at_risk": False,
        "rescuable": False,
        "lagging_slot": None,
    }


def test_view_one_done_one_not_flags_lagging():
    s = touch(empty_state(), "a", D)  # 只有 a 今天动了；last_both_day 仍 None
    s["last_both_day"] = Y            # 假设昨天完成过，火苗还活着
    v_from_a = view(s, "a", D)
    assert v_from_a["i_did_today"] is True
    assert v_from_a["partner_did_today"] is False
    assert v_from_a["at_risk"] is True
    assert v_from_a["lagging_slot"] == "b"   # 该催 b
    v_from_b = view(s, "b", D)
    assert v_from_b["i_did_today"] is False
    assert v_from_b["partner_did_today"] is True


def test_view_broken_shows_zero():
    s = {"count": 9, "last_both_day": DBY, "a_active_day": DBY, "b_active_day": DBY, "rescue_day": None}
    v = view(s, "a", D)
    assert v["count"] == 0            # 断了显示 0
    assert v["at_risk"] is False
    assert v["rescuable"] is True     # 只漏一天 → 露出续火按钮


def test_view_rescuable_flag_tracks_can_rescue():
    # 存活（今天两人都完成）→ 不可救
    alive = touch(touch(empty_state(), "a", D), "b", D)
    assert view(alive, "a", D)["rescuable"] is False
    # 漏超过一天 → 不可救
    big_gap = {"count": 3, "last_both_day": D - timedelta(days=3), "a_active_day": None, "b_active_day": None, "rescue_day": None}
    assert view(big_gap, "a", D)["rescuable"] is False
    # 漏正好一天但今天已续过 → 不可救
    used = {"count": 3, "last_both_day": DBY, "a_active_day": DBY, "b_active_day": DBY, "rescue_day": D}
    assert view(used, "a", D)["rescuable"] is False


def test_rescue_only_when_missed_exactly_one_day():
    ok = {"count": 3, "last_both_day": DBY, "a_active_day": DBY, "b_active_day": DBY, "rescue_day": None}
    assert can_rescue(ok, D) is True
    r = rescue(ok, D)
    assert r["last_both_day"] == Y    # 补成昨天完成
    assert r["rescue_day"] == D
    assert r["count"] == 3            # 天数保留
    # 今天再让两人 touch 就能续上
    r = touch(touch(r, "a", D), "b", D)
    assert r["count"] == 4


def test_rescue_blocked_twice_same_day_or_bigger_gap():
    used = {"count": 3, "last_both_day": DBY, "a_active_day": DBY, "b_active_day": DBY, "rescue_day": D}
    assert can_rescue(used, D) is False           # 今天已续过
    big_gap = {"count": 3, "last_both_day": D - timedelta(days=3), "a_active_day": None, "b_active_day": None, "rescue_day": None}
    assert can_rescue(big_gap, D) is False         # 漏超过一天，不给救
