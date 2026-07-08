from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import push_service
from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.models import CoupleStats, Event, User
from app.routers.actions import event_out
from app.rules.stats import apply_time_decay
from app.time_utils import utcnow

router = APIRouter(prefix="/events", tags=["events"])


class RespondIn(BaseModel):
    content: str = Field("", max_length=1000)
    client_key: str


@router.post("/{event_id}/respond")
def respond(
    event_id: int,
    body: RespondIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    couple = get_active_couple(db, user)
    if couple is None:
        # No active couple means the parent event can never be "in the
        # caller's couple" either — treat it the same as event-not-found
        # rather than 409, so outsiders without any couple get a plain 404.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "action event not found")
    parent = db.get(Event, event_id)
    if parent is None or parent.couple_id != couple.id or parent.kind != "action":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "action event not found")
    if parent.actor_user_id == user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot respond to your own action")

    existing = (
        db.query(Event)
        .filter(
            Event.couple_id == couple.id,
            Event.client_key == body.client_key,
            Event.kind == "real_response",
        )
        .first()
    )
    if existing is not None:
        return event_out(existing)

    ev = Event(
        couple_id=couple.id,
        actor_user_id=user.id,
        kind="real_response",
        content=body.content,
        parent_event_id=parent.id,
        client_key=body.client_key,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)

    # 本尊亲自顶替分身回了 → 推给发起那条动作的人（也就是对方）
    if parent.actor_user_id is not None and parent.actor_user_id != user.id:
        background_tasks.add_task(
            push_service.send_to_user,
            parent.actor_user_id,
            {
                "title": "💬 TA 本尊回你了",
                "body": "这条是 TA 亲自回的，不是分身哦～",
                "url": "/",
                "tag": "respond",
            },
        )
    return event_out(ev)


@router.get("")
def feed(
    since: int = 0,
    before: int = 0,
    limit: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """三种取法（都返回升序）：
    - before>0：拿 id<before 的最近 limit 条（向上翻历史，懒加载）
    - limit>0 且 since==0：拿最新 limit 条（首屏，不再一次性全拉）
    - 否则：拿 id>since 的全部（向前轮询新消息，原行为不变）
    另附 has_more：比返回的最旧一条更早是否还有历史。"""
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")
    base = db.query(Event).filter(Event.couple_id == couple.id)
    if before > 0:
        rows = base.filter(Event.id < before).order_by(Event.id.desc()).limit(limit or 25).all()
        rows = list(reversed(rows))
    elif limit > 0 and since == 0:
        rows = base.order_by(Event.id.desc()).limit(limit).all()
        rows = list(reversed(rows))
    else:
        rows = base.filter(Event.id > since).order_by(Event.id).all()
    has_more = bool(rows) and base.filter(Event.id < rows[0].id).first() is not None
    cs = db.get(CoupleStats, couple.id)
    elapsed = (utcnow() - cs.stats_updated_at).total_seconds()
    live_stats = apply_time_decay(cs.stats, elapsed)  # 只读，不落库
    return {
        "events": [event_out(e) for e in rows],
        "stats": live_stats,
        "has_more": has_more,
    }
