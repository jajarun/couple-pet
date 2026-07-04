from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.quota import ai_quota_available, record_ai_usage
from app.config import settings
from app.db import Base
from app.models import User
from app.time_utils import utcnow


def _session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_quota_available_until_cap():
    db = _session()
    u = User(nickname="a", password_hash="x")
    db.add(u)
    db.commit()
    for _ in range(settings.daily_chat_cap):
        assert ai_quota_available(u, db) is True
        record_ai_usage(u, db)
    assert ai_quota_available(u, db) is False  # cap reached
    assert u.ai_count == settings.daily_chat_cap


def test_quota_resets_on_new_day():
    db = _session()
    u = User(nickname="a", password_hash="x")
    u.ai_count = settings.daily_chat_cap
    u.ai_count_date = (utcnow() - timedelta(days=1)).date()
    db.add(u)
    db.commit()
    assert ai_quota_available(u, db) is True  # yesterday's count reset
    assert u.ai_count == 0  # reset does NOT increment
    record_ai_usage(u, db)
    assert u.ai_count == 1
