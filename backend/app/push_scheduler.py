"""火苗定时提醒 job：每天固定时刻扫一次，给「今晚会灭」或「已断可救」的火苗对应的人发推。

跑在 uvicorn 进程内（main.py lifespan 里的 APScheduler 触发）。自开 SessionLocal。
每天单次触发 → 每对每天至多一条，天然去重，不需额外状态表。永不抛。
"""

import logging

from app import push_service, streak_service
from app.config import settings
from app.db import SessionLocal
from app.models import Couple, CoupleStreak
from app.rules import streak
from app.time_utils import utcnow

logger = logging.getLogger(__name__)

_AT_RISK = {
    "title": "🔥 火苗快灭了",
    "body": "今天还没一起打卡，火苗今晚就要熄了，去戳一下 TA 续上~",
    "url": "/",
    "tag": "streak",
}
_RESCUABLE = {
    "title": "🔥 火苗断了，但还能救",
    "body": "昨天漏了一天，今天花点亲密就能把火苗救回来，快去看看~",
    "url": "/",
    "tag": "streak",
}


def _today():
    return streak.today_for(utcnow(), settings.streak_utc_offset_hours)


def _targets_for(couple, row: CoupleStreak, today):
    """返回 (要提醒的 user_id 列表, payload)。今天已双方齐 / 无火苗可提醒时返回 ([], None)。"""
    state = streak_service._row_to_state(row)
    a_today = row.a_active_day == today
    b_today = row.b_active_day == today
    if a_today and b_today:
        return [], None  # 今天双方齐了，安全
    if streak.can_rescue(state, today):
        return [couple.user_a_id, couple.user_b_id], _RESCUABLE
    alive = row.last_both_day in (today, today - streak.ONE_DAY)
    if not alive:
        return [], None  # 已断且救不了（漏超一天）/ 从没起过火 → 不打扰
    # 还活着但今天没齐 → 今晚会灭，提醒还没打卡的那个人
    if a_today:
        return [couple.user_b_id], _AT_RISK
    if b_today:
        return [couple.user_a_id], _AT_RISK
    return [couple.user_a_id, couple.user_b_id], _AT_RISK


def remind_dying_streaks() -> None:
    """扫所有活跃情侣的火苗，给该被提醒的人发推。"""
    db = SessionLocal()
    try:
        today = _today()
        couples = db.query(Couple).filter(Couple.status == "active").all()
        for couple in couples:
            row = db.get(CoupleStreak, couple.id)
            if row is None:
                continue
            targets, payload = _targets_for(couple, row, today)
            for uid in targets:
                if uid is not None:
                    push_service.send_to_user(uid, payload)
    except Exception as e:
        logger.warning("remind_dying_streaks crashed: %s", e)
    finally:
        db.close()
