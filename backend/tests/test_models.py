from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import User, Couple, Avatar, CoupleStats, Event
from app.time_utils import utcnow


def _session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_utcnow_is_naive_utc():
    now = utcnow()
    assert isinstance(now, datetime)
    assert now.tzinfo is None


def test_user_roundtrip_and_defaults():
    db = _session()
    u = User(nickname="alice", password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    assert u.id is not None
    assert u.ai_count == 0
    assert u.created_at is not None


def test_full_couple_graph_roundtrip():
    db = _session()
    a = User(nickname="a", password_hash="x")
    b = User(nickname="b", password_hash="x")
    db.add_all([a, b])
    db.commit()
    couple = Couple(user_a_id=a.id, user_b_id=b.id, pair_code="ABC123", status="active")
    db.add(couple)
    db.commit()
    av = Avatar(
        couple_id=couple.id,
        subject_user_id=a.id,
        keeper_user_id=b.id,
        name="狗蛋",
        appearance={"emoji": "🐶"},
        persona={"tone": "毒舌"},
    )
    stats = CoupleStats(couple_id=couple.id, stats={"grievance": 0})
    db.add_all([av, stats])
    db.commit()
    ev = Event(couple_id=couple.id, actor_user_id=a.id, kind="action", action_type="scold", content="大猪蹄子")
    db.add(ev)
    db.commit()
    db.refresh(av)
    db.refresh(ev)
    assert av.appearance == {"emoji": "🐶"}
    assert av.evolution == {}          # JSON default
    assert ev.id is not None           # polling cursor
    assert ev.parent_event_id is None
