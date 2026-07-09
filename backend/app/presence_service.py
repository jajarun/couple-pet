"""在线态编排：写心跳 / 读对方是否在线。事务由 router 掌管，这里只 flush。

**全仓库只有 `POST /presence` 会调 `touch()`。** 别把它挂进 `GET /events` 或 `POST /actions`——
那会让「读」变成「写」，而且一方发完动作对方就凭空"在线"了，同框 ×2 会莫名其妙地生效。
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app import push_service
from app.config import settings
from app.models import Couple, User
from app.rules import presence


def touch(db: Session, user: User, now: datetime) -> None:
    user.last_seen_at = now
    db.flush()


def partner_online(db: Session, couple: Couple | None, me_id: int, now: datetime) -> bool:
    """对方此刻是否也开着页面。没配对 / 对方从没打过心跳 → False。"""
    if couple is None:
        return False
    partner_id = push_service.partner_of(couple, me_id)
    if partner_id is None:
        return False
    partner = db.get(User, partner_id)
    if partner is None:
        return False
    return presence.is_online(partner.last_seen_at, now, settings.presence_ttl_seconds)
