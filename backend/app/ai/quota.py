from app.config import settings
from app.models import User
from app.time_utils import utcnow


def ai_quota_available(user: User, db) -> bool:
    """应用每日重置（跨 UTC 日归零并 commit）；返回是否还在额度内。只查不加。"""
    today = utcnow().date()
    if user.ai_count_date != today:
        user.ai_count = 0
        user.ai_count_date = today
        db.add(user)
        db.commit()
    return user.ai_count < settings.daily_chat_cap


def record_ai_usage(user: User, db) -> None:
    """AI 真成功后计一次数。"""
    user.ai_count += 1
    db.add(user)
    db.commit()
