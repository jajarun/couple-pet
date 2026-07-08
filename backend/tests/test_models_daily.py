from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models import CoupleStreak, DailyQuestion, DailyAnswer


def _session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_couple_streak_roundtrip():
    db = _session()
    db.add(CoupleStreak(couple_id=1, count=3, last_both_day=date(2026, 7, 8)))
    db.commit()
    row = db.get(CoupleStreak, 1)
    assert row.count == 3
    assert row.last_both_day == date(2026, 7, 8)
    assert row.a_active_day is None


def test_daily_question_unique_per_couple_day():
    db = _session()
    db.add(DailyQuestion(couple_id=1, day=date(2026, 7, 8), question="q", flavor="silly"))
    db.commit()
    got = db.scalars(select(DailyQuestion).where(DailyQuestion.couple_id == 1)).one()
    assert got.flavor == "silly"


def test_daily_answer_stores_content():
    db = _session()
    db.add(DailyQuestion(couple_id=1, day=date(2026, 7, 8), question="q", flavor="deep"))
    db.commit()
    db.add(DailyAnswer(question_id=1, user_id=42, content="我的答案", client_key="k1"))
    db.commit()
    ans = db.scalars(select(DailyAnswer).where(DailyAnswer.question_id == 1)).one()
    assert ans.content == "我的答案"
    assert ans.user_id == 42
