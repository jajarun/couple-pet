from app.config import settings
from app.models import User
from app.time_utils import utcnow


def consume_ai_quota(user: User, db) -> bool:
    """Reset per UTC day; return False at/over cap, else increment and return True."""
    today = utcnow().date()
    if user.ai_count_date != today:
        user.ai_count = 0
        user.ai_count_date = today
    if user.ai_count >= settings.daily_chat_cap:
        db.add(user)
        db.commit()
        return False
    user.ai_count += 1
    db.add(user)
    db.commit()
    return True
