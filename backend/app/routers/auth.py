from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import create_access_token, hash_password, verify_password
from app.time_utils import utcnow

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    nickname: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    nickname: str
    password: str


class UserOut(BaseModel):
    id: int
    nickname: str


def _token_response(user: User) -> dict:
    return {
        "access_token": create_access_token(sub=str(user.id)),
        "token_type": "bearer",
        "user": UserOut(id=user.id, nickname=user.nickname).model_dump(),
    }


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.nickname == body.nickname).first()
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "nickname already taken")
    user = User(nickname=body.nickname, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.nickname == body.nickname).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad credentials")
    user.last_login_at = utcnow()
    db.commit()
    return _token_response(user)
