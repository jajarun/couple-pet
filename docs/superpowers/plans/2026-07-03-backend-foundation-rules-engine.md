# 计划 1 · 后端地基 + 规则引擎 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭起 FastAPI + MySQL 后端骨架，实现账号(JWT)、数据模型、以及全部纯逻辑规则引擎（数值懒计算衰减、照顾动作、经济、进化触发、孵蛋/毕业），DeepSeek 用可替换的 Stub 顶位，全程 pytest 可验证。

**Architecture:** 前端纯展示、后端唯一真相源。规则引擎写成**无副作用的纯函数**（只吃/吐 Python dict，不碰 DB、不碰时钟、不碰 AI），单独单元测试；DB/API 层薄薄地调用规则引擎并落库。AI 通过 `AIProvider` 协议注入，本计划用 `StubAIProvider` 返回固定文案，计划 2 无缝替换成真 DeepSeek。数值随时间衰减用**时间戳懒计算**，不跑后台定时任务。

**Tech Stack:** Python 3.11+ · FastAPI · SQLAlchemy 2.0 · Pydantic v2 / pydantic-settings · python-jose[cryptography] (JWT) · passlib[bcrypt] · PyMySQL (生产) / SQLite in-memory (测试) · pytest · httpx (TestClient)

## Global Constraints

- **后端是唯一真相源**；前端不写任何游戏规则。
- **数值随时间衰减一律懒计算**（读取时按 `stats_updated_at` 与当前时间的差现算），**禁止后台定时任务**。
- **规则引擎纯函数**：不导入 DB、不调用 `datetime.now()`、不调用 AI；时间差以 `elapsed_seconds: float` 参数传入。
- **效果结算走数据库事务**：一次请求内对数值/经济/记录的修改要么全成功要么全回滚。
- **发奖励的操作幂等**：孵蛋、领取任务奖励重复调用不得双倍发放。
- **DeepSeek 只在后端**，本计划一律用 `StubAIProvider`；接口签名一旦定下，计划 2 必须能原样替换。
- **每用户每日 AI 聊天软上限**默认 `50`（`settings.daily_chat_cap`），到顶不调用 AI、返回人设卖萌文案。
- **stats 字典固定 5 个键**：`satiety` `mood` `cleanliness` `energy` `affection`，取值恒在 `0–100`。
- **测试禁止调用真实网络/真实 DeepSeek**。

---

### Task 1: 项目骨架 + 配置 + DB 会话 + 健康检查

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.gitignore`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/db.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces:
  - `app.config.settings`（属性：`database_url: str`、`jwt_secret: str`、`daily_chat_cap: int`、`deepseek_api_key: str`）
  - `app.db.Base`（SQLAlchemy DeclarativeBase）、`app.db.engine`、`app.db.SessionLocal`、`app.db.get_db()`（FastAPI 依赖，`yield` 一个 `Session`）
  - `app.main.app`（FastAPI 实例）

- [ ] **Step 1: 写依赖清单与忽略文件**

`backend/requirements.txt`:
```
fastapi
uvicorn[standard]
sqlalchemy>=2.0
pydantic>=2
pydantic-settings
python-jose[cryptography]
passlib[bcrypt]
pymysql
python-multipart
pytest
httpx
```

`backend/.gitignore`:
```
__pycache__/
*.pyc
.venv/
.env
dev.db
```

`backend/app/__init__.py` 和 `backend/tests/__init__.py`：空文件。

- [ ] **Step 2: 安装依赖（在 backend 目录建虚拟环境）**

Run:
```bash
cd backend && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```
Expected: 安装成功，无报错。之后所有 `pytest` / `python` 命令都用 `./.venv/bin/...`（或先激活 venv）。

- [ ] **Step 3: 写配置**

`backend/app/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 生产用 MySQL，例如 mysql+pymysql://user:pass@host:3306/petgame
    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = "dev-secret-change-me"
    daily_chat_cap: int = 50
    deepseek_api_key: str = ""


settings = Settings()
```

- [ ] **Step 4: 写 DB 会话层**

`backend/app/db.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 5: 写 FastAPI 入口 + 健康检查**

`backend/app/main.py`:
```python
from fastapi import FastAPI

app = FastAPI(title="AI Pet Game API")


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: 写健康检查测试**

`backend/tests/test_health.py`:
```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 7: 运行测试确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_health.py -v`
Expected: PASS（1 passed）。

- [ ] **Step 8: 提交**

```bash
git add backend/
git commit -m "feat(backend): scaffold FastAPI app, config, db session, health check"
```

---

### Task 2: 规则引擎 — 数值衰减（纯函数）

**Files:**
- Create: `backend/app/rules/__init__.py`
- Create: `backend/app/rules/stats.py`
- Test: `backend/tests/test_rules_stats.py`

**Interfaces:**
- Produces:
  - `app.rules.stats.STAT_KEYS: list[str]` = `["satiety","mood","cleanliness","energy","affection"]`
  - `app.rules.stats.DEFAULT_STATS: dict` — 新宠初始数值
  - `app.rules.stats.clamp(v: float) -> int` — 夹到 0..100 并取整
  - `app.rules.stats.apply_decay(stats: dict, elapsed_seconds: float) -> dict` — 返回衰减后的**新 dict**（不改入参）；`affection` 永不衰减

- [ ] **Step 1: 写失败测试**

`backend/tests/test_rules_stats.py`:
```python
from app.rules.stats import DEFAULT_STATS, apply_decay, clamp


def test_clamp_bounds():
    assert clamp(-10) == 0
    assert clamp(150) == 100
    assert clamp(42.7) == 42


def test_decay_reduces_over_one_hour():
    stats = {"satiety": 80, "mood": 80, "cleanliness": 80, "energy": 80, "affection": 50}
    out = apply_decay(stats, elapsed_seconds=3600)
    assert out["satiety"] < 80
    assert out["cleanliness"] < 80
    assert out["energy"] < 80
    # affection 永不衰减
    assert out["affection"] == 50
    # 纯函数：不改入参
    assert stats["satiety"] == 80


def test_decay_never_below_zero():
    stats = {"satiety": 1, "mood": 1, "cleanliness": 1, "energy": 1, "affection": 0}
    out = apply_decay(stats, elapsed_seconds=3600 * 100)
    assert out["satiety"] == 0
    assert out["energy"] == 0


def test_zero_elapsed_no_change():
    stats = dict(DEFAULT_STATS)
    assert apply_decay(stats, elapsed_seconds=0) == DEFAULT_STATS
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_rules_stats.py -v`
Expected: FAIL（`ModuleNotFoundError: app.rules.stats`）。

- [ ] **Step 3: 写实现**

`backend/app/rules/__init__.py`：空文件。

`backend/app/rules/stats.py`:
```python
STAT_KEYS = ["satiety", "mood", "cleanliness", "energy", "affection"]

DEFAULT_STATS = {
    "satiety": 70,
    "mood": 70,
    "cleanliness": 70,
    "energy": 70,
    "affection": 0,
}

# 每小时衰减点数；affection 不在内（永不衰减）
DECAY_PER_HOUR = {
    "satiety": 8.0,
    "cleanliness": 5.0,
    "energy": 6.0,
    "mood": 3.0,
}


def clamp(v: float) -> int:
    return int(max(0, min(100, v)))


def apply_decay(stats: dict, elapsed_seconds: float) -> dict:
    hours = elapsed_seconds / 3600.0
    out = dict(stats)
    for key, rate in DECAY_PER_HOUR.items():
        out[key] = clamp(stats[key] - rate * hours)
    return out
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_rules_stats.py -v`
Expected: PASS（4 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/rules/ backend/tests/test_rules_stats.py
git commit -m "feat(rules): stats decay pure functions with lazy elapsed-time model"
```

---

### Task 3: 规则引擎 — 照顾动作（纯函数）

**Files:**
- Create: `backend/app/rules/care.py`
- Test: `backend/tests/test_rules_care.py`

**Interfaces:**
- Consumes: `app.rules.stats.clamp`
- Produces:
  - `app.rules.care.CARE_ACTIONS: list[str]` = `["feed","play","wash","rest"]`
  - `app.rules.care.CARE_REACTIONS: dict[str, list[str]]` — 每个动作的本地模板文案（不烧 AI）
  - `app.rules.care.apply_care(stats: dict, action: str) -> tuple[dict, str, str]` — 返回 `(new_stats, reaction_text, influence_tag)`；未知动作抛 `ValueError`；每次照顾 `affection +2`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_rules_care.py`:
```python
import pytest

from app.rules.care import CARE_REACTIONS, apply_care


def test_feed_raises_satiety_and_affection():
    stats = {"satiety": 50, "mood": 50, "cleanliness": 50, "energy": 50, "affection": 10}
    new_stats, reaction, tag = apply_care(stats, "feed")
    assert new_stats["satiety"] > 50
    assert new_stats["affection"] == 12
    assert reaction in CARE_REACTIONS["feed"]
    assert tag == "fed"
    assert stats["satiety"] == 50  # 不改入参


def test_play_costs_energy_boosts_mood():
    stats = {"satiety": 50, "mood": 50, "cleanliness": 50, "energy": 50, "affection": 0}
    new_stats, _, _ = apply_care(stats, "play")
    assert new_stats["mood"] > 50
    assert new_stats["energy"] < 50


def test_unknown_action_raises():
    stats = {"satiety": 50, "mood": 50, "cleanliness": 50, "energy": 50, "affection": 0}
    with pytest.raises(ValueError):
        apply_care(stats, "teleport")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_rules_care.py -v`
Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 写实现**

`backend/app/rules/care.py`:
```python
import random

from app.rules.stats import clamp

CARE_ACTIONS = ["feed", "play", "wash", "rest"]

# 每个动作对数值的增量（affection 单独 +2）
CARE_EFFECTS = {
    "feed": {"satiety": 30, "mood": 5},
    "play": {"mood": 25, "energy": -15},
    "wash": {"cleanliness": 40, "mood": -5},
    "rest": {"energy": 35},
}

# 影响进化的标签
CARE_TAGS = {"feed": "fed", "play": "played", "wash": "washed", "rest": "rested"}

# 本地模板文案（不烧 AI），生产随机挑一句
CARE_REACTIONS = {
    "feed": ["吨吨吨……你是不是想把我养成球？", "这就是传说中的嗟来之食？真香。"],
    "play": ["再玩！再玩！我还没输！", "你终于想起来我不是摆件了。"],
    "wash": ["放开我！我天生自带包浆！", "洗就洗，别搓我肚皮那块。"],
    "rest": ["Zzz……别吵，我在梦里当大老板。", "眯一会儿，做梦都比你有前途。"],
}


def apply_care(stats: dict, action: str) -> tuple[dict, str, str]:
    if action not in CARE_EFFECTS:
        raise ValueError(f"unknown care action: {action}")
    out = dict(stats)
    for key, delta in CARE_EFFECTS[action].items():
        out[key] = clamp(stats[key] + delta)
    out["affection"] = clamp(stats["affection"] + 2)
    reaction = random.choice(CARE_REACTIONS[action])
    return out, reaction, CARE_TAGS[action]
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_rules_care.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/rules/care.py backend/tests/test_rules_care.py
git commit -m "feat(rules): care actions with local reaction templates"
```

---

### Task 4: 规则引擎 — 经济（纯函数）

**Files:**
- Create: `backend/app/rules/economy.py`
- Test: `backend/tests/test_rules_economy.py`

**Interfaces:**
- Produces:
  - `app.rules.economy.EGG_PRICE: int` = `100`
  - `app.rules.economy.normalize_reward(reward: dict) -> dict` — 补全为 `{"coins": int>=0, "egg": bool}`，非法值夹正
  - `app.rules.economy.can_afford_egg(coins: int) -> bool`
  - `app.rules.economy.spend_for_egg(coins: int) -> int` — 返回扣费后余额；不够抛 `ValueError`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_rules_economy.py`:
```python
import pytest

from app.rules.economy import (
    EGG_PRICE,
    can_afford_egg,
    normalize_reward,
    spend_for_egg,
)


def test_normalize_reward_fills_defaults():
    assert normalize_reward({}) == {"coins": 0, "egg": False}
    assert normalize_reward({"coins": 30}) == {"coins": 30, "egg": False}
    assert normalize_reward({"coins": -5, "egg": True}) == {"coins": 0, "egg": True}


def test_afford_and_spend():
    assert can_afford_egg(EGG_PRICE) is True
    assert can_afford_egg(EGG_PRICE - 1) is False
    assert spend_for_egg(EGG_PRICE + 20) == 20


def test_spend_insufficient_raises():
    with pytest.raises(ValueError):
        spend_for_egg(EGG_PRICE - 1)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_rules_economy.py -v`
Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 写实现**

`backend/app/rules/economy.py`:
```python
EGG_PRICE = 100


def normalize_reward(reward: dict) -> dict:
    coins = reward.get("coins", 0)
    if not isinstance(coins, int) or coins < 0:
        coins = 0
    return {"coins": coins, "egg": bool(reward.get("egg", False))}


def can_afford_egg(coins: int) -> bool:
    return coins >= EGG_PRICE


def spend_for_egg(coins: int) -> int:
    if not can_afford_egg(coins):
        raise ValueError("not enough coins for egg")
    return coins - EGG_PRICE
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_rules_economy.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/rules/economy.py backend/tests/test_rules_economy.py
git commit -m "feat(rules): economy — reward normalization and egg pricing"
```

---

### Task 5: 规则引擎 — 进化影响与触发（纯函数）

**Files:**
- Create: `backend/app/rules/evolution.py`
- Test: `backend/tests/test_rules_evolution.py`

**Interfaces:**
- Produces:
  - `app.rules.evolution.DEFAULT_EVOLUTION: dict` = `{"influence": {}, "applied": []}`
  - `app.rules.evolution.add_influence(evolution: dict, tag: str, n: int = 1) -> dict` — 返回累加后的新 evolution（不改入参）
  - `app.rules.evolution.check_trigger(evolution: dict, stats: dict) -> str | None` — 返回首个满足且未 applied 的触发名，否则 `None`。触发名取值：`"grumpy"`（辣条/喂食成瘾）、`"philosopher"`（哲学聊多）、`"runaway"`（被冷落）
  - `app.rules.evolution.mark_applied(evolution: dict, trigger: str) -> dict` — 把触发名加入 `applied`（返回新 dict）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_rules_evolution.py`:
```python
from app.rules.evolution import (
    DEFAULT_EVOLUTION,
    add_influence,
    check_trigger,
    mark_applied,
)


def test_add_influence_accumulates_immutably():
    ev = dict(DEFAULT_EVOLUTION)
    ev = add_influence(ev, "fed", 3)
    ev = add_influence(ev, "fed", 2)
    assert ev["influence"]["fed"] == 5
    assert DEFAULT_EVOLUTION["influence"] == {}  # 常量没被改


def test_grumpy_triggers_on_heavy_feeding():
    ev = {"influence": {"fed": 30}, "applied": []}
    stats = {"satiety": 50, "mood": 50, "cleanliness": 50, "energy": 50, "affection": 50}
    assert check_trigger(ev, stats) == "grumpy"


def test_philosopher_triggers_on_chat_topic():
    ev = {"influence": {"philosophy": 10}, "applied": []}
    stats = {"satiety": 50, "mood": 50, "cleanliness": 50, "energy": 50, "affection": 50}
    assert check_trigger(ev, stats) == "philosopher"


def test_runaway_triggers_on_neglect():
    ev = {"influence": {"neglect": 5}, "applied": []}
    stats = {"satiety": 10, "mood": 10, "cleanliness": 50, "energy": 50, "affection": 50}
    assert check_trigger(ev, stats) == "runaway"


def test_applied_trigger_not_repeated():
    ev = {"influence": {"fed": 30}, "applied": ["grumpy"]}
    stats = {"satiety": 50, "mood": 50, "cleanliness": 50, "energy": 50, "affection": 50}
    assert check_trigger(ev, stats) is None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_rules_evolution.py -v`
Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 写实现**

`backend/app/rules/evolution.py`:
```python
import copy

DEFAULT_EVOLUTION = {"influence": {}, "applied": []}

# 触发规则：(名称, 判定函数)，按顺序取第一个命中的
_TRIGGER_RULES = [
    ("grumpy", lambda inf, st: inf.get("fed", 0) >= 30),
    ("philosopher", lambda inf, st: inf.get("philosophy", 0) >= 10),
    ("runaway", lambda inf, st: inf.get("neglect", 0) >= 5),
]


def add_influence(evolution: dict, tag: str, n: int = 1) -> dict:
    out = copy.deepcopy(evolution)
    out.setdefault("influence", {})
    out["influence"][tag] = out["influence"].get(tag, 0) + n
    return out


def check_trigger(evolution: dict, stats: dict) -> str | None:
    influence = evolution.get("influence", {})
    applied = evolution.get("applied", [])
    for name, predicate in _TRIGGER_RULES:
        if name in applied:
            continue
        if predicate(influence, stats):
            return name
    return None


def mark_applied(evolution: dict, trigger: str) -> dict:
    out = copy.deepcopy(evolution)
    out.setdefault("applied", [])
    if trigger not in out["applied"]:
        out["applied"].append(trigger)
    return out
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_rules_evolution.py -v`
Expected: PASS（5 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/rules/evolution.py backend/tests/test_rules_evolution.py
git commit -m "feat(rules): evolution influence accumulation and trigger detection"
```

---

### Task 6: ORM 数据模型 + 测试夹具

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `app.db.Base`
- Produces（SQLAlchemy 模型，字段名固定，后续任务据此读写）：
  - `User(id, nickname, password_hash, coins, chat_count, chat_count_date, created_at, last_login_at)`
  - `Pet(id, user_id, name, appearance, persona, stats, stats_updated_at, evolution, memory_summary, status, biography, created_at, graduated_at)`
  - `ChatMessage(id, pet_id, role, content, created_at)`
  - `Egg(id, user_id, rarity, source, hatched, obtained_at)`
  - `Quest(id, pet_id, description, reward, status, created_at)`
  - pytest 夹具：`db_session`（内存 SQLite Session）、`client`（覆盖 `get_db` 的 TestClient）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_models.py`:
```python
from datetime import date, datetime

from app.models import Egg, Pet, User


def test_user_pet_roundtrip_with_json_fields(db_session):
    user = User(nickname="沙雕铲屎官", password_hash="x", coins=50)
    db_session.add(user)
    db_session.flush()

    pet = Pet(
        user_id=user.id,
        name="龙王仓鼠",
        appearance={"emoji": "🐹", "color": "#a0f", "description": "左耳缺角"},
        persona={"traits": ["嘴硬"], "speech_style": "东北大碴子", "backstory": "被贬下凡", "quirks": []},
        stats={"satiety": 70, "mood": 70, "cleanliness": 70, "energy": 70, "affection": 0},
        stats_updated_at=datetime(2026, 7, 3, 12, 0, 0),
        evolution={"influence": {}, "applied": []},
        status="active",
    )
    db_session.add(pet)
    db_session.flush()

    got = db_session.get(Pet, pet.id)
    assert got.appearance["emoji"] == "🐹"
    assert got.persona["speech_style"] == "东北大碴子"
    assert got.stats["satiety"] == 70
    assert got.status == "active"


def test_egg_defaults(db_session):
    user = User(nickname="a", password_hash="x")
    db_session.add(user)
    db_session.flush()
    egg = Egg(user_id=user.id, rarity="common", source="onboarding")
    db_session.add(egg)
    db_session.flush()
    got = db_session.get(Egg, egg.id)
    assert got.hatched is False
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_models.py -v`
Expected: FAIL（`ModuleNotFoundError: app.models` 或 fixture 缺失）。

- [ ] **Step 3: 写模型**

`backend/app/models.py`:
```python
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nickname: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    coins: Mapped[int] = mapped_column(Integer, default=0)
    chat_count: Mapped[int] = mapped_column(Integer, default=0)
    chat_count_date = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_login_at = mapped_column(DateTime, nullable=True)


class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    appearance = mapped_column(JSON, default=dict)
    persona = mapped_column(JSON, default=dict)
    stats = mapped_column(JSON, default=dict)
    stats_updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    evolution = mapped_column(JSON, default=dict)
    memory_summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    biography = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    graduated_at = mapped_column(DateTime, nullable=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Egg(Base):
    __tablename__ = "eggs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rarity: Mapped[str] = mapped_column(String(20), default="common")
    source: Mapped[str] = mapped_column(String(30), default="quest")
    hatched: Mapped[bool] = mapped_column(Boolean, default=False)
    obtained_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    reward = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
```

- [ ] **Step 4: 写测试夹具**

`backend/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  确保所有模型都注册到 Base.metadata
from app.db import Base, get_db
from app.main import app as fastapi_app


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_models.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 6: 提交**

```bash
git add backend/app/models.py backend/tests/conftest.py backend/tests/test_models.py
git commit -m "feat(backend): ORM models + pytest fixtures (in-memory sqlite)"
```

---

### Task 7: 安全 — 密码哈希 + JWT（纯函数）

**Files:**
- Create: `backend/app/security.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Consumes: `app.config.settings`
- Produces:
  - `app.security.hash_password(p: str) -> str`
  - `app.security.verify_password(p: str, h: str) -> bool`
  - `app.security.create_access_token(sub: str) -> str`
  - `app.security.decode_token(token: str) -> str | None` — 返回 `sub`（用户 id 字符串），无效返回 `None`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_security.py`:
```python
from app.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("s3cret")
    assert h != "s3cret"
    assert verify_password("s3cret", h) is True
    assert verify_password("wrong", h) is False


def test_jwt_roundtrip():
    token = create_access_token("42")
    assert decode_token(token) == "42"


def test_decode_invalid_token_returns_none():
    assert decode_token("not-a-token") is None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_security.py -v`
Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 写实现**

`backend/app/security.py`:
```python
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
TOKEN_TTL_MINUTES = 60 * 24 * 7  # 7 天


def hash_password(p: str) -> str:
    return pwd_context.hash(p)


def verify_password(p: str, h: str) -> bool:
    return pwd_context.verify(p, h)


def create_access_token(sub: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINUTES)
    return jwt.encode({"sub": sub, "exp": expire}, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_security.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/security.py backend/tests/test_security.py
git commit -m "feat(backend): password hashing + JWT helpers"
```

---

### Task 8: 账号 — 注册 / 登录 + 当前用户依赖 + 新手蛋

**Files:**
- Create: `backend/app/schemas.py`
- Create: `backend/app/deps.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `app.security.*`、`app.models.User`、`app.models.Egg`、`app.db.get_db`
- Produces:
  - `POST /auth/register` body `{nickname, password}` → `201 {token, user_id}`；同时给新用户发一颗 `rarity="common", source="onboarding"` 的蛋
  - `POST /auth/login` body `{nickname, password}` → `200 {token, user_id}`；更新 `last_login_at`
  - `app.deps.get_current_user(...) -> User`（FastAPI 依赖，读 `Authorization: Bearer <token>`，失败 401）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_auth.py`:
```python
def test_register_returns_token_and_grants_onboarding_egg(client, db_session):
    from app.models import Egg

    resp = client.post("/auth/register", json={"nickname": "铲屎官", "password": "pw12345"})
    assert resp.status_code == 201
    body = resp.json()
    assert "token" in body and body["user_id"] > 0

    eggs = db_session.query(Egg).filter_by(user_id=body["user_id"]).all()
    assert len(eggs) == 1
    assert eggs[0].source == "onboarding"


def test_register_duplicate_nickname_conflicts(client):
    client.post("/auth/register", json={"nickname": "dup", "password": "pw12345"})
    resp = client.post("/auth/register", json={"nickname": "dup", "password": "pw12345"})
    assert resp.status_code == 409


def test_login_success_and_wrong_password(client):
    client.post("/auth/register", json={"nickname": "u1", "password": "pw12345"})
    ok = client.post("/auth/login", json={"nickname": "u1", "password": "pw12345"})
    assert ok.status_code == 200 and "token" in ok.json()
    bad = client.post("/auth/login", json={"nickname": "u1", "password": "nope"})
    assert bad.status_code == 401
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_auth.py -v`
Expected: FAIL（404，路由不存在）。

- [ ] **Step 3: 写 Pydantic schema**

`backend/app/schemas.py`:
```python
from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    nickname: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    nickname: str
    password: str


class AuthOut(BaseModel):
    token: str
    user_id: int
```

- [ ] **Step 4: 写当前用户依赖**

`backend/app/deps.py`:
```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="missing token")
    sub = decode_token(creds.credentials)
    if sub is None:
        raise HTTPException(status_code=401, detail="invalid token")
    user = db.get(User, int(sub))
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    return user
```

- [ ] **Step 5: 写 auth 路由**

`backend/app/routers/__init__.py`：空文件。

`backend/app/routers/auth.py`:
```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Egg, User
from app.schemas import AuthOut, LoginIn, RegisterIn
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    exists = db.query(User).filter_by(nickname=body.nickname).first()
    if exists:
        raise HTTPException(status_code=409, detail="nickname taken")
    user = User(nickname=body.nickname, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    db.add(Egg(user_id=user.id, rarity="common", source="onboarding"))
    db.commit()
    return AuthOut(token=create_access_token(str(user.id)), user_id=user.id)


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(nickname=body.nickname).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="bad credentials")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return AuthOut(token=create_access_token(str(user.id)), user_id=user.id)
```

- [ ] **Step 6: 挂载路由**

`backend/app/main.py` 改为：
```python
from fastapi import FastAPI

from app.routers import auth

app = FastAPI(title="AI Pet Game API")


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
```

- [ ] **Step 7: 运行确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_auth.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 8: 提交**

```bash
git add backend/app/schemas.py backend/app/deps.py backend/app/routers/ backend/app/main.py backend/tests/test_auth.py
git commit -m "feat(auth): register/login with JWT + onboarding egg"
```

---

### Task 9: AI 提供者接口 + Stub 实现

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/ai.py`
- Test: `backend/tests/test_ai_stub.py`

**Interfaces:**
- Produces:
  - `app.services.ai.AIProvider`（Protocol）方法签名（计划 2 的 DeepSeek 实现必须照此实现）：
    - `generate_persona(rarity: str) -> dict` → `{"name": str, "appearance": {"emoji","color","description"}, "persona": {"traits": list, "speech_style": str, "backstory": str, "quirks": list}}`
    - `chat_reply(name: str, persona: dict, stats: dict, memory_summary: str, history: list[dict]) -> str`
    - `evolution_text(name: str, persona: dict, trigger: str) -> dict` → `{"persona": dict, "cutscene": str}`
    - `write_biography(name: str, persona: dict, evolution: dict) -> str`
    - `generate_quest(name: str, persona: dict) -> dict` → `{"description": str, "reward": {"coins": int, "egg": bool}}`
  - `app.services.ai.StubAIProvider`（实现上述协议，返回固定/可预测文案）
  - `app.services.ai.get_ai_provider() -> AIProvider`（FastAPI 依赖，本计划返回 `StubAIProvider()`；计划 2 用 `dependency_overrides` 或改此函数换成真 DeepSeek）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_ai_stub.py`:
```python
from app.services.ai import StubAIProvider


def test_stub_persona_shape():
    p = StubAIProvider().generate_persona("rare")
    assert set(p.keys()) == {"name", "appearance", "persona"}
    assert set(p["appearance"].keys()) == {"emoji", "color", "description"}
    assert "speech_style" in p["persona"]


def test_stub_quest_reward_shape():
    q = StubAIProvider().generate_quest("龙王仓鼠", {"traits": []})
    assert isinstance(q["description"], str) and q["description"]
    assert set(q["reward"].keys()) == {"coins", "egg"}


def test_stub_chat_reply_is_nonempty_str():
    r = StubAIProvider().chat_reply("小明", {"speech_style": "阴阳怪气"}, {}, "", [])
    assert isinstance(r, str) and r
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_ai_stub.py -v`
Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 写接口 + Stub**

`backend/app/services/__init__.py`：空文件。

`backend/app/services/ai.py`:
```python
from typing import Protocol


class AIProvider(Protocol):
    def generate_persona(self, rarity: str) -> dict: ...
    def chat_reply(
        self, name: str, persona: dict, stats: dict, memory_summary: str, history: list[dict]
    ) -> str: ...
    def evolution_text(self, name: str, persona: dict, trigger: str) -> dict: ...
    def write_biography(self, name: str, persona: dict, evolution: dict) -> str: ...
    def generate_quest(self, name: str, persona: dict) -> dict: ...


class StubAIProvider:
    """计划 1 用的假 AI：返回固定但结构正确的内容，供端到端跑通与测试。
    计划 2 会新增 DeepSeekAIProvider 实现同一套方法。"""

    def generate_persona(self, rarity: str) -> dict:
        return {
            "name": "赛博烤肠",
            "appearance": {"emoji": "🌭", "color": "#ff8a3d", "description": f"一根{rarity}级、自称有编制的烤肠"},
            "persona": {
                "traits": ["嘴硬", "戏多"],
                "speech_style": "阴阳怪气的东北腔",
                "backstory": "上辈子是夜市顶流，这辈子决定躺平。",
                "quirks": ["每天必须被夸一次"],
            },
        }

    def chat_reply(self, name, persona, stats, memory_summary, history) -> str:
        return f"（{name}翻了个白眼）就你话多，行吧行吧我听着呢。"

    def evolution_text(self, name, persona, trigger) -> dict:
        new_persona = dict(persona)
        new_persona["traits"] = list(persona.get("traits", [])) + [f"觉醒-{trigger}"]
        return {"persona": new_persona, "cutscene": f"{name}浑身一抖，触发了「{trigger}」进化！它看你的眼神变了。"}

    def write_biography(self, name, persona, evolution) -> str:
        return f"{name}的一生：从一枚不起眼的蛋，到把铲屎官治得服服帖帖的传奇。经历了{len(evolution.get('applied', []))}次觉醒，无一后悔。"

    def generate_quest(self, name, persona) -> dict:
        return {
            "description": f"{name}非要你帮它写一封辞职信，虽然它压根没工作。",
            "reward": {"coins": 30, "egg": False},
        }


def get_ai_provider() -> AIProvider:
    return StubAIProvider()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_ai_stub.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/ backend/tests/test_ai_stub.py
git commit -m "feat(ai): AIProvider protocol + StubAIProvider (deepseek swaps in plan 2)"
```

---

### Task 10: 孵蛋 — 生成新主宠 + 老宠毕业（幂等 + 事务）

**Files:**
- Create: `backend/app/routers/eggs.py`
- Modify: `backend/app/main.py`（`app.include_router(eggs.router)`）
- Test: `backend/tests/test_eggs.py`

**Interfaces:**
- Consumes: `app.deps.get_current_user`、`app.services.ai.get_ai_provider`、`app.rules.stats.DEFAULT_STATS`、`app.rules.evolution.DEFAULT_EVOLUTION`、`app.models.*`
- Produces:
  - `GET /eggs` → `200 [{id, rarity, source, hatched}]`（当前用户未孵化的蛋）
  - `POST /eggs/{egg_id}/hatch` → `201 {pet_id, name, appearance, persona}`；把该蛋标记 `hatched=True`；用 AI 生成人设建**新 active 宠**；若已有 active 宠，则先给它写传记（AI）+ `status="graduated"` + `graduated_at`；**整体一个事务**；重复孵同一颗蛋返回 `409`（幂等）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_eggs.py`:
```python
def _register(client):
    r = client.post("/auth/register", json={"nickname": "n", "password": "pw12345"})
    return r.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_hatch_creates_active_pet(client, db_session):
    from app.models import Egg, Pet

    token = _register(client)
    egg = client.get("/eggs", headers=_auth(token)).json()[0]

    resp = client.post(f"/eggs/{egg['id']}/hatch", headers=_auth(token))
    assert resp.status_code == 201
    pet = resp.json()
    assert pet["pet_id"] > 0 and pet["name"]

    row = db_session.get(Pet, pet["pet_id"])
    assert row.status == "active"
    assert db_session.get(Egg, egg["id"]).hatched is True


def test_second_hatch_graduates_previous_pet(client, db_session):
    from app.models import Egg, Pet

    token = _register(client)
    first_egg = client.get("/eggs", headers=_auth(token)).json()[0]
    first = client.post(f"/eggs/{first_egg['id']}/hatch", headers=_auth(token)).json()

    # 手动再发一颗蛋模拟"攒够了"
    user_id = db_session.query(Pet).get(first["pet_id"]).user_id
    db_session.add(Egg(user_id=user_id, rarity="rare", source="quest"))
    db_session.commit()
    second_egg = [e for e in client.get("/eggs", headers=_auth(token)).json()][0]

    client.post(f"/eggs/{second_egg['id']}/hatch", headers=_auth(token))
    assert db_session.get(Pet, first["pet_id"]).status == "graduated"
    assert db_session.get(Pet, first["pet_id"]).biography  # 传记已生成


def test_hatch_same_egg_twice_conflicts(client):
    token = _register(client)
    egg = client.get("/eggs", headers=_auth(token)).json()[0]
    client.post(f"/eggs/{egg['id']}/hatch", headers=_auth(token))
    again = client.post(f"/eggs/{egg['id']}/hatch", headers=_auth(token))
    assert again.status_code == 409
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_eggs.py -v`
Expected: FAIL（404）。

- [ ] **Step 3: 写孵蛋路由**

`backend/app/routers/eggs.py`:
```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Egg, Pet, User
from app.rules.evolution import DEFAULT_EVOLUTION
from app.rules.stats import DEFAULT_STATS
from app.services.ai import AIProvider, get_ai_provider

router = APIRouter(prefix="/eggs", tags=["eggs"])


@router.get("")
def list_eggs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    eggs = db.query(Egg).filter_by(user_id=user.id, hatched=False).all()
    return [
        {"id": e.id, "rarity": e.rarity, "source": e.source, "hatched": e.hatched}
        for e in eggs
    ]


@router.post("/{egg_id}/hatch", status_code=201)
def hatch(
    egg_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    egg = db.query(Egg).filter_by(id=egg_id, user_id=user.id).first()
    if egg is None:
        raise HTTPException(status_code=404, detail="egg not found")
    if egg.hatched:
        raise HTTPException(status_code=409, detail="egg already hatched")

    # 老宠毕业
    current = db.query(Pet).filter_by(user_id=user.id, status="active").first()
    if current is not None:
        current.biography = ai.write_biography(current.name, current.persona, current.evolution)
        current.status = "graduated"
        current.graduated_at = datetime.now(timezone.utc)

    spec = ai.generate_persona(egg.rarity)
    pet = Pet(
        user_id=user.id,
        name=spec["name"],
        appearance=spec["appearance"],
        persona=spec["persona"],
        stats=dict(DEFAULT_STATS),
        evolution={"influence": {}, "applied": []},
        status="active",
    )
    egg.hatched = True
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return {
        "pet_id": pet.id,
        "name": pet.name,
        "appearance": pet.appearance,
        "persona": pet.persona,
    }
```

（注：`DEFAULT_EVOLUTION` 是共享常量，这里直接写字面量新 dict 避免别名，故未直接引用；import 保留给后续任务可用。若 linter 报未使用，删掉该 import。）

- [ ] **Step 4: 挂载路由**

`backend/app/main.py` 增加：
```python
from app.routers import auth, eggs
# ...
app.include_router(eggs.router)
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_eggs.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/eggs.py backend/app/main.py backend/tests/test_eggs.py
git commit -m "feat(eggs): hatch new active pet + graduate previous with biography (idempotent)"
```

---

### Task 11: 主宠读取 — 懒计算衰减

**Files:**
- Create: `backend/app/routers/pets.py`
- Modify: `backend/app/main.py`（`app.include_router(pets.router)`）
- Test: `backend/tests/test_pets_read.py`

**Interfaces:**
- Consumes: `app.rules.stats.apply_decay`、`app.deps.get_current_user`、`app.models.Pet`
- Produces:
  - `GET /pets/active` → `200 {id, name, appearance, persona, stats, evolution, status}`；读取时按 `now - stats_updated_at` 懒计算衰减，落库更新 `stats` + `stats_updated_at`；无 active 宠返回 `404`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_pets_read.py`:
```python
from datetime import datetime, timedelta, timezone


def _register_and_hatch(client):
    token = client.post("/auth/register", json={"nickname": "n", "password": "pw12345"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    egg = client.get("/eggs", headers=headers).json()[0]
    client.post(f"/eggs/{egg['id']}/hatch", headers=headers)
    return headers


def test_active_pet_decays_since_last_update(client, db_session):
    from app.models import Pet

    headers = _register_and_hatch(client)
    pet = db_session.query(Pet).filter_by(status="active").first()
    # 把上次更新时间拨到 5 小时前
    pet.stats_updated_at = datetime.now(timezone.utc) - timedelta(hours=5)
    pet.stats = {"satiety": 90, "mood": 90, "cleanliness": 90, "energy": 90, "affection": 20}
    db_session.commit()

    resp = client.get("/pets/active", headers=headers)
    assert resp.status_code == 200
    stats = resp.json()["stats"]
    assert stats["satiety"] < 90  # 衰减发生了
    assert stats["affection"] == 20  # affection 不衰减


def test_no_active_pet_returns_404(client):
    token = client.post("/auth/register", json={"nickname": "z", "password": "pw12345"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    # 注册后只有蛋没孵，没有 active 宠
    resp = client.get("/pets/active", headers=headers)
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_pets_read.py -v`
Expected: FAIL（404 路由不存在 / 或断言失败）。

- [ ] **Step 3: 写路由**

`backend/app/routers/pets.py`:
```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Pet, User
from app.rules.stats import apply_decay

router = APIRouter(prefix="/pets", tags=["pets"])


def _load_active_or_404(db: Session, user_id: int) -> Pet:
    pet = db.query(Pet).filter_by(user_id=user_id, status="active").first()
    if pet is None:
        raise HTTPException(status_code=404, detail="no active pet")
    return pet


def _apply_lazy_decay(pet: Pet) -> None:
    now = datetime.now(timezone.utc)
    last = pet.stats_updated_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    elapsed = (now - last).total_seconds()
    pet.stats = apply_decay(pet.stats, elapsed)
    pet.stats_updated_at = now


def _serialize(pet: Pet) -> dict:
    return {
        "id": pet.id,
        "name": pet.name,
        "appearance": pet.appearance,
        "persona": pet.persona,
        "stats": pet.stats,
        "evolution": pet.evolution,
        "status": pet.status,
    }


@router.get("/active")
def get_active(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pet = _load_active_or_404(db, user.id)
    _apply_lazy_decay(pet)
    db.commit()
    return _serialize(pet)
```

- [ ] **Step 4: 挂载路由**

`backend/app/main.py` 增加 `from app.routers import auth, eggs, pets` 与 `app.include_router(pets.router)`。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_pets_read.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/pets.py backend/app/main.py backend/tests/test_pets_read.py
git commit -m "feat(pets): GET /pets/active with lazy time-based decay"
```

---

### Task 12: 照顾动作端点（衰减 → 施加动作 → 进化影响 → 事务落库）

**Files:**
- Modify: `backend/app/routers/pets.py`
- Test: `backend/tests/test_pets_care.py`

**Interfaces:**
- Consumes: `app.rules.care.apply_care`、`app.rules.care.CARE_ACTIONS`、`app.rules.evolution.add_influence`
- Produces:
  - `POST /pets/care/{action}`（action ∈ feed/play/wash/rest）→ `200 {stats, reaction}`；流程：先懒计算衰减 → `apply_care` → `add_influence(evolution, tag)` → 落库（一个事务）；非法 action 返回 `422`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_pets_care.py`:
```python
def _register_and_hatch(client):
    token = client.post("/auth/register", json={"nickname": "n", "password": "pw12345"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    egg = client.get("/eggs", headers=headers).json()[0]
    client.post(f"/eggs/{egg['id']}/hatch", headers=headers)
    return headers


def test_feed_updates_stats_and_influence(client, db_session):
    from app.models import Pet

    headers = _register_and_hatch(client)
    resp = client.post("/pets/care/feed", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["reaction"]
    assert "satiety" in body["stats"]

    pet = db_session.query(Pet).filter_by(status="active").first()
    assert pet.evolution["influence"].get("fed", 0) >= 1


def test_invalid_action_rejected(client):
    headers = _register_and_hatch(client)
    resp = client.post("/pets/care/teleport", headers=headers)
    assert resp.status_code == 422
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_pets_care.py -v`
Expected: FAIL（404/405）。

- [ ] **Step 3: 追加路由到 `pets.py`**

在 `backend/app/routers/pets.py` 末尾追加（复用已有的 `_load_active_or_404` / `_apply_lazy_decay`）：
```python
from fastapi import Path

from app.rules.care import CARE_ACTIONS, apply_care
from app.rules.evolution import add_influence


@router.post("/care/{action}")
def care(
    action: str = Path(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if action not in CARE_ACTIONS:
        raise HTTPException(status_code=422, detail="unknown action")
    pet = _load_active_or_404(db, user.id)
    _apply_lazy_decay(pet)
    new_stats, reaction, tag = apply_care(pet.stats, action)
    pet.stats = new_stats
    pet.evolution = add_influence(pet.evolution, tag)
    db.commit()
    return {"stats": pet.stats, "reaction": reaction}
```

（把新增的 `import` 提到文件顶部与其它 import 合并，避免函数内 import。）

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_pets_care.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/pets.py backend/tests/test_pets_care.py
git commit -m "feat(pets): care action endpoint updates stats + evolution influence"
```

---

### Task 13: 聊天端点（Stub AI + 每日软上限 + 进化关键词）

**Files:**
- Modify: `backend/app/routers/pets.py`
- Test: `backend/tests/test_pets_chat.py`

**Interfaces:**
- Consumes: `app.services.ai.get_ai_provider`、`app.rules.evolution.add_influence`、`app.config.settings.daily_chat_cap`、`app.models.ChatMessage`
- Produces:
  - `POST /pets/chat` body `{message}` → `200 {reply, capped: bool}`；流程：检查/重置每日计数（按 `chat_count_date` 与今天比对）→ 若已达 `daily_chat_cap`，`capped=True` 且用人设卖萌文案（不调用 AI、不加计数）→ 否则调用 `ai.chat_reply`，存两条 `ChatMessage`（role=`user`/`pet`），`affection +1`，若消息含"哲学/意义/人生"等关键词则 `add_influence(evolution,"philosophy")`，`chat_count += 1`，一个事务落库

- [ ] **Step 1: 写失败测试**

`backend/tests/test_pets_chat.py`:
```python
from datetime import date


def _register_and_hatch(client):
    token = client.post("/auth/register", json={"nickname": "n", "password": "pw12345"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    egg = client.get("/eggs", headers=headers).json()[0]
    client.post(f"/eggs/{egg['id']}/hatch", headers=headers)
    return headers


def test_chat_returns_reply_and_stores_messages(client, db_session):
    from app.models import ChatMessage

    headers = _register_and_hatch(client)
    resp = client.post("/pets/chat", headers=headers, json={"message": "在吗"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] and body["capped"] is False
    assert db_session.query(ChatMessage).count() == 2  # user + pet


def test_philosophy_keyword_adds_influence(client, db_session):
    from app.models import Pet

    headers = _register_and_hatch(client)
    client.post("/pets/chat", headers=headers, json={"message": "你觉得人生的意义是什么"})
    pet = db_session.query(Pet).filter_by(status="active").first()
    assert pet.evolution["influence"].get("philosophy", 0) >= 1


def test_daily_cap_blocks_without_ai(client, db_session):
    from app.models import User

    headers = _register_and_hatch(client)
    user = db_session.query(User).first()
    user.chat_count = 50
    user.chat_count_date = date.today()
    db_session.commit()

    resp = client.post("/pets/chat", headers=headers, json={"message": "再聊一句"})
    assert resp.status_code == 200
    assert resp.json()["capped"] is True
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_pets_chat.py -v`
Expected: FAIL（404）。

- [ ] **Step 3: 追加聊天路由到 `pets.py`**

顶部 import 增补：
```python
from datetime import date

from pydantic import BaseModel

from app.config import settings
from app.models import ChatMessage
from app.services.ai import AIProvider, get_ai_provider
```
路由体：
```python
class ChatIn(BaseModel):
    message: str


PHILOSOPHY_KEYWORDS = ("哲学", "意义", "人生", "存在", "宇宙")


@router.post("/chat")
def chat(
    body: ChatIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    pet = _load_active_or_404(db, user.id)

    today = date.today()
    if user.chat_count_date != today:
        user.chat_count = 0
        user.chat_count_date = today

    if user.chat_count >= settings.daily_chat_cap:
        db.commit()
        return {"reply": f"（{pet.name}打了个哈欠）今天聊累了，明儿再唠嗑吧。", "capped": True}

    reply = ai.chat_reply(pet.name, pet.persona, pet.stats, pet.memory_summary, [])
    db.add(ChatMessage(pet_id=pet.id, role="user", content=body.message))
    db.add(ChatMessage(pet_id=pet.id, role="pet", content=reply))

    pet.stats = {**pet.stats, "affection": min(100, pet.stats["affection"] + 1)}
    if any(k in body.message for k in PHILOSOPHY_KEYWORDS):
        pet.evolution = add_influence(pet.evolution, "philosophy")
    user.chat_count += 1
    db.commit()
    return {"reply": reply, "capped": False}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_pets_chat.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/pets.py backend/tests/test_pets_chat.py
git commit -m "feat(pets): chat endpoint with daily cap + philosophy influence"
```

---

### Task 14: 任务（quests）— 生成 / 列表 / 完成（幂等发奖）

**Files:**
- Create: `backend/app/routers/quests.py`
- Modify: `backend/app/main.py`（`app.include_router(quests.router)`）
- Test: `backend/tests/test_quests.py`

**Interfaces:**
- Consumes: `app.services.ai.get_ai_provider`、`app.rules.economy.normalize_reward`、`app.models.Quest`、`app.models.Egg`
- Produces:
  - `POST /quests/generate` → `201 {id, description, reward}`（给当前 active 宠用 AI 生成一条 active 任务）
  - `GET /quests` → `200 [{id, description, reward, status}]`（当前 active 宠的任务）
  - `POST /quests/{quest_id}/complete` → `200 {coins, granted_egg: bool}`；把任务置 `completed`、按 `reward` 发 coins（可选发蛋）；已 `completed` 的任务再次调用返回 `409`（幂等，不重复发奖）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_quests.py`:
```python
def _register_and_hatch(client):
    token = client.post("/auth/register", json={"nickname": "n", "password": "pw12345"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    egg = client.get("/eggs", headers=headers).json()[0]
    client.post(f"/eggs/{egg['id']}/hatch", headers=headers)
    return headers


def test_generate_and_complete_grants_coins(client, db_session):
    from app.models import User

    headers = _register_and_hatch(client)
    q = client.post("/quests/generate", headers=headers).json()
    assert q["description"]

    resp = client.post(f"/quests/{q['id']}/complete", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["coins"] == 30
    assert db_session.query(User).first().coins == 30


def test_complete_twice_is_idempotent(client, db_session):
    from app.models import User

    headers = _register_and_hatch(client)
    q = client.post("/quests/generate", headers=headers).json()
    client.post(f"/quests/{q['id']}/complete", headers=headers)
    again = client.post(f"/quests/{q['id']}/complete", headers=headers)
    assert again.status_code == 409
    assert db_session.query(User).first().coins == 30  # 没有翻倍
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_quests.py -v`
Expected: FAIL（404）。

- [ ] **Step 3: 写路由**

`backend/app/routers/quests.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Egg, Pet, Quest, User
from app.rules.economy import normalize_reward
from app.services.ai import AIProvider, get_ai_provider

router = APIRouter(prefix="/quests", tags=["quests"])


def _active_pet(db: Session, user_id: int) -> Pet:
    pet = db.query(Pet).filter_by(user_id=user_id, status="active").first()
    if pet is None:
        raise HTTPException(status_code=404, detail="no active pet")
    return pet


@router.post("/generate", status_code=201)
def generate(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    pet = _active_pet(db, user.id)
    spec = ai.generate_quest(pet.name, pet.persona)
    quest = Quest(
        pet_id=pet.id,
        description=spec["description"],
        reward=normalize_reward(spec["reward"]),
        status="active",
    )
    db.add(quest)
    db.commit()
    db.refresh(quest)
    return {"id": quest.id, "description": quest.description, "reward": quest.reward}


@router.get("")
def list_quests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pet = _active_pet(db, user.id)
    quests = db.query(Quest).filter_by(pet_id=pet.id).all()
    return [
        {"id": q.id, "description": q.description, "reward": q.reward, "status": q.status}
        for q in quests
    ]


@router.post("/{quest_id}/complete")
def complete(
    quest_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pet = _active_pet(db, user.id)
    quest = db.query(Quest).filter_by(id=quest_id, pet_id=pet.id).first()
    if quest is None:
        raise HTTPException(status_code=404, detail="quest not found")
    if quest.status == "completed":
        raise HTTPException(status_code=409, detail="quest already completed")

    reward = normalize_reward(quest.reward)
    user.coins += reward["coins"]
    granted_egg = False
    if reward["egg"]:
        db.add(Egg(user_id=user.id, rarity="common", source="quest"))
        granted_egg = True
    quest.status = "completed"
    db.commit()
    return {"coins": reward["coins"], "granted_egg": granted_egg}
```

- [ ] **Step 4: 挂载路由**

`backend/app/main.py` 增加 `from app.routers import auth, eggs, pets, quests` 与 `app.include_router(quests.router)`。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && ./.venv/bin/pytest tests/test_quests.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/quests.py backend/app/main.py backend/tests/test_quests.py
git commit -m "feat(quests): generate/list/complete with idempotent reward payout"
```

---

### Task 15: 图鉴读取 + 进化事件端点 + 全量回归

**Files:**
- Modify: `backend/app/routers/pets.py`
- Test: `backend/tests/test_collection.py`

**Interfaces:**
- Consumes: `app.rules.evolution.check_trigger`、`app.rules.evolution.mark_applied`、`app.services.ai.get_ai_provider`
- Produces:
  - `GET /pets/collection` → `200 [{id, name, appearance, biography, graduated_at}]`（当前用户 `status="graduated"` 的老宠，即图鉴）
  - `POST /pets/evolve/check` → `200 {evolved: bool, trigger: str|null, cutscene: str|null}`；对 active 宠先懒衰减，`check_trigger` 命中则调用 `ai.evolution_text` 改写 persona、`mark_applied`、落库；无触发则 `evolved=False`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_collection.py`:
```python
def _register_and_hatch(client):
    token = client.post("/auth/register", json={"nickname": "n", "password": "pw12345"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    egg = client.get("/eggs", headers=headers).json()[0]
    client.post(f"/eggs/{egg['id']}/hatch", headers=headers)
    return headers


def test_collection_lists_graduated_pets(client, db_session):
    from app.models import Egg, Pet

    headers = _register_and_hatch(client)
    user_id = db_session.query(Pet).first().user_id
    db_session.add(Egg(user_id=user_id, rarity="rare", source="quest"))
    db_session.commit()
    egg2 = [e for e in client.get("/eggs", headers=headers).json()][0]
    client.post(f"/eggs/{egg2['id']}/hatch", headers=headers)  # 让第一只毕业

    coll = client.get("/pets/collection", headers=headers).json()
    assert len(coll) == 1
    assert coll[0]["biography"]


def test_evolve_check_triggers_grumpy(client, db_session):
    from app.models import Pet

    headers = _register_and_hatch(client)
    pet = db_session.query(Pet).filter_by(status="active").first()
    pet.evolution = {"influence": {"fed": 30}, "applied": []}
    db_session.commit()

    resp = client.post("/pets/evolve/check", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["evolved"] is True
    assert body["trigger"] == "grumpy"
    assert body["cutscene"]


def test_evolve_check_no_trigger(client):
    headers = _register_and_hatch(client)
    resp = client.post("/pets/evolve/check", headers=headers)
    assert resp.json()["evolved"] is False
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && ./.venv/bin/pytest tests/test_collection.py -v`
Expected: FAIL（404）。

- [ ] **Step 3: 追加路由到 `pets.py`**

顶部 import 增补：
```python
from app.rules.evolution import check_trigger, mark_applied
```
路由体（`add_influence`/`AIProvider`/`get_ai_provider` 已在前面任务引入）：
```python
@router.get("/collection")
def collection(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pets = (
        db.query(Pet)
        .filter_by(user_id=user.id, status="graduated")
        .order_by(Pet.graduated_at.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "name": p.name,
            "appearance": p.appearance,
            "biography": p.biography,
            "graduated_at": p.graduated_at.isoformat() if p.graduated_at else None,
        }
        for p in pets
    ]


@router.post("/evolve/check")
def evolve_check(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    pet = _load_active_or_404(db, user.id)
    _apply_lazy_decay(pet)
    trigger = check_trigger(pet.evolution, pet.stats)
    if trigger is None:
        db.commit()
        return {"evolved": False, "trigger": None, "cutscene": None}

    result = ai.evolution_text(pet.name, pet.persona, trigger)
    pet.persona = result["persona"]
    pet.evolution = mark_applied(pet.evolution, trigger)
    db.commit()
    return {"evolved": True, "trigger": trigger, "cutscene": result["cutscene"]}
```

- [ ] **Step 4: 运行确认通过（含全量回归）**

Run: `cd backend && ./.venv/bin/pytest -v`
Expected: 全部 PASS（本计划累计约 30+ 用例）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/pets.py backend/tests/test_collection.py
git commit -m "feat(pets): collection (图鉴) read + evolution trigger endpoint"
```

---

## Self-Review

**Spec coverage（对照设计文档逐节核对）：**
- §3 系统架构 → Task 1（FastAPI/DB）、全局约束"前端纯展示/后端唯一真相源" ✅
- §4 数据模型（users/pets/chat_messages/eggs/quests，JSON 字段，memory_summary）→ Task 6 ✅
- §5 数值衰减/懒计算 → Task 2 + Task 11 ✅；照顾按钮 → Task 3 + Task 12 ✅；变异进化 → Task 5 + Task 15 ✅；孵蛋换代 + 毕业传记 → Task 10 ✅；图鉴 → Task 15 ✅；轻经济 coins/quests/eggs → Task 4 + Task 14 ✅
- §6 AI 集成：AIProvider 接口 + Stub（计划 2 换真 DeepSeek）→ Task 9 ✅；每日软上限 → Task 13 ✅；（真 prompt/流式/安全护栏/记忆压缩 = 计划 2，本计划不做，符合分期）
- §7 界面 → 计划 3，本计划不涉及 ✅
- §8 错误处理：幂等（孵蛋 Task 10、领奖 Task 14）、事务落库（各写端点 `db.commit()` 原子提交）、服务端唯一真相源（懒计算 Task 11）✅；（前端乐观更新/账号刷新 = 计划 3）
- §9 非目标：无第三方登录、无多宠、图鉴只读、无定时任务 —— 计划未引入，符合 ✅

**Placeholder scan：** 无 TODO/TBD；每个 code step 均含完整可运行代码。

**Type consistency：** stats 五键在 Task 2/3/11/12/13 一致；evolution 结构 `{"influence","applied"}` 在 Task 5/10/12/13/15 一致；AIProvider 五个方法签名 Task 9 定义、Task 10/13/14/15 按此调用一致；`_load_active_or_404`/`_apply_lazy_decay` 在 Task 11 定义、Task 12/15 复用。

**已知实现提示（非阻塞）：** Task 12/13/15 会往 `pets.py` 顶部合并 import；执行者应把散落的 import 收拢到文件头，保持单一职责与整洁。
