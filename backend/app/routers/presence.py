"""在线心跳：前端每 10 秒打一次，用来点亮「TA 正在看这只分身」。

这是**唯一**写 `users.last_seen_at` 的地方（见 presence_service 的注释）。
前端用 TanStack 的 `refetchInterval` 打这个心跳，切后台会自动停 → 我自动对 TA 显示为离线，
正是「TA 正在看」想要的语义。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import presence_service
from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.models import User
from app.time_utils import utcnow

router = APIRouter(tags=["presence"])


def _now():
    return utcnow()


@router.post("/presence")
def heartbeat(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = _now()
    couple = get_active_couple(db, user)
    online = presence_service.partner_online(db, couple, user.id, now)  # 先读，再写自己的
    presence_service.touch(db, user, now)
    db.commit()
    return {"partner_online": online}
