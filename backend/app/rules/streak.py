"""纯函数：情侣火苗 streak。无 DB / 时钟 / settings。today 由调用方传入。"""

from datetime import date, datetime, timedelta

ONE_DAY = timedelta(days=1)


def today_for(now_utc: datetime, offset_hours: int = 8) -> date:
    """把 naive-UTC 现在换算成固定偏移时区下的"日期"（默认 UTC+8=上海，无 DST）。"""
    return (now_utc + timedelta(hours=offset_hours)).date()


def empty_state() -> dict:
    return {
        "count": 0,
        "last_both_day": None,
        "a_active_day": None,
        "b_active_day": None,
        "rescue_day": None,
    }


def touch(state: dict, slot: str, today: date) -> dict:
    """记一次某槽（'a'/'b'）今天的有效互动，必要时推进 count。返回新 state（不改入参）。"""
    if slot not in ("a", "b"):
        raise ValueError(f"bad slot: {slot}")
    out = dict(state)
    out[f"{slot}_active_day"] = today
    both_today = out["a_active_day"] == today and out["b_active_day"] == today
    if both_today and out["last_both_day"] != today:
        out["count"] = out["count"] + 1 if out["last_both_day"] == today - ONE_DAY else 1
        out["last_both_day"] = today
    return out


def view(state: dict, slot: str, today: date) -> dict:
    """读时派生（不改存储）。slot=发起请求者的槽，用于算 i/partner_did。"""
    last = state["last_both_day"]
    alive = last in (today, today - ONE_DAY)
    a_today = state["a_active_day"] == today
    b_today = state["b_active_day"] == today
    both_today = a_today and b_today
    i_did = a_today if slot == "a" else b_today
    partner_did = b_today if slot == "a" else a_today
    lagging = None
    if alive:
        if a_today and not b_today:
            lagging = "b"
        elif b_today and not a_today:
            lagging = "a"
    return {
        "count": state["count"] if alive else 0,
        "i_did_today": i_did,
        "partner_did_today": partner_did,
        "at_risk": alive and not both_today,
        "lagging_slot": lagging,
    }


def can_rescue(state: dict, today: date) -> bool:
    """只漏了正好一天（前天完成、昨天空了）且今天还没续过，才可补救。"""
    return state["last_both_day"] == today - 2 * ONE_DAY and state["rescue_day"] != today


def rescue(state: dict, today: date) -> dict:
    out = dict(state)
    out["last_both_day"] = today - ONE_DAY  # 补成昨天完成，今天两人 touch 即可续
    out["rescue_day"] = today
    return out
