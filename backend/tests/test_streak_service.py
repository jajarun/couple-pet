from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app import streak_service
from app.db import Base
from app.models import Couple, Event
from app.rules.streak import today_for
from app.time_utils import utcnow


def _db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _couple(db):
    c = Couple(user_a_id=1, user_b_id=2, pair_code="X", status="active")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_slot_for_maps_users_to_ab():
    class C:
        user_a_id = 1
        user_b_id = 2

    assert streak_service.slot_for(C, 1) == "a"
    assert streak_service.slot_for(C, 2) == "b"


def test_one_side_active_keeps_streak_zero():
    db = _db()
    c = _couple(db)
    streak_service.do_touch(db, c, 2)  # 只有 bob(user_b=2)
    db.commit()
    v = streak_service.build_view(db, c, 2)
    assert v["i_did_today"] is True
    assert v["partner_did_today"] is False
    assert v["count"] == 0


def test_both_active_today_streak_one():
    db = _db()
    c = _couple(db)
    streak_service.do_touch(db, c, 1)
    streak_service.do_touch(db, c, 2)
    db.commit()
    v = streak_service.build_view(db, c, 1)
    assert v["count"] == 1
    assert v["at_risk"] is False
    assert v["lagging_user_id"] is None


def test_milestone_emits_system_event():
    db = _db()
    c = _couple(db)
    today = today_for(utcnow(), 8)
    row = streak_service.get_or_create_row(db, c.id)
    row.count = 6                               # 预置：昨天完成、已 6 天
    row.last_both_day = today - timedelta(days=1)
    row.a_active_day = today - timedelta(days=1)
    row.b_active_day = today - timedelta(days=1)
    db.commit()
    streak_service.do_touch(db, c, 1)
    streak_service.do_touch(db, c, 2)           # 今天两人齐 → 6→7 里程碑
    db.commit()
    assert streak_service.build_view(db, c, 1)["count"] == 7
    systems = db.query(Event).filter(Event.kind == "system").all()
    assert any("7" in e.content for e in systems)
