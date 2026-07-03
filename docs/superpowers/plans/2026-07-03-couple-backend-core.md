# 情侣分身后端核心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the testable FastAPI backend core for the couple avatar-pet game — accounts, pairing, mirrored avatars, shared relationship stats, and the unified interaction/event flow — with DeepSeek behind a deterministic stub.

**Architecture:** Backend is the single source of truth; the frontend (a later plan) is pure display. Relationship stats live in one shared pool per couple and change over time via lazy timestamp computation (no cron). All rules live in pure functions (no DB/clock/AI imports). Every interaction follows one flow: apply stats → write an `action` event → attach an `ai_reaction` (stub or local template) → partner polls the shared timeline → partner may post a `real_response`. DeepSeek is swapped in later; this plan uses a deterministic stub so CI never calls a real API.

**Tech Stack:** Python 3.11+ (uv-managed CPython 3.13 venv), FastAPI, SQLAlchemy 2.0, Pydantic v2 / pydantic-settings, PyMySQL (prod) / in-memory SQLite + StaticPool (tests), python-jose (JWT HS256), passlib[bcrypt], pytest, httpx TestClient.

## Global Constraints

Every task's requirements implicitly include this section.

- **Backend is the single source of truth.** This plan is backend-only; no frontend, no real network AI.
- **No background/cron jobs.** Time-based stat changes are computed lazily from `couple_stats.stats_updated_at` on read/write.
- **Pure rules engine.** Files under `app/rules/` import no DB, no clock, no AI, no config. Elapsed time enters as an `elapsed_seconds: float` parameter.
- **Stats shape:** exactly 4 keys — `grievance` (委屈值), `dogfood` (狗粮值), `miss` (想你值), `intimacy` (亲密度). Every value is an `int` in `[0, 100]` (use `clamp`). `intimacy` never changes with time (only actions raise it).
- **Time deltas per hour:** `miss +4.0`, `grievance -2.0`, `dogfood -1.0`, `intimacy` absent (no time change).
- **Grievance safety valve:** `GRIEVANCE_THRESHOLD = 80`; at/above it the interaction appends a `system` narration event ("该哄了").
- **One shared stats pool per couple.** Both partners read the same `couple_stats` row.
- **`events.id` is the polling cursor.** Events are append-only; `GET /events?since=<id>` returns only rows with `id > since`, ordered by `id` ascending.
- **Action idempotency via `client_key`.** One action produces one event bundle; a retry with the same `(couple_id, client_key)` returns the existing bundle, never a duplicate.
- **`couple_stats` writes run inside a DB transaction** (single `commit`, `rollback` on error).
- **Permissions:** a user may act only within their own `active` couple, may act only on the avatar they keep, and may `real_response` only to a partner's `action` event in their couple.
- **DeepSeek is a deterministic stub in this plan** (`app/ai/deepseek.py`). AI is called only for `scold` and `chat` actions and safety-valve narration; cheap actions (`poke`, `feed_dogfood`, `hug`, `miss_you`, `apologize`) use local templates. Never call a real API in tests.
- **Per-user daily AI cap** = `settings.daily_chat_cap` (50), reset per UTC date. Over cap → fall back to a local template, never error.
- **Time helper:** all stored/compared datetimes are naive UTC via `app.time_utils.utcnow()` (no `datetime.utcnow()` — it warns; no aware/naive mixing).
- **Out of scope (deferred to later plans / upgrade slots):** real DeepSeek calls and their safety guardrails (comedic-buffer system prompt, input filtering, intimacy-scale limits) — these only bind the real model and belong with the AI-integration plan; the `evolution` column exists but avatar evolution/进化 triggers are not implemented here; real-response content moderation; SSE/WebSocket; Web Push; per-direction stat ledgers.

---

### Task 1: Branch setup & reusable foundation

**Files:**
- Create branch `feat/couple-backend-core` off `main`
- Reuse (from `feat/backend-foundation`): `backend/.gitignore`, `backend/requirements.txt`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/main.py`, `backend/tests/__init__.py`, `backend/tests/test_health.py`
- Do NOT bring over the single-player rules: `backend/app/rules/stats.py`, `backend/app/rules/care.py`, `backend/tests/test_rules_stats.py`, `backend/tests/test_rules_care.py`

**Interfaces:**
- Produces: `app.config.settings` (`database_url`, `jwt_secret`, `daily_chat_cap=50`, `deepseek_api_key`); `app.db` (`Base`, `engine`, `SessionLocal`, `get_db`); `app.main.app` with `GET /health`.

- [ ] **Step 1: Create the branch off main**

```bash
cd /Users/majh/Cursor/lucas
git checkout main
git checkout -b feat/couple-backend-core
```

- [ ] **Step 2: Bring over ONLY the reusable skeleton from the foundation branch**

The working tree may hold untracked `backend/` residue. Reset to a clean, known set of reusable files:

```bash
cd /Users/majh/Cursor/lucas
rm -rf backend
git checkout feat/backend-foundation -- \
  backend/.gitignore \
  backend/requirements.txt \
  backend/app/__init__.py \
  backend/app/config.py \
  backend/app/db.py \
  backend/app/main.py \
  backend/tests/__init__.py \
  backend/tests/test_health.py
```

Confirm the single-player rules did NOT come along:

```bash
ls backend/app/rules 2>/dev/null && echo "UNEXPECTED: rules present" || echo "OK: no rules dir"
```
Expected: `OK: no rules dir`

- [ ] **Step 3: Pin bcrypt to keep test output pristine**

passlib 1.7.4 + bcrypt ≥ 4.1 logs a spurious `AttributeError: module 'bcrypt' has no attribute '__about__'` (a "(trapped) error reading bcrypt version" line) on first hash — that noise would fail the pristine-output gate in later auth tasks. Pin bcrypt. Open `backend/requirements.txt` and add one line under `passlib[bcrypt]`:

```text
bcrypt==4.0.1
```

- [ ] **Step 4: Create the Python 3.13 venv with uv and install deps**

```bash
cd /Users/majh/Cursor/lucas/backend
uv venv --python 3.13 .venv
./.venv/bin/python -m ensurepip --upgrade
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python --version
```
Expected: `Python 3.13.x`

- [ ] **Step 5: Run the health test to verify the foundation works**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_health.py -v
```
Expected: `1 passed`, output pristine (no warnings).

- [ ] **Step 6: Commit**

```bash
cd /Users/majh/Cursor/lucas
git add backend/.gitignore backend/requirements.txt backend/app/__init__.py \
  backend/app/config.py backend/app/db.py backend/app/main.py \
  backend/tests/__init__.py backend/tests/test_health.py
git commit -m "chore(couple-backend): branch off foundation, reuse skeleton"
```

---

### Task 2: Shared stats rules engine (pure functions)

**Files:**
- Create: `backend/app/rules/__init__.py`
- Create: `backend/app/rules/stats.py`
- Test: `backend/tests/test_rules_stats.py`

**Interfaces:**
- Produces: `STAT_KEYS: list[str]`; `DEFAULT_STATS: dict`; `GRIEVANCE_THRESHOLD: int`; `clamp(v: float) -> int`; `apply_time_decay(stats: dict, elapsed_seconds: float) -> dict`; `needs_comfort(stats: dict) -> bool`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_rules_stats.py
from app.rules.stats import (
    STAT_KEYS,
    DEFAULT_STATS,
    GRIEVANCE_THRESHOLD,
    clamp,
    apply_time_decay,
    needs_comfort,
)


def test_stat_keys_and_defaults():
    assert STAT_KEYS == ["grievance", "dogfood", "miss", "intimacy"]
    assert DEFAULT_STATS == {"grievance": 0, "dogfood": 0, "miss": 0, "intimacy": 0}


def test_clamp_bounds_and_int():
    assert clamp(-5) == 0
    assert clamp(150) == 100
    assert clamp(42.9) == 42
    assert isinstance(clamp(42.9), int)


def test_time_decay_miss_rises_grievance_and_dogfood_fall():
    stats = {"grievance": 50, "dogfood": 30, "miss": 10, "intimacy": 60}
    out = apply_time_decay(stats, 3600.0)  # one hour
    assert out["miss"] == 14        # +4/hr
    assert out["grievance"] == 48   # -2/hr
    assert out["dogfood"] == 29     # -1/hr
    assert out["intimacy"] == 60    # never changes with time


def test_time_decay_clamps_at_zero():
    stats = {"grievance": 1, "dogfood": 0, "miss": 0, "intimacy": 0}
    out = apply_time_decay(stats, 3600.0)
    assert out["grievance"] == 0
    assert out["dogfood"] == 0


def test_time_decay_does_not_mutate_input():
    stats = {"grievance": 50, "dogfood": 30, "miss": 10, "intimacy": 60}
    apply_time_decay(stats, 3600.0)
    assert stats["miss"] == 10


def test_needs_comfort_threshold():
    assert needs_comfort({"grievance": 80, "dogfood": 0, "miss": 0, "intimacy": 0}) is True
    assert needs_comfort({"grievance": 79, "dogfood": 0, "miss": 0, "intimacy": 0}) is False
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_rules_stats.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.rules'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/rules/__init__.py
```
(empty file)

```python
# backend/app/rules/stats.py
"""纯函数：共享关系数值。无 DB / 时钟 / AI / config 依赖。"""

STAT_KEYS = ["grievance", "dogfood", "miss", "intimacy"]

DEFAULT_STATS = {"grievance": 0, "dogfood": 0, "miss": 0, "intimacy": 0}

GRIEVANCE_THRESHOLD = 80

# 每小时时间变化点数；intimacy 不在内（永不随时间变化）
TIME_DELTA_PER_HOUR = {"miss": 4.0, "grievance": -2.0, "dogfood": -1.0}


def clamp(v: float) -> int:
    return int(max(0, min(100, v)))


def apply_time_decay(stats: dict, elapsed_seconds: float) -> dict:
    hours = elapsed_seconds / 3600.0
    out = dict(stats)
    for key, rate in TIME_DELTA_PER_HOUR.items():
        out[key] = clamp(stats[key] + rate * hours)
    return out


def needs_comfort(stats: dict) -> bool:
    return stats["grievance"] >= GRIEVANCE_THRESHOLD
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_rules_stats.py -v
```
Expected: `6 passed`, output pristine.

- [ ] **Step 5: Commit**

```bash
cd /Users/majh/Cursor/lucas
git add backend/app/rules/__init__.py backend/app/rules/stats.py backend/tests/test_rules_stats.py
git commit -m "feat(rules): shared couple stats with lazy time decay"
```

---

### Task 3: Interaction action effects (pure functions)

**Files:**
- Create: `backend/app/rules/actions.py`
- Test: `backend/tests/test_rules_actions.py`

**Interfaces:**
- Consumes: `app.rules.stats.clamp`.
- Produces: `ACTION_TYPES: list[str]`; `AI_ACTIONS: set[str]`; `apply_action(stats: dict, action: str) -> tuple[dict, bool, str | None]` returning `(new_stats, needs_ai, local_reaction)`. `needs_ai` is `True` for AI actions (then `local_reaction is None`); otherwise a random local template string. Raises `ValueError` on unknown action.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_rules_actions.py
import pytest

from app.rules.actions import ACTION_TYPES, AI_ACTIONS, LOCAL_REACTIONS, apply_action


def test_action_types_cover_roast_and_sweet():
    assert set(ACTION_TYPES) == {
        "scold", "poke", "feed_dogfood", "hug", "miss_you", "apologize", "chat"
    }
    assert AI_ACTIONS == {"scold", "chat"}


def test_scold_raises_grievance_and_flags_ai():
    stats = {"grievance": 10, "dogfood": 0, "miss": 0, "intimacy": 0}
    new, needs_ai, reaction = apply_action(stats, "scold")
    assert new["grievance"] == 25   # +15
    assert needs_ai is True
    assert reaction is None


def test_feed_dogfood_local_reaction_and_stat_moves():
    stats = {"grievance": 30, "dogfood": 0, "miss": 0, "intimacy": 0}
    new, needs_ai, reaction = apply_action(stats, "feed_dogfood")
    assert new["dogfood"] == 20     # +20
    assert new["grievance"] == 20   # -10
    assert needs_ai is False
    assert reaction in LOCAL_REACTIONS["feed_dogfood"]


def test_hug_converts_miss_to_intimacy():
    stats = {"grievance": 0, "dogfood": 0, "miss": 40, "intimacy": 5}
    new, _, _ = apply_action(stats, "hug")
    assert new["miss"] == 10        # -30
    assert new["intimacy"] == 15    # +10


def test_apologize_lowers_grievance_raises_intimacy():
    stats = {"grievance": 50, "dogfood": 0, "miss": 0, "intimacy": 0}
    new, _, _ = apply_action(stats, "apologize")
    assert new["grievance"] == 25   # -25
    assert new["intimacy"] == 8     # +8


def test_chat_is_ai_no_stat_change():
    stats = {"grievance": 10, "dogfood": 10, "miss": 10, "intimacy": 10}
    new, needs_ai, reaction = apply_action(stats, "chat")
    assert new == stats
    assert needs_ai is True
    assert reaction is None


def test_poke_and_miss_you_local_reactions():
    for action in ("poke", "miss_you"):
        _, needs_ai, reaction = apply_action(
            {"grievance": 0, "dogfood": 0, "miss": 50, "intimacy": 0}, action
        )
        assert needs_ai is False
        assert reaction in LOCAL_REACTIONS[action]


def test_unknown_action_raises():
    with pytest.raises(ValueError):
        apply_action({"grievance": 0, "dogfood": 0, "miss": 0, "intimacy": 0}, "nope")


def test_apply_action_does_not_mutate_input():
    stats = {"grievance": 10, "dogfood": 0, "miss": 0, "intimacy": 0}
    apply_action(stats, "scold")
    assert stats["grievance"] == 10
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_rules_actions.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.rules.actions'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/rules/actions.py
"""纯函数：互动动作对共享数值的影响。无 DB / 时钟 / AI / config 依赖。"""

import random

from app.rules.stats import clamp

ACTION_TYPES = ["scold", "poke", "feed_dogfood", "hug", "miss_you", "apologize", "chat"]

# 需要叫 DeepSeek 的动作（骂 / 聊天）；其余走本地模板
AI_ACTIONS = {"scold", "chat"}

# 每个动作对数值的增量（未列出的键不变）
ACTION_EFFECTS = {
    "scold": {"grievance": 15},
    "poke": {"grievance": 5},
    "feed_dogfood": {"dogfood": 20, "grievance": -10},
    "hug": {"miss": -30, "intimacy": 10},
    "miss_you": {"miss": -20, "intimacy": 6},
    "apologize": {"grievance": -25, "intimacy": 8},
    "chat": {},
}

# 便宜动作的本地沙雕文案（不烧 API），随机挑一句
LOCAL_REACTIONS = {
    "poke": ["戳你咋了，我这叫亲密接触。", "再戳我可要收费了啊喂。"],
    "feed_dogfood": ["狗粮已入库，本汪原地满血复活。", "这波狗粮我先干为敬。"],
    "hug": ["抱一下，续命一整天。", "行吧行吧，勉强让你抱三秒。"],
    "miss_you": ["想我啦？我可是一直在你脑子里蹦迪。", "别想了，我这不就来了。"],
    "apologize": ["哼，看在你态度诚恳的份上，本尊原谅你了。", "算了算了，谁让我大度呢。"],
}


def apply_action(stats: dict, action: str) -> tuple[dict, bool, str | None]:
    if action not in ACTION_EFFECTS:
        raise ValueError(f"unknown action: {action}")
    out = dict(stats)
    for key, delta in ACTION_EFFECTS[action].items():
        out[key] = clamp(stats[key] + delta)
    needs_ai = action in AI_ACTIONS
    reaction = None if needs_ai else random.choice(LOCAL_REACTIONS[action])
    return out, needs_ai, reaction
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_rules_actions.py -v
```
Expected: `9 passed`, output pristine.

- [ ] **Step 5: Commit**

```bash
cd /Users/majh/Cursor/lucas
git add backend/app/rules/actions.py backend/tests/test_rules_actions.py
git commit -m "feat(rules): interaction action effects with local templates"
```

---

### Task 4: Database models & time helper

**Files:**
- Create: `backend/app/time_utils.py`
- Create: `backend/app/models.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `app.db.Base`.
- Produces: `app.time_utils.utcnow() -> datetime` (naive UTC); ORM models `User`, `Couple`, `Avatar`, `CoupleStats`, `Event` on `Base.metadata`. Key columns are fixed here and referenced by every later task — see code.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_models.py
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
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/time_utils.py
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC now — avoids datetime.utcnow() deprecation and aware/naive mixing."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
```

```python
# backend/app/models.py
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
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_models.py -v
```
Expected: `3 passed`, output pristine.

- [ ] **Step 5: Commit**

```bash
cd /Users/majh/Cursor/lucas
git add backend/app/time_utils.py backend/app/models.py backend/tests/test_models.py
git commit -m "feat(models): users, couples, avatars, shared stats, events"
```

---

### Task 5: Security utilities (password hashing + JWT)

**Files:**
- Create: `backend/app/security.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Consumes: `app.config.settings.jwt_secret`.
- Produces: `hash_password(pw: str) -> str`; `verify_password(pw: str, pw_hash: str) -> bool`; `create_access_token(sub: str, expires_minutes: int = 60 * 24 * 7) -> str`; `decode_token(token: str) -> str` (returns `sub`, raises `ValueError` on invalid/expired).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_security.py
import pytest

from app.security import hash_password, verify_password, create_access_token, decode_token


def test_hash_then_verify_roundtrip():
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h) is True
    assert verify_password("wrong", h) is False


def test_token_roundtrip_returns_subject():
    token = create_access_token(sub="42")
    assert decode_token(token) == "42"


def test_decode_rejects_garbage():
    with pytest.raises(ValueError):
        decode_token("not.a.jwt")


def test_decode_rejects_expired():
    token = create_access_token(sub="42", expires_minutes=-1)
    with pytest.raises(ValueError):
        decode_token(token)
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_security.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.security'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/security.py
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
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_security.py -v
```
Expected: `4 passed`, output pristine.

- [ ] **Step 5: Commit**

```bash
cd /Users/majh/Cursor/lucas
git add backend/app/security.py backend/tests/test_security.py
git commit -m "feat(security): bcrypt hashing and JWT access tokens"
```

---

### Task 6: Auth endpoints, current-user dependency & test harness

**Files:**
- Create: `backend/app/deps.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `app.db.get_db`, `app.models.User`, `app.security.*`, `app.time_utils.utcnow`.
- Produces: `app.deps.get_current_user(...) -> User` (FastAPI dependency, 401 on bad/missing token); routes `POST /auth/register`, `POST /auth/login`. `conftest.py` fixtures `client` (TestClient with in-memory SQLite via `StaticPool` + `get_db` override) and helper `auth_headers(client, nickname)` reused by later tasks.

- [ ] **Step 1: Write the failing tests + shared test harness**

```python
# backend/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — register tables on Base.metadata
from app.db import Base, get_db
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register(client, nickname="alice", password="pw123456"):
    return client.post("/auth/register", json={"nickname": nickname, "password": password})


def auth_headers(client, nickname="alice", password="pw123456"):
    r = register(client, nickname, password)
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

```python
# backend/tests/test_auth.py
from tests.conftest import register


def test_register_returns_token_and_user(client):
    r = register(client, "alice")
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["user"]["nickname"] == "alice"
    assert "password" not in body["user"]


def test_duplicate_nickname_rejected(client):
    register(client, "alice")
    r = register(client, "alice")
    assert r.status_code == 409


def test_login_success_and_wrong_password(client):
    register(client, "bob", "secret1")
    ok = client.post("/auth/login", json={"nickname": "bob", "password": "secret1"})
    assert ok.status_code == 200
    assert ok.json()["access_token"]
    bad = client.post("/auth/login", json={"nickname": "bob", "password": "nope"})
    assert bad.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/auth/login", json={"nickname": "ghost", "password": "x"})
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_auth.py -v
```
Expected: FAIL — 404 on `/auth/register` (route not defined) / import error for `app.deps`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import decode_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing credentials")
    try:
        sub = decode_token(creds.credentials)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    user = db.get(User, int(sub))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user
```

```python
# backend/app/routers/__init__.py
```
(empty file)

```python
# backend/app/routers/auth.py
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
```

Update `backend/app/main.py`:

```python
# backend/app/main.py
from fastapi import FastAPI

from app.routers import auth

app = FastAPI(title="AI Couple Pet Game API")

app.include_router(auth.router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_auth.py tests/test_health.py -v
```
Expected: `test_auth` 4 passed + `test_health` 1 passed, output pristine.

- [ ] **Step 5: Commit**

```bash
cd /Users/majh/Cursor/lucas
git add backend/app/deps.py backend/app/routers/__init__.py backend/app/routers/auth.py \
  backend/app/main.py backend/tests/conftest.py backend/tests/test_auth.py
git commit -m "feat(auth): register/login, JWT dependency, test harness"
```

---

### Task 7: Pairing (create / join / me) + avatar & stats bootstrap

**Files:**
- Create: `backend/app/routers/couples.py`
- Modify: `backend/app/deps.py` (add `get_active_couple`)
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_couples.py`

**Interfaces:**
- Consumes: `get_current_user`, `User`, `Couple`, `Avatar`, `CoupleStats`, `DEFAULT_STATS`, `utcnow`.
- Produces: `app.deps.get_active_couple(db, user) -> Couple | None` (couple with `status=="active"` where user is member); routes `POST /couples`, `POST /couples/join`, `GET /couples/me`. On successful join: `status="active"`, `paired_at` set, **2 mirrored `Avatar` rows** (subject=A/keeper=B and subject=B/keeper=A), **1 `CoupleStats` row** with `DEFAULT_STATS`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_couples.py
from tests.conftest import auth_headers


def _create(client, headers):
    return client.post("/couples", headers=headers)


def test_create_returns_pending_and_pair_code(client):
    h = auth_headers(client, "alice")
    r = _create(client, h)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["pair_code"]


def test_join_activates_and_bootstraps(client):
    ha = auth_headers(client, "alice")
    code = _create(client, ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    r = client.post("/couples/join", headers=hb, json={"pair_code": code})
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    # both partners now see an active couple
    me_a = client.get("/couples/me", headers=ha).json()
    me_b = client.get("/couples/me", headers=hb).json()
    assert me_a["status"] == "active"
    assert me_b["status"] == "active"
    assert me_a["couple_id"] == me_b["couple_id"]


def test_join_invalid_code(client):
    hb = auth_headers(client, "bob")
    r = client.post("/couples/join", headers=hb, json={"pair_code": "ZZZZZZ"})
    assert r.status_code == 404


def test_cannot_join_own_code(client):
    ha = auth_headers(client, "alice")
    code = _create(client, ha).json()["pair_code"]
    r = client.post("/couples/join", headers=ha, json={"pair_code": code})
    assert r.status_code == 400


def test_cannot_double_pair(client):
    ha = auth_headers(client, "alice")
    code = _create(client, ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    hc = auth_headers(client, "carol")
    r = client.post("/couples/join", headers=hc, json={"pair_code": code})
    assert r.status_code == 409  # already active


def test_creating_when_already_active_rejected(client):
    ha = auth_headers(client, "alice")
    code = _create(client, ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    r = _create(client, ha)
    assert r.status_code == 409


def test_me_when_unpaired(client):
    h = auth_headers(client, "solo")
    r = client.get("/couples/me", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "none"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_couples.py -v
```
Expected: FAIL — 404 on `/couples` (route not defined).

- [ ] **Step 3: Write the implementation**

Add to `backend/app/deps.py` (append below `get_current_user`):

```python
from sqlalchemy import or_

from app.models import Couple


def get_active_couple(db, user) -> Couple | None:
    return (
        db.query(Couple)
        .filter(
            Couple.status == "active",
            or_(Couple.user_a_id == user.id, Couple.user_b_id == user.id),
        )
        .first()
    )
```

```python
# backend/app/routers/couples.py
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
```

Update `backend/app/main.py` router imports/includes:

```python
from app.routers import auth, couples

app.include_router(auth.router)
app.include_router(couples.router)
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_couples.py -v
```
Expected: `7 passed`, output pristine.

- [ ] **Step 5: Commit**

```bash
cd /Users/majh/Cursor/lucas
git add backend/app/routers/couples.py backend/app/deps.py backend/app/main.py \
  backend/tests/test_couples.py
git commit -m "feat(couples): pairing with mirrored avatar and shared-stats bootstrap"
```

---

### Task 8: Avatar persona (捏分身: mine / pet)

**Files:**
- Create: `backend/app/routers/avatars.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_avatars.py`

**Interfaces:**
- Consumes: `get_current_user`, `get_active_couple`, `Avatar`.
- Produces: routes `GET /avatars/mine` (avatar where `subject_user_id == me` — "对方眼里的你"), `PUT /avatars/mine` (set `name`/`appearance`/`persona` — only the subject may edit), `GET /avatars/pet` (avatar where `keeper_user_id == me` — "你养的对方"). All require an active couple (else 409).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_avatars.py
from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    return ha, hb


def test_edit_mine_and_partner_sees_it_as_pet(client):
    ha, hb = _pair(client)
    r = client.put(
        "/avatars/mine",
        headers=ha,
        json={"name": "狗蛋", "appearance": {"emoji": "🐶"}, "persona": {"tone": "毒舌"}},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "狗蛋"

    # bob keeps alice's avatar as his pet
    pet = client.get("/avatars/pet", headers=hb).json()
    assert pet["name"] == "狗蛋"
    assert pet["persona"] == {"tone": "毒舌"}
    assert pet["subject_user_id"] != pet["keeper_user_id"]


def test_mine_is_the_one_i_am_subject_of(client):
    ha, hb = _pair(client)
    mine = client.get("/avatars/mine", headers=ha).json()
    pet = client.get("/avatars/pet", headers=ha).json()
    assert mine["id"] != pet["id"]
    assert mine["subject_user_id"] == pet["keeper_user_id"]  # both are alice's id


def test_requires_active_couple(client):
    h = auth_headers(client, "solo")
    assert client.get("/avatars/mine", headers=h).status_code == 409
    assert client.put("/avatars/mine", headers=h, json={"name": "x"}).status_code == 409
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_avatars.py -v
```
Expected: FAIL — 404 on `/avatars/mine`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/routers/avatars.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.models import Avatar, User

router = APIRouter(prefix="/avatars", tags=["avatars"])


class AvatarUpdate(BaseModel):
    name: str | None = None
    appearance: dict | None = None
    persona: dict | None = None


def _avatar_out(av: Avatar) -> dict:
    return {
        "id": av.id,
        "couple_id": av.couple_id,
        "subject_user_id": av.subject_user_id,
        "keeper_user_id": av.keeper_user_id,
        "name": av.name,
        "appearance": av.appearance,
        "persona": av.persona,
    }


def _require_couple(db: Session, user: User):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")
    return couple


@router.get("/mine")
def get_mine(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    couple = _require_couple(db, user)
    av = (
        db.query(Avatar)
        .filter(Avatar.couple_id == couple.id, Avatar.subject_user_id == user.id)
        .first()
    )
    return _avatar_out(av)


@router.put("/mine")
def update_mine(
    body: AvatarUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    couple = _require_couple(db, user)
    av = (
        db.query(Avatar)
        .filter(Avatar.couple_id == couple.id, Avatar.subject_user_id == user.id)
        .first()
    )
    if body.name is not None:
        av.name = body.name
    if body.appearance is not None:
        av.appearance = body.appearance
    if body.persona is not None:
        av.persona = body.persona
    db.commit()
    db.refresh(av)
    return _avatar_out(av)


@router.get("/pet")
def get_pet(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    couple = _require_couple(db, user)
    av = (
        db.query(Avatar)
        .filter(Avatar.couple_id == couple.id, Avatar.keeper_user_id == user.id)
        .first()
    )
    return _avatar_out(av)
```

Update `backend/app/main.py`:

```python
from app.routers import auth, avatars, couples

app.include_router(auth.router)
app.include_router(couples.router)
app.include_router(avatars.router)
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_avatars.py -v
```
Expected: `3 passed`, output pristine.

- [ ] **Step 5: Commit**

```bash
cd /Users/majh/Cursor/lucas
git add backend/app/routers/avatars.py backend/app/main.py backend/tests/test_avatars.py
git commit -m "feat(avatars): persona editing for mine and pet views"
```

---

### Task 9: DeepSeek stub + daily AI quota

**Files:**
- Create: `backend/app/ai/__init__.py`
- Create: `backend/app/ai/deepseek.py`
- Create: `backend/app/ai/quota.py`
- Test: `backend/tests/test_ai.py`

**Interfaces:**
- Consumes: `settings.daily_chat_cap`, `User`, `utcnow`.
- Produces: `app.ai.deepseek.generate_reaction(persona: dict, stats: dict, action_type: str, content: str, memory_summary: str = "") -> str` (deterministic stub — no network, no randomness); `app.ai.quota.consume_ai_quota(user: User, db) -> bool` (resets `ai_count` when `ai_count_date` != today UTC; returns `False` when at/over cap, else increments and returns `True`; caller commits).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_ai.py
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
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_ai.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ai'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/ai/__init__.py
```
(empty file)

```python
# backend/app/ai/deepseek.py
"""DeepSeek 分身反应。本版为确定性 Stub，不联网；真实实现后置替换。"""


def generate_reaction(
    persona: dict,
    stats: dict,
    action_type: str,
    content: str,
    memory_summary: str = "",
) -> str:
    tone = persona.get("tone", "沙雕")
    said = content.strip() if content else ""
    tail = f"「{said}」" if said else ""
    return f"[{tone}分身] 收到你的 {action_type}{tail}，哼，本尊可不吃这套~"
```

```python
# backend/app/ai/quota.py
from app.config import settings
from app.models import User
from app.time_utils import utcnow


def consume_ai_quota(user: User, db) -> bool:
    """Reset per UTC day; return False at/over cap, else increment and return True."""
    today = utcnow().date()
    if user.ai_count_date != today:
        user.ai_count = 0
        user.ai_count_date = today
    if user.ai_count >= settings.daily_chat_cap:
        db.add(user)
        db.commit()
        return False
    user.ai_count += 1
    db.add(user)
    db.commit()
    return True
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_ai.py -v
```
Expected: `3 passed`, output pristine.

- [ ] **Step 5: Commit**

```bash
cd /Users/majh/Cursor/lucas
git add backend/app/ai/__init__.py backend/app/ai/deepseek.py backend/app/ai/quota.py \
  backend/tests/test_ai.py
git commit -m "feat(ai): deterministic DeepSeek stub and daily AI quota"
```

---

### Task 10: Interaction endpoint (unified action flow + idempotency)

**Files:**
- Create: `backend/app/routers/actions.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_actions.py`

**Interfaces:**
- Consumes: `get_current_user`, `get_active_couple`, `Avatar`, `CoupleStats`, `Event`, `apply_time_decay`, `apply_action`, `ACTION_TYPES`, `generate_reaction`, `consume_ai_quota`, `utcnow`.
- Produces: route `POST /actions` with body `{action_type, content?, client_key}` → `{"events": [EventOut...], "stats": {...}}`. Flow: validate active couple + known action + `client_key` present; **idempotency** — an existing event with `(couple_id, client_key)` returns its bundle unchanged; else within one transaction: realize time decay onto stored stats, `apply_action`, persist `couple_stats` (new `stats` + `stats_updated_at=utcnow()`), insert an `action` event (`actor=me`, carries `client_key`) and an `ai_reaction` child event (`actor=None`, `parent=action.id`) whose content is the DeepSeek stub for AI actions (falling back to a local template if over quota) or the local template otherwise. `EventOut = {id, couple_id, actor_user_id, kind, action_type, content, parent_event_id, created_at}`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_actions.py
from app.rules.actions import LOCAL_REACTIONS
from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    # alice sets her persona so the stub reaction is in-persona
    client.put("/avatars/mine", headers=ha, json={"persona": {"tone": "毒舌"}})
    return ha, hb


def _act(client, headers, action_type, key, content=""):
    return client.post(
        "/actions",
        headers=headers,
        json={"action_type": action_type, "content": content, "client_key": key},
    )


def test_scold_produces_action_and_ai_reaction(client):
    ha, hb = _pair(client)
    # bob scolds his pet (alice's avatar, persona 毒舌)
    r = _act(client, hb, "scold", "k1", "大猪蹄子")
    assert r.status_code == 200
    body = r.json()
    kinds = [e["kind"] for e in body["events"]]
    assert "action" in kinds and "ai_reaction" in kinds
    reaction = next(e for e in body["events"] if e["kind"] == "ai_reaction")
    assert reaction["parent_event_id"] is not None
    assert "毒舌" in reaction["content"]
    assert body["stats"]["grievance"] == 15


def test_cheap_action_uses_local_template(client):
    ha, hb = _pair(client)
    r = _act(client, hb, "feed_dogfood", "k1")
    reaction = next(e for e in r.json()["events"] if e["kind"] == "ai_reaction")
    assert reaction["content"] in LOCAL_REACTIONS["feed_dogfood"]
    assert r.json()["stats"]["dogfood"] == 20


def test_idempotent_replay_returns_same_events(client):
    ha, hb = _pair(client)
    first = _act(client, hb, "scold", "same-key", "x").json()
    second = _act(client, hb, "scold", "same-key", "x").json()
    assert [e["id"] for e in first["events"]] == [e["id"] for e in second["events"]]
    # grievance did not double-apply
    assert second["stats"]["grievance"] == 15


def test_unknown_action_rejected(client):
    ha, hb = _pair(client)
    r = _act(client, hb, "nope", "k1")
    assert r.status_code == 422


def test_requires_active_couple(client):
    h = auth_headers(client, "solo")
    r = _act(client, h, "scold", "k1", "x")
    assert r.status_code == 409


def test_over_quota_falls_back_to_local(client, monkeypatch):
    ha, hb = _pair(client)
    import app.routers.actions as actions_mod

    monkeypatch.setattr(actions_mod, "consume_ai_quota", lambda user, db: False)
    r = _act(client, hb, "scold", "k1", "大猪蹄子")
    assert r.status_code == 200  # never errors on quota exhaustion
    reaction = next(e for e in r.json()["events"] if e["kind"] == "ai_reaction")
    assert reaction["content"]  # a fallback line, not empty
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_actions.py -v
```
Expected: FAIL — 404 on `/actions`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/routers/actions.py
import random

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.deepseek import generate_reaction
from app.ai.quota import consume_ai_quota
from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.models import Avatar, CoupleStats, Event, User
from app.rules.actions import ACTION_TYPES, LOCAL_REACTIONS, apply_action
from app.rules.stats import apply_time_decay
from app.time_utils import utcnow

router = APIRouter(tags=["actions"])

# 兜底本地文案（AI 动作超额度时用）
_AI_FALLBACK = ["（分身正在充电，先甩你个白眼~）", "（本尊今日营业已满，明天再怼你）"]


class ActionIn(BaseModel):
    action_type: str
    content: str = ""
    client_key: str


def event_out(ev: Event) -> dict:
    return {
        "id": ev.id,
        "couple_id": ev.couple_id,
        "actor_user_id": ev.actor_user_id,
        "kind": ev.kind,
        "action_type": ev.action_type,
        "content": ev.content,
        "parent_event_id": ev.parent_event_id,
        "created_at": ev.created_at.isoformat(),
    }


def _bundle(db: Session, couple_id: int, action_event: Event, stats: dict) -> dict:
    children = (
        db.query(Event)
        .filter(Event.parent_event_id == action_event.id)
        .order_by(Event.id)
        .all()
    )
    events = [action_event] + children
    return {"events": [event_out(e) for e in events], "stats": stats}


@router.post("/actions")
def do_action(
    body: ActionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.action_type not in ACTION_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "unknown action")
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")

    # 幂等：同一 (couple, client_key) 直接返回既有 bundle
    existing = (
        db.query(Event)
        .filter(
            Event.couple_id == couple.id,
            Event.client_key == body.client_key,
            Event.kind == "action",
        )
        .first()
    )
    if existing is not None:
        cs = db.get(CoupleStats, couple.id)
        return _bundle(db, couple.id, existing, cs.stats)

    pet = (
        db.query(Avatar)
        .filter(Avatar.couple_id == couple.id, Avatar.keeper_user_id == user.id)
        .first()
    )
    cs = db.get(CoupleStats, couple.id)

    now = utcnow()
    elapsed = (now - cs.stats_updated_at).total_seconds()
    decayed = apply_time_decay(cs.stats, elapsed)
    new_stats, needs_ai, local_reaction = apply_action(decayed, body.action_type)

    if needs_ai:
        if consume_ai_quota(user, db):
            reaction_text = generate_reaction(
                pet.persona, new_stats, body.action_type, body.content, pet.memory_summary
            )
        else:
            reaction_text = random.choice(_AI_FALLBACK)
    else:
        reaction_text = local_reaction

    cs.stats = new_stats
    cs.stats_updated_at = now
    action_event = Event(
        couple_id=couple.id,
        actor_user_id=user.id,
        kind="action",
        action_type=body.action_type,
        content=body.content,
        client_key=body.client_key,
    )
    db.add(action_event)
    db.flush()  # assign action_event.id for the child
    reaction_event = Event(
        couple_id=couple.id,
        actor_user_id=None,
        kind="ai_reaction",
        action_type=body.action_type,
        content=reaction_text,
        parent_event_id=action_event.id,
    )
    db.add(reaction_event)
    db.commit()
    db.refresh(action_event)
    return _bundle(db, couple.id, action_event, new_stats)
```

Update `backend/app/main.py`:

```python
from app.routers import actions, auth, avatars, couples

app.include_router(auth.router)
app.include_router(couples.router)
app.include_router(avatars.router)
app.include_router(actions.router)
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_actions.py -v
```
Expected: `6 passed`, output pristine.

- [ ] **Step 5: Commit**

```bash
cd /Users/majh/Cursor/lucas
git add backend/app/routers/actions.py backend/app/main.py backend/tests/test_actions.py
git commit -m "feat(actions): unified interaction flow with idempotency"
```

---

### Task 11: Real response (本尊附身)

**Files:**
- Create: `backend/app/routers/events.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_real_response.py`

**Interfaces:**
- Consumes: `get_current_user`, `get_active_couple`, `Event`, `event_out` (from `app.routers.actions`), `utcnow`.
- Produces: route `POST /events/{event_id}/respond` with body `{content, client_key}` → the created `real_response` `EventOut`. Permission: the parent event must be a `kind=="action"` event in the caller's active couple whose `actor_user_id != caller` (i.e. the caller is the partner / 本尊). Idempotent on `(couple_id, client_key)`. Sets `parent_event_id = event_id`, `actor_user_id = caller`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_real_response.py
from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    return ha, hb


def _scold(client, headers, key="k1"):
    return client.post(
        "/actions",
        headers=headers,
        json={"action_type": "scold", "content": "大猪蹄子", "client_key": key},
    ).json()


def test_subject_can_respond_to_partner_action(client):
    ha, hb = _pair(client)
    bundle = _scold(client, hb)  # bob acts on alice's avatar; alice is the subject
    action_id = next(e["id"] for e in bundle["events"] if e["kind"] == "action")
    r = client.post(
        f"/events/{action_id}/respond",
        headers=ha,
        json={"content": "你才是猪蹄子", "client_key": "resp1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "real_response"
    assert body["parent_event_id"] == action_id


def test_actor_cannot_respond_to_own_action(client):
    ha, hb = _pair(client)
    bundle = _scold(client, hb)
    action_id = next(e["id"] for e in bundle["events"] if e["kind"] == "action")
    r = client.post(
        f"/events/{action_id}/respond",
        headers=hb,  # bob was the actor
        json={"content": "自问自答", "client_key": "resp1"},
    )
    assert r.status_code == 403


def test_cannot_respond_to_event_in_other_couple(client):
    ha, hb = _pair(client)
    bundle = _scold(client, hb)
    action_id = next(e["id"] for e in bundle["events"] if e["kind"] == "action")
    outsider = auth_headers(client, "carol")
    r = client.post(
        f"/events/{action_id}/respond",
        headers=outsider,
        json={"content": "路过", "client_key": "resp1"},
    )
    assert r.status_code in (403, 404)


def test_respond_is_idempotent(client):
    ha, hb = _pair(client)
    bundle = _scold(client, hb)
    action_id = next(e["id"] for e in bundle["events"] if e["kind"] == "action")
    first = client.post(
        f"/events/{action_id}/respond", headers=ha,
        json={"content": "x", "client_key": "resp1"},
    ).json()
    second = client.post(
        f"/events/{action_id}/respond", headers=ha,
        json={"content": "x", "client_key": "resp1"},
    ).json()
    assert first["id"] == second["id"]
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_real_response.py -v
```
Expected: FAIL — 404 on `/events/{id}/respond`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/routers/events.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.models import Event, User
from app.routers.actions import event_out

router = APIRouter(prefix="/events", tags=["events"])


class RespondIn(BaseModel):
    content: str = ""
    client_key: str


@router.post("/{event_id}/respond")
def respond(
    event_id: int,
    body: RespondIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")
    parent = db.get(Event, event_id)
    if parent is None or parent.couple_id != couple.id or parent.kind != "action":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "action event not found")
    if parent.actor_user_id == user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot respond to your own action")

    existing = (
        db.query(Event)
        .filter(
            Event.couple_id == couple.id,
            Event.client_key == body.client_key,
            Event.kind == "real_response",
        )
        .first()
    )
    if existing is not None:
        return event_out(existing)

    ev = Event(
        couple_id=couple.id,
        actor_user_id=user.id,
        kind="real_response",
        content=body.content,
        parent_event_id=parent.id,
        client_key=body.client_key,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return event_out(ev)
```

Update `backend/app/main.py`:

```python
from app.routers import actions, auth, avatars, couples, events

app.include_router(auth.router)
app.include_router(couples.router)
app.include_router(avatars.router)
app.include_router(actions.router)
app.include_router(events.router)
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_real_response.py -v
```
Expected: `4 passed`, output pristine.

- [ ] **Step 5: Commit**

```bash
cd /Users/majh/Cursor/lucas
git add backend/app/routers/events.py backend/app/main.py backend/tests/test_real_response.py
git commit -m "feat(events): real-response (本尊附身) with permission and idempotency"
```

---

### Task 12: Polling feed (shared timeline + live stats)

**Files:**
- Modify: `backend/app/routers/events.py` (add `GET /events`)
- Test: `backend/tests/test_feed.py`

**Interfaces:**
- Consumes: `get_active_couple`, `Event`, `CoupleStats`, `apply_time_decay`, `event_out`, `utcnow`.
- Produces: route `GET /events?since=<int>` → `{"events": [EventOut...], "stats": {...}}`. Returns only events in the caller's active couple with `id > since`, ordered by `id` ascending. `stats` is the shared pool **time-decayed on read but not persisted** (decay is realized only on the next write). Default `since=0`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_feed.py
from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    return ha, hb


def _scold(client, headers, key):
    return client.post(
        "/actions",
        headers=headers,
        json={"action_type": "scold", "content": "x", "client_key": key},
    ).json()


def test_feed_is_shared_and_cursor_advances(client):
    ha, hb = _pair(client)
    _scold(client, hb, "k1")

    # alice (partner) polls from 0 and sees bob's action + ai_reaction
    full = client.get("/events?since=0", headers=ha).json()
    assert len(full["events"]) == 2
    last_id = full["events"][-1]["id"]

    # nothing new since the last id
    empty = client.get(f"/events?since={last_id}", headers=ha).json()
    assert empty["events"] == []

    # a new action shows up only above the cursor
    _scold(client, hb, "k2")
    delta = client.get(f"/events?since={last_id}", headers=ha).json()
    assert all(e["id"] > last_id for e in delta["events"])
    assert len(delta["events"]) == 2


def test_feed_includes_stats(client):
    ha, hb = _pair(client)
    _scold(client, hb, "k1")
    feed = client.get("/events?since=0", headers=hb).json()
    assert feed["stats"]["grievance"] == 15


def test_feed_requires_active_couple(client):
    h = auth_headers(client, "solo")
    assert client.get("/events?since=0", headers=h).status_code == 409


def test_feed_scoped_to_own_couple(client):
    ha, hb = _pair(client)
    _scold(client, hb, "k1")
    # a second, unrelated couple
    hc = auth_headers(client, "carol")
    code = client.post("/couples", headers=hc).json()["pair_code"]
    hd = auth_headers(client, "dave")
    client.post("/couples/join", headers=hd, json={"pair_code": code})
    feed = client.get("/events?since=0", headers=hc).json()
    assert feed["events"] == []  # carol sees nothing from alice+bob
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_feed.py -v
```
Expected: FAIL — `GET /events` returns 405/404 (only the respond route exists).

- [ ] **Step 3: Write the implementation**

Add to `backend/app/routers/events.py` (imports at top, route below `respond`):

```python
from app.models import CoupleStats
from app.rules.stats import apply_time_decay
from app.time_utils import utcnow


@router.get("")
def feed(
    since: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")
    events = (
        db.query(Event)
        .filter(Event.couple_id == couple.id, Event.id > since)
        .order_by(Event.id)
        .all()
    )
    cs = db.get(CoupleStats, couple.id)
    elapsed = (utcnow() - cs.stats_updated_at).total_seconds()
    live_stats = apply_time_decay(cs.stats, elapsed)  # 只读，不落库
    return {"events": [event_out(e) for e in events], "stats": live_stats}
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_feed.py -v
```
Expected: `4 passed`, output pristine.

- [ ] **Step 5: Commit**

```bash
cd /Users/majh/Cursor/lucas
git add backend/app/routers/events.py backend/tests/test_feed.py
git commit -m "feat(events): polling feed with shared timeline and live stats"
```

---

### Task 13: Grievance safety valve (system narration)

**Files:**
- Modify: `backend/app/routers/actions.py` (append `system` event when `needs_comfort`)
- Test: `backend/tests/test_safety_valve.py`

**Interfaces:**
- Consumes: `needs_comfort` (from `app.rules.stats`).
- Produces: within `POST /actions`, after persisting stats, if `needs_comfort(new_stats)` is `True`, append one `system` event (`actor=None`, `parent=action.id`, `kind="system"`) carrying a fixed "该哄了" narration. It appears in the returned bundle and in the feed. Non-triggering actions add no system event.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_safety_valve.py
from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    return ha, hb


def _scold(client, headers, key):
    return client.post(
        "/actions",
        headers=headers,
        json={"action_type": "scold", "content": "x", "client_key": key},
    ).json()


def test_system_narration_appears_when_grievance_maxes(client):
    ha, hb = _pair(client)
    bundle = {}
    # scold +15 each; 6 scolds → 90 >= threshold 80 (fast, minimal time decay)
    for i in range(6):
        bundle = _scold(client, hb, f"k{i}")
    kinds = [e["kind"] for e in bundle["events"]]
    assert "system" in kinds
    system_ev = next(e for e in bundle["events"] if e["kind"] == "system")
    assert system_ev["content"]  # a comfort nudge, not empty
    assert system_ev["parent_event_id"] is not None


def test_no_system_narration_below_threshold(client):
    ha, hb = _pair(client)
    bundle = _scold(client, hb, "k0")  # grievance 15, well below 80
    kinds = [e["kind"] for e in bundle["events"]]
    assert "system" not in kinds
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_safety_valve.py -v
```
Expected: FAIL — no `system` event in the bundle (feature not implemented).

- [ ] **Step 3: Write the implementation**

In `backend/app/routers/actions.py`, add the import and a constant near the top:

```python
from app.rules.stats import apply_time_decay, needs_comfort
```

```python
_COMFORT_NARRATION = "⚠️ 委屈值爆表啦——TA 在角落画圈圈，快去哄哄（喂口狗粮/抱一个/道个歉）~"
```

Then, in `do_action`, after `db.add(reaction_event)` and before `db.commit()`, insert:

```python
    if needs_comfort(new_stats):
        db.add(
            Event(
                couple_id=couple.id,
                actor_user_id=None,
                kind="system",
                content=_COMFORT_NARRATION,
                parent_event_id=action_event.id,
            )
        )
```

(The existing `_bundle` already collects all children of the action event, so the `system` event is returned automatically.)

- [ ] **Step 4: Run to verify it passes**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest tests/test_safety_valve.py -v
```
Expected: `2 passed`, output pristine.

- [ ] **Step 5: Run the full suite to confirm nothing regressed**

```bash
cd /Users/majh/Cursor/lucas/backend
./.venv/bin/python -m pytest -v
```
Expected: all tests pass (health, rules_stats, rules_actions, models, security, auth, couples, avatars, ai, actions, real_response, feed, safety_valve), output pristine.

- [ ] **Step 6: Commit**

```bash
cd /Users/majh/Cursor/lucas
git add backend/app/routers/actions.py backend/tests/test_safety_valve.py
git commit -m "feat(actions): grievance safety-valve system narration"
```

---

## Notes for the Frontend Plan (out of scope here)

These backend endpoints are the contract the React app (a later plan) will consume:
- `POST /auth/register`, `POST /auth/login` → `{access_token, user}`
- `POST /couples`, `POST /couples/join`, `GET /couples/me`
- `GET /avatars/mine`, `PUT /avatars/mine`, `GET /avatars/pet`
- `POST /actions` (unified interaction), `POST /events/{id}/respond`, `GET /events?since=<cursor>`

Real DeepSeek calls, Web Push, and SSE remain deferred per the spec's non-goals; the stub in `app/ai/deepseek.py` is the single swap point for real AI.
