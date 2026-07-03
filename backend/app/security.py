from datetime import timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.time_utils import utcnow

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_ALGO = "HS256"


def hash_password(pw: str) -> str:
    return _pwd.hash(pw)


def verify_password(pw: str, pw_hash: str) -> bool:
    return _pwd.verify(pw, pw_hash)


def create_access_token(sub: str, expires_minutes: int = 60 * 24 * 7) -> str:
    expire = utcnow() + timedelta(minutes=expires_minutes)
    payload = {"sub": sub, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGO)


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGO])
    except JWTError as exc:
        raise ValueError("invalid token") from exc
    sub = payload.get("sub")
    if sub is None:
        raise ValueError("token missing subject")
    return sub
