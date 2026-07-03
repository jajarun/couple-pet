from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.deepseek import generate_reaction
from app.ai.quota import consume_ai_quota
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


def test_generate_reaction_is_deterministic_and_in_persona():
    persona = {"tone": "毒舌"}
    a = generate_reaction(persona, {"grievance": 0}, "scold", "大猪蹄子")
    b = generate_reaction(persona, {"grievance": 0}, "scold", "大猪蹄子")
    assert a == b  # deterministic — safe for CI
    assert "毒舌" in a
    assert "大猪蹄子" in a


def test_quota_increments_until_cap():
    db = _session()
    u = User(nickname="a", password_hash="x")
    db.add(u)
    db.commit()
    for _ in range(settings.daily_chat_cap):
        assert consume_ai_quota(u, db) is True
    assert consume_ai_quota(u, db) is False  # cap reached
    assert u.ai_count == settings.daily_chat_cap


def test_quota_resets_on_new_day():
    db = _session()
    u = User(nickname="a", password_hash="x")
    u.ai_count = settings.daily_chat_cap
    u.ai_count_date = (utcnow() - timedelta(days=1)).date()
    db.add(u)
    db.commit()
    assert consume_ai_quota(u, db) is True  # yesterday's count reset
    assert u.ai_count == 1
