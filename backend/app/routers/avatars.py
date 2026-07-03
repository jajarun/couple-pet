from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.models import Avatar, User

router = APIRouter(prefix="/avatars", tags=["avatars"])


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
    return _avatar_out(av)


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


@router.get("/pet")
def get_pet(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    couple = _require_couple(db, user)
    av = (
        db.query(Avatar)
        .filter(Avatar.couple_id == couple.id, Avatar.keeper_user_id == user.id)
        .first()
    )
    return _avatar_out(av)
