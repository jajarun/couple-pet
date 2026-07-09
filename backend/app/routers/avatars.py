from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import evolution_service, runaway_service
from app.config import settings
from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.live_scheduler import dream_client_key
from app.models import Avatar, Event, User
from app.rules import runaway, streak
from app.time_utils import utcnow

router = APIRouter(prefix="/avatars", tags=["avatars"])


def _today():
    return streak.today_for(utcnow(), settings.streak_utc_offset_hours)


class AvatarUpdate(BaseModel):
    name: str | None = None
    appearance: dict | None = None
    persona: dict | None = None


def _avatar_out(av: Avatar) -> dict:
    return {
        "id": av.id,
        "couple_id": av.couple_id,
        "subject_user_id": av.subject_user_id,
        "keeper_user_id": av.keeper_user_id,
        "name": av.name,
        "appearance": av.appearance,
        "persona": av.persona,
        # /pet → 我把 TA 养成了什么样；/mine → 我在 TA 眼里被养成了什么样
        "evolution": evolution_service.build_view(av),
    }


def _runaway_out(db: Session, couple_id: int, keeper_id: int) -> dict:
    """这只分身的出走三态。两个端点都带：
    /pet → 我养的那只被我气跑了；/mine → 代表我的那只被 TA 气跑了（点头的按钮在我这儿）。
    """
    state = runaway_service.pet_state(db, couple_id, keeper_id)
    home = state == runaway.HOME
    return {
        "runaway_state": state,
        "is_away": not home,
        "runaway_note": None if home else runaway_service.latest_note(db, couple_id, keeper_id),
    }


def _require_couple(db: Session, user: User):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")
    return couple


@router.get("/mine")
def get_mine(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    couple = _require_couple(db, user)
    av = (
        db.query(Avatar)
        .filter(Avatar.couple_id == couple.id, Avatar.subject_user_id == user.id)
        .first()
    )
    # keeper 是对方：代表我的那只，跑的是 TA 家的门
    return {**_avatar_out(av), **_runaway_out(db, couple.id, av.keeper_user_id)}


@router.put("/mine")
def update_mine(
    body: AvatarUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    couple = _require_couple(db, user)
    av = (
        db.query(Avatar)
        .filter(Avatar.couple_id == couple.id, Avatar.subject_user_id == user.id)
        .first()
    )
    if body.name is not None:
        av.name = body.name
    if body.appearance is not None:
        av.appearance = body.appearance
    if body.persona is not None:
        av.persona = body.persona
    db.commit()
    db.refresh(av)
    return _avatar_out(av)


def _todays_dream(db: Session, av: Avatar) -> dict | None:
    """今早那条梦话（由 live_scheduler 落下）。没有就 None，前端不渲染梦话卡。"""
    key = dream_client_key(av.id, _today())
    ev = (
        db.query(Event)
        .filter(
            Event.couple_id == av.couple_id,
            Event.client_key == key,
            Event.kind == "ai_reaction",
        )
        .first()
    )
    return {"content": ev.content, "at": ev.created_at.isoformat() + "Z"} if ev else None


@router.get("/pet")
def get_pet(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    couple = _require_couple(db, user)
    av = (
        db.query(Avatar)
        .filter(Avatar.couple_id == couple.id, Avatar.keeper_user_id == user.id)
        .first()
    )
    return {
        **_avatar_out(av),
        "dream": _todays_dream(db, av),
        **_runaway_out(db, couple.id, user.id),
    }
