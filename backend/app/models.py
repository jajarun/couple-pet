from sqlalchemy import (
    JSON,
    Boolean,
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
    gender: Mapped[str] = mapped_column(String(8), nullable=True)  # 'male' | 'female'
    # 分身是否自动接话；关掉则 /actions 不生成 ai_reaction，把话头留给「本尊回应」。默认关。
    ai_reply_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_count_date: Mapped[object] = mapped_column(Date, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_login_at: Mapped[object] = mapped_column(DateTime, nullable=True)
    # 在线心跳。只有 POST /presence 写它；「TA 正在看这只分身」和同框 ×2 都读它。
    last_seen_at: Mapped[object] = mapped_column(DateTime, nullable=True)


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
        UniqueConstraint(
            "couple_id", "client_key", "kind", name="uq_events_couple_client_key_kind"
        ),
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


class CoupleStreak(Base):
    __tablename__ = "couple_streaks"

    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_both_day: Mapped[object] = mapped_column(Date, nullable=True)
    a_active_day: Mapped[object] = mapped_column(Date, nullable=True)
    b_active_day: Mapped[object] = mapped_column(Date, nullable=True)
    rescue_day: Mapped[object] = mapped_column(Date, nullable=True)


class DailyQuestion(Base):
    __tablename__ = "daily_questions"
    __table_args__ = (
        UniqueConstraint("couple_id", "day", name="uq_daily_questions_couple_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), nullable=False)
    day: Mapped[object] = mapped_column(Date, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    flavor: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)


class DailyAnswer(Base):
    __tablename__ = "daily_answers"
    __table_args__ = (
        UniqueConstraint("question_id", "user_id", name="uq_daily_answers_question_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("daily_questions.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    client_key: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)


class Story(Base):
    """一章剧情副本。每对每天至多开一章（唯一约束顺带挡住并发首建）；
    没打完的会顺延到第二天（找 status='active' 的那章，不看 day）。"""

    __tablename__ = "stories"
    __table_args__ = (UniqueConstraint("couple_id", "day", name="uq_stories_couple_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), nullable=False)
    day: Mapped[object] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    total_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)
    ended_at: Mapped[object] = mapped_column(DateTime, nullable=True)


class StoryRound(Base):
    """一幕。options 为空列表 = 结局幕（没得选了）。

    (story_id, round_no) 唯一：两人几乎同时选完时双方都可能去生成下一幕，靠它挡住重复插入。
    """

    __tablename__ = "story_rounds"
    __table_args__ = (
        UniqueConstraint("story_id", "round_no", name="uq_story_rounds_story_round"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id"), nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    scene: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[object] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)


class StoryChoice(Base):
    """某人在某一幕的抉择。两人都选完才互相看得见（同每日一问的解锁范式）。"""

    __tablename__ = "story_choices"
    __table_args__ = (
        UniqueConstraint("round_id", "user_id", name="uq_story_choices_round_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("story_rounds.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    option_index: Mapped[int] = mapped_column(Integer, nullable=False)
    client_key: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)


class PushSubscription(Base):
    """一个浏览器的 Web Push 订阅。按 endpoint 唯一（重复订阅走 upsert）；
    一个 user 可有多行（多设备）。发推失败为 404/410 时按 endpoint 删除。"""

    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # 定长 VARCHAR：MySQL 不允许 TEXT 列直接建唯一索引（须给 key 长度）；
    # 512 足够容纳各家推送 endpoint（FCM/Mozilla/Apple 实测都 < 512），且 utf8mb4 下
    # 唯一索引 2048B < InnoDB 3072B 上限。
    endpoint: Mapped[str] = mapped_column(String(512), nullable=False)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow, nullable=False)
