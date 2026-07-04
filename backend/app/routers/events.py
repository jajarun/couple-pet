from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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
    return event_out(ev)


@router.get("")
def feed(
    since: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")
    events = (
        db.query(Event)
        .filter(Event.couple_id == couple.id, Event.id > since)
        .order_by(Event.id)
        .all()
    )
    cs = db.get(CoupleStats, couple.id)
    elapsed = (utcnow() - cs.stats_updated_at).total_seconds()
    live_stats = apply_time_decay(cs.stats, elapsed)  # 只读，不落库
    return {"events": [event_out(e) for e in events], "stats": live_stats}
