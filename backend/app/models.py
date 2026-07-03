from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.time_utils import utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nickname: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    ai_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_count_date: Mapped[object] = mapped_column(Date, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_login_at: Mapped[object] = mapped_column(DateTime, nullable=True)


class Couple(Base):
    __tablename__ = "couples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_a_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_b_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    pair_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)
    paired_at: Mapped[object] = mapped_column(DateTime, nullable=True)


class Avatar(Base):
    __tablename__ = "avatars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), nullable=False)
    subject_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    keeper_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    appearance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    persona: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evolution: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    memory_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)


class CoupleStats(Base):
    __tablename__ = "couple_stats"

    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), primary_key=True)
    stats: Mapped[dict] = mapped_column(JSON, nullable=False)
    stats_updated_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("couple_id", "client_key", name="uq_events_couple_client_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 轮询游标
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # action/ai_reaction/real_response/system
    action_type: Mapped[str] = mapped_column(String(32), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    parent_event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=True)
    client_key: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)
