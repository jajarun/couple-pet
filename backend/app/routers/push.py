"""Web Push 订阅管理：前端订阅/退订浏览器推送，以及下发 VAPID 公钥。"""

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import PushSubscription, User

router = APIRouter(prefix="/push", tags=["push"])


class SubKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeIn(BaseModel):
    endpoint: str
    keys: SubKeys


class UnsubscribeIn(BaseModel):
    endpoint: str


@router.get("/public-key")
def public_key():
    """前端订阅要用的 VAPID 公钥；空串表示服务端未启用推送，前端据此隐藏开关。"""
    return {"key": settings.vapid_public_key}


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
def subscribe(
    body: SubscribeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 按 endpoint 唯一：同一浏览器重复订阅 → 更新归属与密钥，不新增行
    row = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == body.endpoint)
        .first()
    )
    if row is None:
        row = PushSubscription(endpoint=body.endpoint)
        db.add(row)
    row.user_id = user.id
    row.p256dh = body.keys.p256dh
    row.auth = body.keys.auth
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    body: UnsubscribeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db.query(PushSubscription).filter(
        PushSubscription.endpoint == body.endpoint,
        PushSubscription.user_id == user.id,
    ).delete()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
