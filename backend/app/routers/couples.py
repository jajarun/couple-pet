import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.models import Avatar, Couple, CoupleStats, User
from app.rules.stats import DEFAULT_STATS
from app.time_utils import utcnow

router = APIRouter(prefix="/couples", tags=["couples"])


class JoinIn(BaseModel):
    pair_code: str


def _generate_pair_code(db: Session) -> str:
    for _ in range(10):
        code = secrets.token_hex(3).upper()  # 6 hex chars
        if db.query(Couple).filter(Couple.pair_code == code).first() is None:
            return code
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "could not allocate pair code")


def _has_any_couple(db: Session, user_id: int) -> Couple | None:
    return (
        db.query(Couple)
        .filter(
            Couple.status.in_(["pending", "active"]),
            or_(Couple.user_a_id == user_id, Couple.user_b_id == user_id),
        )
        .first()
    )


@router.post("")
def create_couple(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    if _has_any_couple(db, user.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already in a couple")
    couple = Couple(user_a_id=user.id, pair_code=_generate_pair_code(db), status="pending")
    db.add(couple)
    db.commit()
    db.refresh(couple)
    return {"couple_id": couple.id, "pair_code": couple.pair_code, "status": couple.status}


@router.post("/join")
def join_couple(
    body: JoinIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    couple = db.query(Couple).filter(Couple.pair_code == body.pair_code).first()
    if couple is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invalid pair code")
    if couple.status == "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "couple already active")
    if couple.user_a_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot join your own code")
    if _has_any_couple(db, user.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already in a couple")

    couple.user_b_id = user.id
    couple.status = "active"
    couple.paired_at = utcnow()
    a_id, b_id = couple.user_a_id, couple.user_b_id
    # 两只镜像分身：subject 设人设/被代表，keeper 天天互动
    db.add_all(
        [
            Avatar(couple_id=couple.id, subject_user_id=a_id, keeper_user_id=b_id),
            Avatar(couple_id=couple.id, subject_user_id=b_id, keeper_user_id=a_id),
            CoupleStats(couple_id=couple.id, stats=dict(DEFAULT_STATS)),
        ]
    )
    db.commit()
    return {"couple_id": couple.id, "status": couple.status}


@router.get("/me")
def my_couple(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    active = get_active_couple(db, user)
    if active is not None:
        partner_id = active.user_b_id if active.user_a_id == user.id else active.user_a_id
        return {"couple_id": active.id, "status": "active", "partner_id": partner_id}
    pending = (
        db.query(Couple)
        .filter(Couple.status == "pending", Couple.user_a_id == user.id)
        .first()
    )
    if pending is not None:
        return {"couple_id": pending.id, "status": "pending", "pair_code": pending.pair_code}
    return {"couple_id": None, "status": "none"}
