# 情侣火苗 🔥 + 每日一问 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给游戏加每日回访钩子——情侣火苗 streak(两人都得每天露面才续)+ 每日一问(双方都答完才解锁对方答案)。

**Architecture:** 后端沿用现有分层:纯函数放 `app/rules/*.py`(无 DB/时钟,好单测),DB 编排放 service + router;火苗状态存新表 `couple_streaks`,每日问答存 `daily_questions`/`daily_answers`;解锁时往现有 `events` 时间线落一条 `daily_qa` 事件。前端沿用 TanStack Query 轮询 + MSW 测试,首页顶部加火苗条 + 今日一问卡。

**Tech Stack:** 后端 FastAPI + SQLAlchemy 2.0 + pytest(内存 SQLite);前端 Vite + React 18 + TS + TanStack Query + Vitest + MSW。

## Global Constraints

- **前端只用 pnpm**,禁止 npm/npx。前端测试:`pnpm -C frontend exec vitest run <file>`;类型检查:`pnpm -C frontend exec tsc --noEmit`。
- **后端测试**从 `backend/` 跑:`cd backend && .venv/bin/python -m pytest <path> -v`。
- **新模型必须写进 `backend/app/models.py`**——启动时 `Base.metadata.create_all` 按 `Base.metadata` 建表,不写这里不会建表。无 Alembic,不写迁移。
- **DeepSeek key 只在服务端**;空 key / 超额一律走本地兜底,绝不 500、不空屏。本计划**出题走本地题库**(AI 出题列为可选后续)。
- **所有面向用户的文案用中文、无厘头风**;代码注释跟随周边中文风格。
- **幂等**靠请求里的 `client_key`。
- 时间用 `app.time_utils.utcnow()`(naive UTC)。日界=UTC+8 固定偏移(配置 `streak_utc_offset_hours`,默认 8),不引入 zoneinfo/tzdata。
- **纯函数不碰 DB/时钟/settings**:`today` 由调用方算好传入,镜像现有 `rules/stats.py` 的风格。

---

## File Structure

**新建**
- `backend/app/rules/streak.py` — 火苗纯函数(touch/view/rescue/today_for)。
- `backend/app/rules/daily_questions.py` — 每日一问本地题库 + 选题纯函数。
- `backend/app/streak_service.py` — 火苗 DB 编排(行↔state、槽位、do_touch、build_view)。
- `backend/app/routers/daily.py` — `GET /daily`、`POST /daily/answer`、`POST /streak/rescue`。
- `backend/tests/test_rules_streak.py`、`test_rules_daily_questions.py`、`test_daily.py`。
- `frontend/src/api/daily.ts` — 前端 API 封装。
- `frontend/src/hooks/useDaily.ts` — 今日一问 + 火苗数据 hook。
- `frontend/src/home/FireBar.tsx` — 火苗条。
- `frontend/src/home/DailyQuestionCard.tsx` — 今日一问卡(三态)。
- 对应 `*.test.tsx`。

**修改**
- `backend/app/config.py` — 加 `streak_utc_offset_hours`。
- `backend/app/models.py` — 加 `CoupleStreak`、`DailyQuestion`、`DailyAnswer`。
- `backend/app/routers/actions.py` — `do_action` 末尾 commit 前调 `streak_service.do_touch`。
- `backend/app/main.py` — 注册 `daily.router`。
- `frontend/src/api/types.ts` — `EventKind` 加 `'daily_qa'`;加 `DailyResponse`/`StreakView` 类型。
- `frontend/src/home/HomeScreen.tsx` — 顶部插入 `FireBar` + `DailyQuestionCard`。
- `frontend/src/chat/ChatScreen.tsx` — 渲染 `daily_qa` 问答卡。

---

## Task 1: 火苗纯函数 `rules/streak.py`

**Files:**
- Create: `backend/app/rules/streak.py`
- Create: `backend/app/tests`… → Test: `backend/tests/test_rules_streak.py`
- Modify: `backend/app/config.py`(加配置项)

**Interfaces:**
- Produces:
  - `today_for(now_utc: datetime, offset_hours: int = 8) -> date`
  - `empty_state() -> dict`（keys: `count:int, last_both_day:date|None, a_active_day:date|None, b_active_day:date|None, rescue_day:date|None`）
  - `touch(state: dict, slot: str, today: date) -> dict`（`slot ∈ {"a","b"}`）
  - `view(state: dict, slot: str, today: date) -> dict`（keys: `count, i_did_today, partner_did_today, at_risk, lagging_slot`）
  - `can_rescue(state: dict, today: date) -> bool`
  - `rescue(state: dict, today: date) -> dict`

- [ ] **Step 1: 写失败测试** `backend/tests/test_rules_streak.py`

```python
from datetime import date, datetime, timedelta

from app.rules.streak import (
    today_for,
    empty_state,
    touch,
    view,
    can_rescue,
    rescue,
)

D = date(2026, 7, 8)          # “今天”
Y = D - timedelta(days=1)     # 昨天
DBY = D - timedelta(days=2)   # 前天


def test_today_for_applies_utc8_offset():
    # 2026-07-08 17:00 UTC = 2026-07-09 01:00 +08 → 落在 7/9
    assert today_for(datetime(2026, 7, 8, 17, 0, 0), 8) == date(2026, 7, 9)
    assert today_for(datetime(2026, 7, 8, 15, 0, 0), 8) == date(2026, 7, 8)


def test_empty_state_shape():
    s = empty_state()
    assert s == {
        "count": 0,
        "last_both_day": None,
        "a_active_day": None,
        "b_active_day": None,
        "rescue_day": None,
    }


def test_touch_one_side_does_not_advance():
    s = touch(empty_state(), "a", D)
    assert s["a_active_day"] == D
    assert s["count"] == 0            # 只有一方，火苗没起
    assert s["last_both_day"] is None


def test_touch_both_today_starts_at_one():
    s = touch(empty_state(), "a", D)
    s = touch(s, "b", D)
    assert s["count"] == 1
    assert s["last_both_day"] == D


def test_touch_continues_from_yesterday():
    s = {"count": 5, "last_both_day": Y, "a_active_day": Y, "b_active_day": Y, "rescue_day": None}
    s = touch(s, "a", D)
    s = touch(s, "b", D)
    assert s["count"] == 6            # 昨天完成→今天+1


def test_touch_resets_after_gap():
    s = {"count": 5, "last_both_day": DBY, "a_active_day": DBY, "b_active_day": DBY, "rescue_day": None}
    s = touch(s, "a", D)
    s = touch(s, "b", D)
    assert s["count"] == 1            # 断了→重新从 1 起


def test_touch_same_day_is_idempotent():
    s = touch(touch(empty_state(), "a", D), "b", D)
    again = touch(s, "a", D)         # 同一天再 touch 不重复 +1
    assert again["count"] == 1


def test_view_alive_and_both_done():
    s = touch(touch(empty_state(), "a", D), "b", D)
    v = view(s, "a", D)
    assert v == {
        "count": 1,
        "i_did_today": True,
        "partner_did_today": True,
        "at_risk": False,
        "lagging_slot": None,
    }


def test_view_one_done_one_not_flags_lagging():
    s = touch(empty_state(), "a", D)  # 只有 a 今天动了；last_both_day 仍 None
    s["last_both_day"] = Y            # 假设昨天完成过，火苗还活着
    v_from_a = view(s, "a", D)
    assert v_from_a["i_did_today"] is True
    assert v_from_a["partner_did_today"] is False
    assert v_from_a["at_risk"] is True
    assert v_from_a["lagging_slot"] == "b"   # 该催 b
    v_from_b = view(s, "b", D)
    assert v_from_b["i_did_today"] is False
    assert v_from_b["partner_did_today"] is True


def test_view_broken_shows_zero():
    s = {"count": 9, "last_both_day": DBY, "a_active_day": DBY, "b_active_day": DBY, "rescue_day": None}
    v = view(s, "a", D)
    assert v["count"] == 0            # 断了显示 0
    assert v["at_risk"] is False


def test_rescue_only_when_missed_exactly_one_day():
    ok = {"count": 3, "last_both_day": DBY, "a_active_day": DBY, "b_active_day": DBY, "rescue_day": None}
    assert can_rescue(ok, D) is True
    r = rescue(ok, D)
    assert r["last_both_day"] == Y    # 补成昨天完成
    assert r["rescue_day"] == D
    assert r["count"] == 3            # 天数保留
    # 今天再让两人 touch 就能续上
    r = touch(touch(r, "a", D), "b", D)
    assert r["count"] == 4


def test_rescue_blocked_twice_same_day_or_bigger_gap():
    used = {"count": 3, "last_both_day": DBY, "a_active_day": DBY, "b_active_day": DBY, "rescue_day": D}
    assert can_rescue(used, D) is False           # 今天已续过
    big_gap = {"count": 3, "last_both_day": D - timedelta(days=3), "a_active_day": None, "b_active_day": None, "rescue_day": None}
    assert can_rescue(big_gap, D) is False         # 漏超过一天，不给救
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_rules_streak.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'app.rules.streak'`）

- [ ] **Step 3: 写实现** `backend/app/rules/streak.py`

```python
"""纯函数：情侣火苗 streak。无 DB / 时钟 / settings。today 由调用方传入。"""

from datetime import date, datetime, timedelta

ONE_DAY = timedelta(days=1)


def today_for(now_utc: datetime, offset_hours: int = 8) -> date:
    """把 naive-UTC 现在换算成固定偏移时区下的“日期”（默认 UTC+8=上海，无 DST）。"""
    return (now_utc + timedelta(hours=offset_hours)).date()


def empty_state() -> dict:
    return {
        "count": 0,
        "last_both_day": None,
        "a_active_day": None,
        "b_active_day": None,
        "rescue_day": None,
    }


def touch(state: dict, slot: str, today: date) -> dict:
    """记一次某槽（'a'/'b'）今天的有效互动，必要时推进 count。返回新 state（不改入参）。"""
    if slot not in ("a", "b"):
        raise ValueError(f"bad slot: {slot}")
    out = dict(state)
    out[f"{slot}_active_day"] = today
    both_today = out["a_active_day"] == today and out["b_active_day"] == today
    if both_today and out["last_both_day"] != today:
        out["count"] = out["count"] + 1 if out["last_both_day"] == today - ONE_DAY else 1
        out["last_both_day"] = today
    return out


def view(state: dict, slot: str, today: date) -> dict:
    """读时派生（不改存储）。slot=发起请求者的槽，用于算 i/partner_did。"""
    last = state["last_both_day"]
    alive = last in (today, today - ONE_DAY)
    a_today = state["a_active_day"] == today
    b_today = state["b_active_day"] == today
    both_today = a_today and b_today
    i_did = a_today if slot == "a" else b_today
    partner_did = b_today if slot == "a" else a_today
    lagging = None
    if alive:
        if a_today and not b_today:
            lagging = "b"
        elif b_today and not a_today:
            lagging = "a"
    return {
        "count": state["count"] if alive else 0,
        "i_did_today": i_did,
        "partner_did_today": partner_did,
        "at_risk": alive and not both_today,
        "lagging_slot": lagging,
    }


def can_rescue(state: dict, today: date) -> bool:
    """只漏了正好一天（前天完成、昨天空了）且今天还没续过，才可补救。"""
    return state["last_both_day"] == today - 2 * ONE_DAY and state["rescue_day"] != today


def rescue(state: dict, today: date) -> dict:
    out = dict(state)
    out["last_both_day"] = today - ONE_DAY  # 补成昨天完成，今天两人 touch 即可续
    out["rescue_day"] = today
    return out
```

- [ ] **Step 4: 加配置项** `backend/app/config.py`（在 `nudge_idle_seconds` 那行后加一行）

```python
    streak_utc_offset_hours: int = 8  # 火苗日界时区偏移（8=上海，无 DST）
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_rules_streak.py -v`
Expected: PASS(12 passed)

- [ ] **Step 6: 提交**

```bash
git add backend/app/rules/streak.py backend/tests/test_rules_streak.py backend/app/config.py
git commit -m "feat(streak): 火苗纯函数 touch/view/rescue + UTC+8 日界"
```

---

## Task 2: 数据模型 `CoupleStreak` / `DailyQuestion` / `DailyAnswer`

**Files:**
- Modify: `backend/app/models.py`（文件尾追加三个模型)
- Test: `backend/tests/test_models.py`（追加一个建表/字段测试;若无该测试文件的合适入口,新建 `test_models_daily.py`）

**Interfaces:**
- Produces(ORM 列):
  - `CoupleStreak(couple_id PK, count int, last_both_day Date|None, a_active_day Date|None, b_active_day Date|None, rescue_day Date|None)`
  - `DailyQuestion(id PK, couple_id, day Date, question Text, flavor str, created_at)`，唯一 `(couple_id, day)`
  - `DailyAnswer(id PK, question_id, user_id, content Text, client_key str|None, created_at)`，唯一 `(question_id, user_id)`

- [ ] **Step 1: 写失败测试** `backend/tests/test_models_daily.py`

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models_daily.py -v`
Expected: FAIL(`ImportError: cannot import name 'CoupleStreak'`)

- [ ] **Step 3: 写实现** —— 在 `backend/app/models.py` 末尾追加

```python
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
```

（`Integer/Date/DateTime/String/Text/ForeignKey/UniqueConstraint/Mapped/mapped_column/utcnow` 均已在文件顶部 import,无需新增。)

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models_daily.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: 提交**

```bash
git add backend/app/models.py backend/tests/test_models_daily.py
git commit -m "feat(models): couple_streaks + daily_questions + daily_answers"
```

---

## Task 3: 每日一问本地题库 `rules/daily_questions.py`

**Files:**
- Create: `backend/app/rules/daily_questions.py`
- Test: `backend/tests/test_rules_daily_questions.py`

**Interfaces:**
- Produces:
  - `FLAVORS: list[str]`（`["ambiguous", "deep", "silly"]`）
  - `LOCAL_QUESTIONS: dict[str, list[str]]`
  - `choose_flavor(seed: int) -> str`（确定性:`FLAVORS[seed % 3]`,便于测试与“按天定味”)
  - `pick_local(flavor: str, exclude: set[str], seed: int) -> str`（避开 `exclude`,确定性挑一句)

- [ ] **Step 1: 写失败测试** `backend/tests/test_rules_daily_questions.py`

```python
from app.rules.daily_questions import (
    FLAVORS,
    LOCAL_QUESTIONS,
    choose_flavor,
    pick_local,
)


def test_three_flavors_each_have_enough_unique_lines():
    assert FLAVORS == ["ambiguous", "deep", "silly"]
    for flavor in FLAVORS:
        lines = LOCAL_QUESTIONS[flavor]
        assert len(lines) >= 8, f"{flavor} 只有 {len(lines)} 条"
        assert len(set(lines)) == len(lines), f"{flavor} 有重复"


def test_choose_flavor_is_deterministic_and_cycles():
    assert choose_flavor(0) == "ambiguous"
    assert choose_flavor(1) == "deep"
    assert choose_flavor(2) == "silly"
    assert choose_flavor(3) == "ambiguous"


def test_pick_local_returns_a_line_from_that_flavor():
    q = pick_local("silly", set(), seed=0)
    assert q in LOCAL_QUESTIONS["silly"]


def test_pick_local_avoids_excluded_when_possible():
    bank = LOCAL_QUESTIONS["deep"]
    exclude = set(bank[:-1])  # 只留最后一条没被排除
    q = pick_local("deep", exclude, seed=0)
    assert q == bank[-1]


def test_pick_local_falls_back_when_all_excluded():
    bank = LOCAL_QUESTIONS["deep"]
    q = pick_local("deep", set(bank), seed=0)  # 全排除也得给一句
    assert q in bank
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_rules_daily_questions.py -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: 写实现** `backend/app/rules/daily_questions.py`

```python
"""纯函数：每日一问的本地题库 + 选题。无 DB / 时钟 / AI。混味=三种 flavor 轮换。"""

FLAVORS = ["ambiguous", "deep", "silly"]

LOCAL_QUESTIONS = {
    # 暧昧撩拨
    "ambiguous": [
        "我身上你最想咬一口的地方是哪儿?",
        "如果现在能瞬移到我身边,你第一件事想干嘛?",
        "我做过最让你心动的一个小动作是什么?",
        "今晚想在梦里跟我做点啥?",
        "我哪个表情或角度最让你把持不住?",
        "如果只能亲我一个地方,你选哪儿?",
        "有件想跟我一起做的事,你偷偷想过但还没说的?",
        "我说哪句话会让你耳朵发烫?",
        "现在最想被我怎么撩?",
        "我穿成什么样,你会看到走不动道?",
    ],
    # 深度了解
    "deep": [
        "这周末完全归你安排,你想我们怎么过?",
        "你最近有什么没说出口的小情绪?",
        "我做的哪件事,让你觉得'被偏爱'了?",
        "你理想中五年后的我们,在过什么样的日子?",
        "最近哪一刻,你突然很想我?",
        "你最希望我更懂你哪一点?",
        "有没有一件小事,我一直没做、但你很想我做?",
        "你觉得我们之间最珍贵的默契是什么?",
        "上次我惹你不开心,你当时心里其实在想什么?",
        "什么样的瞬间,会让你觉得'还好有你'?",
    ],
    # 沙雕无厘头
    "silly": [
        "如果我变成一只狗,你会给我起什么名?",
        "给我们的爱情起个菜名,你选啥?",
        "如果只能用一种动物形容我,是啥?",
        "我的睡姿像哪种生物?",
        "世界末日,只能带我或者充电宝,你诚实选谁?",
        "给我编一个三个字的沙雕外号。",
        "我俩合体变成一道菜,叫什么名字?",
        "我最近做过最蠢、但你觉得最可爱的事是啥?",
        "用一个 emoji 总结今天的我。",
        "如果给我们的关系拍部电影,片名叫啥?",
    ],
}


def choose_flavor(seed: int) -> str:
    return FLAVORS[seed % len(FLAVORS)]


def pick_local(flavor: str, exclude: set[str], seed: int) -> str:
    bank = LOCAL_QUESTIONS[flavor]
    pool = [q for q in bank if q not in exclude] or bank
    return pool[seed % len(pool)]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_rules_daily_questions.py -v`
Expected: PASS(5 passed)

- [ ] **Step 5: 提交**

```bash
git add backend/app/rules/daily_questions.py backend/tests/test_rules_daily_questions.py
git commit -m "feat(daily): 每日一问本地题库(暧昧/深度/沙雕)+ 选题纯函数"
```

---

## Task 4: 火苗 DB 编排 `streak_service.py` + 接进 `/actions`

**Files:**
- Create: `backend/app/streak_service.py`
- Modify: `backend/app/routers/actions.py`（`do_action` 末尾 `db.commit()` 前加一行 touch)
- Test: `backend/tests/test_streak_service.py`

**Interfaces:**
- Consumes: `app.rules.streak`(Task 1)、`app.models.CoupleStreak/Event`(Task 2)、`app.config.settings.streak_utc_offset_hours`。
- Produces:
  - `slot_for(couple, user_id: int) -> str`
  - `get_or_create_row(db, couple_id: int) -> CoupleStreak`
  - `do_touch(db, couple, user_id: int) -> None`（读 `utcnow()`,touch 后写回行;**跨过 7/30/100/365 时落一条 system 庆祝事件**;**不 commit**,交给 router)
  - `build_view(db, couple, user_id: int) -> dict`（返回 `{count, i_did_today, partner_did_today, at_risk, lagging_user_id}`)

> **测试策略**:本任务用**隔离内存 session 直测 service 函数**(不走 HTTP);`/actions` 里接的 `do_touch` 一行,其端到端效果在 Task 5 用 `GET /daily` 验证(那时端点才存在)。

- [ ] **Step 1: 写失败测试** `backend/tests/test_streak_service.py`

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_streak_service.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'app.streak_service'`)

- [ ] **Step 3: 写实现** `backend/app/streak_service.py`

```python
"""火苗的 DB 编排：行↔纯函数 state 转换、槽位、touch/view + 里程碑事件。事务由 router 掌管（不 commit）。"""

from app.config import settings
from app.models import CoupleStreak, Event
from app.rules import streak
from app.time_utils import utcnow

_STATE_KEYS = ("count", "last_both_day", "a_active_day", "b_active_day", "rescue_day")

MILESTONES = {7, 30, 100, 365}
_MILESTONE_TEXT = {
    7: "🔥 火苗满 7 天啦——一周没断，这份坚持有点甜。",
    30: "🔥 火苗 30 天！整整一个月天天见，厉害了。",
    100: "🔥 火苗破 100 天！这是要处成传说啊。",
    365: "🔥 火苗满一年！365 天没断过，离谱又浪漫。",
}


def slot_for(couple, user_id: int) -> str:
    return "a" if couple.user_a_id == user_id else "b"


def get_or_create_row(db, couple_id: int) -> CoupleStreak:
    row = db.get(CoupleStreak, couple_id)
    if row is None:
        row = CoupleStreak(couple_id=couple_id, count=0)
        db.add(row)
        db.flush()
    return row


def _row_to_state(row: CoupleStreak) -> dict:
    return {k: getattr(row, k) for k in _STATE_KEYS}


def _apply_state(row: CoupleStreak, state: dict) -> None:
    for k in _STATE_KEYS:
        setattr(row, k, state[k])


def _today() -> "object":
    return streak.today_for(utcnow(), settings.streak_utc_offset_hours)


def do_touch(db, couple, user_id: int) -> None:
    row = get_or_create_row(db, couple.id)
    before = row.count
    _apply_state(row, streak.touch(_row_to_state(row), slot_for(couple, user_id), _today()))
    after = row.count
    if after > before and after in MILESTONES:  # 跨过里程碑 → 落一条系统庆祝
        db.add(
            Event(
                couple_id=couple.id,
                actor_user_id=None,
                kind="system",
                content=_MILESTONE_TEXT[after],
            )
        )


def build_view(db, couple, user_id: int) -> dict:
    row = get_or_create_row(db, couple.id)
    v = streak.view(_row_to_state(row), slot_for(couple, user_id), _today())
    lag = v.pop("lagging_slot")
    lagging_user_id = None
    if lag == "a":
        lagging_user_id = couple.user_a_id
    elif lag == "b":
        lagging_user_id = couple.user_b_id
    return {**v, "lagging_user_id": lagging_user_id}
```

- [ ] **Step 4: 接进 `/actions`** —— `backend/app/routers/actions.py`

顶部 import 区加:

```python
from app import streak_service
```

在 `do_action` 里,把现有

```python
    db.commit()
    db.refresh(action_event)
    return _bundle(db, couple.id, action_event, new_stats)
```

改成(在 commit 前加一行 touch):

```python
    streak_service.do_touch(db, couple, user.id)
    db.commit()
    db.refresh(action_event)
    return _bundle(db, couple.id, action_event, new_stats)
```

- [ ] **Step 5: 跑测试确认通过 + 回归**

Run: `cd backend && .venv/bin/python -m pytest tests/test_streak_service.py tests/test_actions.py -v`
Expected: PASS(新 4 + 原有 test_actions 全过——里程碑事件 `parent_event_id=None`,不进动作 bundle,不影响现有断言)

- [ ] **Step 6: 提交**

```bash
git add backend/app/streak_service.py backend/app/routers/actions.py backend/tests/test_streak_service.py
git commit -m "feat(streak): DB 编排 + /actions 触发火苗结算"
```

---

## Task 5: 每日一问路由 `routers/daily.py`(`GET /daily` + `POST /daily/answer`)

**Files:**
- Create: `backend/app/routers/daily.py`
- Modify: `backend/app/main.py`（注册 router)
- Test: `backend/tests/test_daily.py`

**Interfaces:**
- Consumes: `streak_service`(Task 4)、`rules.daily_questions`(Task 3)、`models.DailyQuestion/DailyAnswer/Event/Couple/User`、`deps.get_current_user/get_active_couple`。
- Produces(HTTP,两个端点返回同一形状):
  ```json
  {
    "question": {"text": "...", "flavor": "silly"},
    "my_answer": "..." | null,
    "partner_answer": "..." | null,
    "both_answered": false,
    "streak": {"count": 0, "i_did_today": false, "partner_did_today": false, "at_risk": false, "lagging_user_id": null}
  }
  ```
  - `partner_answer` 仅在 `both_answered` 时非 null;双方答完时往 `events` 落 `daily_qa`(父题 + 两答子事件)。

- [ ] **Step 1: 写失败测试** `backend/tests/test_daily.py`

```python
from tests.conftest import auth_headers


def _pair(client):
    ha = auth_headers(client, "alice")
    code = client.post("/couples", headers=ha).json()["pair_code"]
    hb = auth_headers(client, "bob")
    client.post("/couples/join", headers=hb, json={"pair_code": code})
    return ha, hb


def test_get_daily_generates_question_and_streak(client):
    ha, hb = _pair(client)
    r = client.get("/daily", headers=ha)
    assert r.status_code == 200
    body = r.json()
    assert body["question"]["text"]                 # 有题
    assert body["question"]["flavor"] in ("ambiguous", "deep", "silly")
    assert body["my_answer"] is None
    assert body["both_answered"] is False
    assert body["streak"]["count"] == 0


def test_get_daily_is_stable_same_day(client):
    ha, hb = _pair(client)
    q1 = client.get("/daily", headers=ha).json()["question"]["text"]
    q2 = client.get("/daily", headers=hb).json()["question"]["text"]  # 同一对、同一天
    assert q1 == q2                                  # 双方看到同一道题、且不变


def test_answer_waits_until_both_then_unlocks(client):
    ha, hb = _pair(client)
    client.get("/daily", headers=ha)                 # 生成题
    # alice 先答
    ra = client.post("/daily/answer", headers=ha, json={"content": "爱丽丝的答案", "client_key": "a1"})
    assert ra.status_code == 200
    a_body = ra.json()
    assert a_body["my_answer"] == "爱丽丝的答案"
    assert a_body["both_answered"] is False
    assert a_body["partner_answer"] is None          # 对方还没答，看不到
    # bob 后答 → 解锁
    rb = client.post("/daily/answer", headers=hb, json={"content": "鲍勃的答案", "client_key": "b1"})
    b_body = rb.json()
    assert b_body["both_answered"] is True
    assert b_body["my_answer"] == "鲍勃的答案"
    assert b_body["partner_answer"] == "爱丽丝的答案"  # 解锁后能看到对方
    # alice 再拉，也解锁了
    a2 = client.get("/daily", headers=ha).json()
    assert a2["both_answered"] is True
    assert a2["partner_answer"] == "鲍勃的答案"


def test_answer_is_idempotent(client):
    ha, hb = _pair(client)
    client.get("/daily", headers=ha)
    first = client.post("/daily/answer", headers=ha, json={"content": "答案一", "client_key": "a1"}).json()
    again = client.post("/daily/answer", headers=ha, json={"content": "答案二", "client_key": "a1"}).json()
    assert again["my_answer"] == "答案一"            # 首答锁定，不被覆盖


def test_reveal_drops_daily_qa_event_into_timeline(client):
    ha, hb = _pair(client)
    client.get("/daily", headers=ha)
    client.post("/daily/answer", headers=ha, json={"content": "AAA", "client_key": "a1"})
    client.post("/daily/answer", headers=hb, json={"content": "BBB", "client_key": "b1"})
    feed = client.get("/events", headers=ha).json()
    qa = [e for e in feed["events"] if e["kind"] == "daily_qa"]
    assert len(qa) == 3                              # 1 父题 + 2 答
    parent = next(e for e in qa if e["parent_event_id"] is None)
    answers = [e for e in qa if e["parent_event_id"] == parent["id"]]
    assert {e["content"] for e in answers} == {"AAA", "BBB"}


def test_answering_counts_toward_streak(client):
    ha, hb = _pair(client)
    client.get("/daily", headers=ha)
    client.post("/daily/answer", headers=ha, json={"content": "x", "client_key": "a1"})
    client.post("/daily/answer", headers=hb, json={"content": "y", "client_key": "b1"})
    body = client.get("/daily", headers=ha).json()
    assert body["streak"]["count"] == 1             # 两人都答了 → 火苗起


def test_actions_also_bump_streak(client):
    # 用互动动作（非答题）端到端验证 Task 4 在 /actions 里接的 do_touch
    ha, hb = _pair(client)
    client.post("/actions", headers=ha, json={"action_type": "poke", "content": "", "client_key": "pa"})
    client.post("/actions", headers=hb, json={"action_type": "poke", "content": "", "client_key": "pb"})
    body = client.get("/daily", headers=ha).json()
    assert body["streak"]["count"] == 1


def test_requires_active_couple(client):
    h = auth_headers(client, "solo")
    assert client.get("/daily", headers=h).status_code == 409
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_daily.py -v`
Expected: FAIL(404,因为 `/daily` 还没注册)

- [ ] **Step 3: 写实现** `backend/app/routers/daily.py`

```python
"""每日一问：每对每天一道混味题；双方都答完才解锁对方答案，解锁时落 daily_qa 时间线。"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import streak_service
from app.config import settings
from app.db import get_db
from app.deps import get_active_couple, get_current_user
from app.models import Couple, DailyAnswer, DailyQuestion, Event, User
from app.rules import daily_questions, streak
from app.time_utils import utcnow

router = APIRouter(tags=["daily"])


class AnswerIn(BaseModel):
    content: str = Field("", max_length=1000)
    client_key: str


def _today():
    return streak.today_for(utcnow(), settings.streak_utc_offset_hours)


def _get_or_create_question(db: Session, couple: Couple) -> DailyQuestion:
    today = _today()
    q = (
        db.query(DailyQuestion)
        .filter(DailyQuestion.couple_id == couple.id, DailyQuestion.day == today)
        .first()
    )
    if q is not None:
        return q
    # 按天定味 + 避开最近若干天的题，避免短期重复
    seed = today.toordinal() + couple.id
    flavor = daily_questions.choose_flavor(seed)
    recent = {
        r.question
        for r in db.query(DailyQuestion)
        .filter(DailyQuestion.couple_id == couple.id)
        .order_by(DailyQuestion.day.desc())
        .limit(20)
        .all()
    }
    text = daily_questions.pick_local(flavor, recent, seed)
    q = DailyQuestion(couple_id=couple.id, day=today, question=text, flavor=flavor)
    db.add(q)
    db.flush()
    return q


def _answer_of(db: Session, question_id: int, user_id: int) -> DailyAnswer | None:
    return (
        db.query(DailyAnswer)
        .filter(DailyAnswer.question_id == question_id, DailyAnswer.user_id == user_id)
        .first()
    )


def _build_response(db: Session, couple: Couple, user: User, q: DailyQuestion) -> dict:
    partner_id = couple.user_b_id if couple.user_a_id == user.id else couple.user_a_id
    mine = _answer_of(db, q.id, user.id)
    partner = _answer_of(db, q.id, partner_id) if partner_id is not None else None
    both = mine is not None and partner is not None
    return {
        "question": {"text": q.question, "flavor": q.flavor},
        "my_answer": mine.content if mine else None,
        "partner_answer": partner.content if (both and partner) else None,
        "both_answered": both,
        "streak": streak_service.build_view(db, couple, user.id),
    }


@router.get("/daily")
def get_daily(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")
    q = _get_or_create_question(db, couple)
    resp = _build_response(db, couple, user, q)
    db.commit()  # 可能新建了题 / streak 行
    return resp


@router.post("/daily/answer")
def answer_daily(
    body: AnswerIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")
    q = _get_or_create_question(db, couple)

    existing = _answer_of(db, q.id, user.id)
    if existing is not None:
        resp = _build_response(db, couple, user, q)   # 幂等：首答锁定
        db.commit()
        return resp

    db.add(
        DailyAnswer(
            question_id=q.id, user_id=user.id, content=body.content, client_key=body.client_key
        )
    )
    db.flush()
    streak_service.do_touch(db, couple, user.id)      # 答题算有效互动

    # 若这是第二个答的人 → 双方齐了 → 落 daily_qa 时间线（只落一次）
    answers = db.query(DailyAnswer).filter(DailyAnswer.question_id == q.id).all()
    if len(answers) == 2:
        parent = Event(
            couple_id=couple.id,
            actor_user_id=None,
            kind="daily_qa",
            content=q.question,
            parent_event_id=None,
        )
        db.add(parent)
        db.flush()
        for a in answers:
            db.add(
                Event(
                    couple_id=couple.id,
                    actor_user_id=a.user_id,
                    kind="daily_qa",
                    content=a.content,
                    parent_event_id=parent.id,
                )
            )

    resp = _build_response(db, couple, user, q)
    db.commit()
    return resp
```

- [ ] **Step 4: 注册 router** —— `backend/app/main.py`

```python
from app.routers import actions, auth, avatars, couples, daily, events
```

并加一行:

```python
app.include_router(daily.router)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_daily.py -v`
Expected: PASS(8 passed)

- [ ] **Step 6: 全后端回归**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 全过

- [ ] **Step 7: 提交**

```bash
git add backend/app/routers/daily.py backend/app/main.py backend/tests/test_daily.py
git commit -m "feat(daily): GET /daily + POST /daily/answer(双答解锁 + daily_qa 时间线)"
```

---

## Task 6:(可选,最低优先)续火 `POST /streak/rescue`

> **可砍**:排期紧就跳过整个 Task 6,只保留 at_risk 警告。砍掉不影响其它任务。

**Files:**
- Modify: `backend/app/streak_service.py`（加 `do_rescue`)
- Modify: `backend/app/routers/daily.py`（加一个端点)
- Test: `backend/tests/test_daily.py`（追加)

**Interfaces:**
- Consumes: `rules.streak.can_rescue/rescue`、`streak_service.do_rescue`、`CoupleStats`(扣亲密)。
- Produces:
  - `streak_service.do_rescue(db, couple, user_id: int) -> bool`（可救则应用并 True,否则 False;不扣数值、不 commit)
  - `POST /streak/rescue` → 成功返回 `build_view` 结果;不可救返回 409;扣 `CoupleStats.stats["intimacy"]` 固定 5 点。

- [ ] **Step 1: 写失败测试**(追加到 `backend/tests/test_daily.py`)

```python
def test_rescue_rejected_when_not_broken(client):
    ha, hb = _pair(client)
    client.get("/daily", headers=ha)
    r = client.post("/streak/rescue", headers=ha)
    assert r.status_code == 409          # 火苗没断，没得救
```

> 说明:构造"正好漏一天"的断火状态需要跨天,属 `rules/streak` 已覆盖的纯逻辑;这里只验证 router 的"未断则拒绝"接线。跨天成功路径由 Task 1 的 `test_rescue_*` 保证。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_daily.py::test_rescue_rejected_when_not_broken -v`
Expected: FAIL(404)

- [ ] **Step 3a: 给 `streak_service.py` 加 `do_rescue`**(接在 `do_touch` 后)

```python
def do_rescue(db, couple, user_id: int) -> bool:
    """尝试续火：可救则应用并返回 True，否则 False。不扣数值、不 commit。"""
    row = get_or_create_row(db, couple.id)
    today = _today()
    state = _row_to_state(row)
    if not streak.can_rescue(state, today):
        return False
    _apply_state(row, streak.rescue(state, today))
    return True
```

- [ ] **Step 3b: 给 `routers/daily.py` 加端点**(顶部 import 里的 `from app.models import ...` 追加 `CoupleStats`)

```python
_RESCUE_INTIMACY_COST = 5


@router.post("/streak/rescue")
def rescue_streak(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    couple = get_active_couple(db, user)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no active couple")
    if not streak_service.do_rescue(db, couple, user.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "cannot rescue")
    cs = db.get(CoupleStats, couple.id)
    if cs is not None:
        s = dict(cs.stats)
        s["intimacy"] = max(0, s.get("intimacy", 0) - _RESCUE_INTIMACY_COST)
        cs.stats = s
    view = streak_service.build_view(db, couple, user.id)
    db.commit()
    return view
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_daily.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/daily.py backend/tests/test_daily.py
git commit -m "feat(streak): 续火端点 POST /streak/rescue(扣亲密补救)"
```

---

## Task 7: 前端 API + `useDaily` hook

**Files:**
- Modify: `frontend/src/api/types.ts`（`EventKind` 加 `'daily_qa'`;加 `StreakView`/`DailyResponse`)
- Create: `frontend/src/api/daily.ts`
- Create: `frontend/src/hooks/useDaily.ts`
- Test: `frontend/src/hooks/useDaily.test.tsx`

**Interfaces:**
- Produces:
  - `StreakView { count:number; i_did_today:boolean; partner_did_today:boolean; at_risk:boolean; lagging_user_id:number|null }`
  - `DailyResponse { question:{text:string;flavor:string}; my_answer:string|null; partner_answer:string|null; both_answered:boolean; streak:StreakView }`
  - `getDaily(): Promise<DailyResponse>`、`postDailyAnswer(content, client_key): Promise<DailyResponse>`
  - `useDaily(coupleId): { data, isLoading, answer, isAnswering }`

- [ ] **Step 1: 加类型** —— `frontend/src/api/types.ts`

把

```typescript
export type EventKind = 'action' | 'ai_reaction' | 'real_response' | 'system'
```

改成

```typescript
export type EventKind = 'action' | 'ai_reaction' | 'real_response' | 'system' | 'daily_qa'
```

文件末尾追加:

```typescript
export interface StreakView {
  count: number
  i_did_today: boolean
  partner_did_today: boolean
  at_risk: boolean
  lagging_user_id: number | null
}
export interface DailyResponse {
  question: { text: string; flavor: string }
  my_answer: string | null
  partner_answer: string | null
  both_answered: boolean
  streak: StreakView
}
```

- [ ] **Step 2: 写 API 封装** —— `frontend/src/api/daily.ts`

```typescript
import { apiRequest } from './client'
import { DailyResponse } from './types'

export function getDaily() {
  return apiRequest<DailyResponse>('GET', '/daily')
}
export function postDailyAnswer(content: string, client_key: string) {
  return apiRequest<DailyResponse>('POST', '/daily/answer', { content, client_key })
}
```

- [ ] **Step 3: 写失败测试** —— `frontend/src/hooks/useDaily.test.tsx`

```tsx
import { describe, it, expect } from 'vitest'
import { ReactNode } from 'react'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import { useDaily } from './useDaily'

// renderHook 需要一个包裹组件；utils.tsx 的 renderWithProviders 是给 render() 用的，
// 这里自带一个只含 QueryClient 的 wrapper。
function wrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

const base = {
  question: { text: '今天想我了吗?', flavor: 'deep' },
  my_answer: null,
  partner_answer: null,
  both_answered: false,
  streak: { count: 3, i_did_today: false, partner_did_today: false, at_risk: true, lagging_user_id: 7 },
}

describe('useDaily', () => {
  it('拉取今日一问 + 火苗', async () => {
    server.use(http.get('/api/daily', () => HttpResponse.json(base)))
    const { result } = renderHook(() => useDaily(1), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.data?.question.text).toBe('今天想我了吗?'))
    expect(result.current.data?.streak.count).toBe(3)
  })

  it('提交答案后更新缓存', async () => {
    server.use(
      http.get('/api/daily', () => HttpResponse.json(base)),
      http.post('/api/daily/answer', () => HttpResponse.json({ ...base, my_answer: '想了' })),
    )
    const { result } = renderHook(() => useDaily(1), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.data).toBeTruthy())
    await act(async () => {
      await result.current.answer('想了')
    })
    await waitFor(() => expect(result.current.data?.my_answer).toBe('想了'))
  })
})
```

- [ ] **Step 4: 跑测试确认失败**

Run: `pnpm -C frontend exec vitest run src/hooks/useDaily.test.tsx`
Expected: FAIL(找不到 `./useDaily`)

- [ ] **Step 5: 写 hook** —— `frontend/src/hooks/useDaily.ts`

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getDaily, postDailyAnswer } from '../api/daily'
import { ApiError } from '../api/client'
import { DailyResponse } from '../api/types'
import { randomId } from '../uuid'

export function dailyKey(coupleId: number) {
  return ['daily', coupleId] as const
}

export function useDaily(coupleId: number) {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: dailyKey(coupleId),
    queryFn: getDaily,
    refetchInterval: 20000, // 对方答完时自动解锁
  })
  const mutation = useMutation({
    // client_key 放进 variables，重试时复用同一个 key → 幂等（别在 mutationFn 里现生成）
    mutationFn: (v: { content: string; key: string }) => postDailyAnswer(v.content, v.key),
    retry: (n, e) => n < 2 && !(e instanceof ApiError),
    retryDelay: 200,
    onSuccess: (resp: DailyResponse) => qc.setQueryData(dailyKey(coupleId), resp),
  })
  return {
    data: query.data,
    isLoading: query.isLoading,
    answer: (content: string) => mutation.mutateAsync({ content, key: randomId() }),
    isAnswering: mutation.isPending,
  }
}
```

- [ ] **Step 6: 跑测试确认通过**

Run: `pnpm -C frontend exec vitest run src/hooks/useDaily.test.tsx`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add frontend/src/api/types.ts frontend/src/api/daily.ts frontend/src/hooks/useDaily.ts frontend/src/hooks/useDaily.test.tsx
git commit -m "feat(daily): 前端 API + useDaily hook(轮询解锁)"
```

---

## Task 8: 火苗条 + 今日一问卡 + 接进首页

**Files:**
- Create: `frontend/src/home/FireBar.tsx`
- Create: `frontend/src/home/DailyQuestionCard.tsx`
- Create: `frontend/src/home/DailyQuestionCard.test.tsx`
- Modify: `frontend/src/home/HomeScreen.tsx`（顶部插入两个组件)

**Interfaces:**
- Consumes: `useDaily`(Task 7)、`DailyResponse/StreakView`。
- Produces: `<FireBar streak={StreakView} />`、`<DailyQuestionCard coupleId={number} />`（内部用 `useDaily`）。

- [ ] **Step 1: 写火苗条** —— `frontend/src/home/FireBar.tsx`

```tsx
import { StreakView } from '../api/types'

export function FireBar({ streak }: { streak: StreakView }) {
  const { count, at_risk, i_did_today, partner_did_today } = streak
  let hint = ''
  if (at_risk && !i_did_today) hint = '快断了!今天还没露面'
  else if (at_risk && i_did_today && !partner_did_today) hint = '今天你搞定了,就等 TA'
  return (
    <div className={`fire-bar${at_risk ? ' at-risk' : ''}`} role="status">
      <span className="fire-emoji" aria-hidden>🔥</span>
      <b>{count} 天</b>
      {hint && <span className="fire-hint">· {hint}</span>}
    </div>
  )
}
```

- [ ] **Step 2: 写失败测试** —— `frontend/src/home/DailyQuestionCard.test.tsx`

```tsx
import { describe, it, expect } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { DailyQuestionCard } from './DailyQuestionCard'

const q = { question: { text: '今晚想干嘛?', flavor: 'ambiguous' }, streak: { count: 1, i_did_today: false, partner_did_today: false, at_risk: false, lagging_user_id: null } }

describe('DailyQuestionCard', () => {
  it('未答:显示题目和输入框', async () => {
    server.use(http.get('/api/daily', () => HttpResponse.json({ ...q, my_answer: null, partner_answer: null, both_answered: false })))
    renderWithProviders(<DailyQuestionCard coupleId={1} />)
    await waitFor(() => expect(screen.getByText('今晚想干嘛?')).toBeTruthy())
    expect(screen.getByRole('textbox')).toBeTruthy()
  })

  it('已答未解锁:显示等 TA', async () => {
    server.use(http.get('/api/daily', () => HttpResponse.json({ ...q, my_answer: '睡觉', partner_answer: null, both_answered: false })))
    renderWithProviders(<DailyQuestionCard coupleId={1} />)
    await waitFor(() => expect(screen.getByText(/就等 TA/)).toBeTruthy())
  })

  it('双方解锁:并排显示两人答案', async () => {
    server.use(http.get('/api/daily', () => HttpResponse.json({ ...q, my_answer: '睡觉', partner_answer: '想你', both_answered: true })))
    renderWithProviders(<DailyQuestionCard coupleId={1} />)
    await waitFor(() => expect(screen.getByText('想你')).toBeTruthy())
    expect(screen.getByText('睡觉')).toBeTruthy()
  })
})
```

- [ ] **Step 3: 跑测试确认失败**

Run: `pnpm -C frontend exec vitest run src/home/DailyQuestionCard.test.tsx`
Expected: FAIL(找不到 `./DailyQuestionCard`)

- [ ] **Step 4: 写今日一问卡** —— `frontend/src/home/DailyQuestionCard.tsx`

```tsx
import { useState } from 'react'
import { useDaily } from '../hooks/useDaily'

export function DailyQuestionCard({ coupleId }: { coupleId: number }) {
  const { data, answer, isAnswering } = useDaily(coupleId)
  const [draft, setDraft] = useState('')
  if (!data) return null

  return (
    <div className="daily-card">
      <div className="daily-title">📮 今日一问</div>
      <div className="daily-q">{data.question.text}</div>

      {data.both_answered ? (
        <div className="daily-reveal stack" style={{ gap: 6 }}>
          <div className="daily-ans mine"><b>你:</b> {data.my_answer}</div>
          <div className="daily-ans partner"><b>TA:</b> {data.partner_answer}</div>
        </div>
      ) : data.my_answer != null ? (
        <div className="daily-waiting">✅ 你答完啦,就等 TA 了…</div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            const t = draft.trim()
            if (t) answer(t).then(() => setDraft(''))
          }}
        >
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="写下你的答案，答完才能看 TA 的~"
            rows={2}
          />
          <button type="submit" disabled={isAnswering || !draft.trim()}>
            {isAnswering ? '发送中…' : '答一个'}
          </button>
        </form>
      )}
    </div>
  )
}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pnpm -C frontend exec vitest run src/home/DailyQuestionCard.test.tsx`
Expected: PASS(3 passed)

- [ ] **Step 6: 接进首页** —— `frontend/src/home/HomeScreen.tsx`

顶部 import 追加:

```tsx
import { FireBar } from './FireBar'
import { DailyQuestionCard } from './DailyQuestionCard'
import { useDaily } from '../hooks/useDaily'
```

在 `HomeScreen` 组件体里(已有 `const feed = useFeed(coupleId)` 附近)加:

```tsx
  const daily = useDaily(coupleId)
```

把 `return` 里的

```tsx
      <div className="screenview-body pad stack" style={{ gap: 14 }}>
        <StatDashboard coupleId={coupleId} />
```

改成(在 `StatDashboard` 之上插入火苗条 + 今日一问卡):

```tsx
      <div className="screenview-body pad stack" style={{ gap: 14 }}>
        {daily.data && <FireBar streak={daily.data.streak} />}
        <DailyQuestionCard coupleId={coupleId} />
        <StatDashboard coupleId={coupleId} />
```

- [ ] **Step 7: 补默认 `/api/daily` handler**(必做)—— `frontend/src/test/handlers.ts`

首页现在会拉 `/api/daily`,凡是渲染 `HomeScreen`/`MainShell`/`App` 的现有测试都会打这个请求,必须有默认 handler,否则它们会挂。`handlers.ts` 顶部已 `import { http, HttpResponse } from 'msw'`。在默认 `handlers` 数组里(`/api/events` 那条后面)加:

```typescript
  http.get('/api/daily', () =>
    HttpResponse.json({
      question: { text: '今天过得咋样?', flavor: 'deep' },
      my_answer: null,
      partner_answer: null,
      both_answered: false,
      streak: { count: 0, i_did_today: false, partner_did_today: false, at_risk: false, lagging_user_id: null },
    }),
  ),
```

- [ ] **Step 8: 类型检查 + 首页/回归测试**

Run: `pnpm -C frontend exec tsc --noEmit && pnpm -C frontend exec vitest run src/home src/App.test.tsx`
Expected: 类型无错;首页与 App 测试全过。

- [ ] **Step 9: 提交**

```bash
git add frontend/src/home/FireBar.tsx frontend/src/home/DailyQuestionCard.tsx frontend/src/home/DailyQuestionCard.test.tsx frontend/src/home/HomeScreen.tsx frontend/src/test/handlers.ts
git commit -m "feat(home): 火苗条 + 今日一问卡(三态)接进首页"
```

---

## Task 9: 聊天时间线渲染 `daily_qa`

**Files:**
- Modify: `frontend/src/chat/ChatScreen.tsx`（识别 `kind==='daily_qa'` 渲染问答卡)
- Test: `frontend/src/chat/ChatScreen.test.tsx`（追加一条)

**Interfaces:**
- Consumes: `GameEvent`(已含 `kind:'daily_qa'`,Task 7 已加类型)。
- Produces:时间线里 `daily_qa` 父事件渲染成"📮 今日一问"标题卡,其子事件(按 `parent_event_id`)渲染成两条答案,按 `actor_user_id` 上色/左右分。

- [ ] **Step 1: 写失败测试** —— 在 `frontend/src/chat/ChatScreen.test.tsx` 末尾追加(该文件顶部已 import `screen`/`http`/`HttpResponse`/`server`/`renderWithProviders`/`test`/`expect`)

```tsx
test('renders a daily_qa card with both answers', async () => {
  server.use(
    http.get('/api/events', () =>
      HttpResponse.json({
        events: [
          { id: 100, couple_id: 1, actor_user_id: null, kind: 'daily_qa', action_type: null, content: '今天想我了吗?', parent_event_id: null, created_at: 't' },
          { id: 101, couple_id: 1, actor_user_id: 1, kind: 'daily_qa', action_type: null, content: '想了', parent_event_id: 100, created_at: 't' },
          { id: 102, couple_id: 1, actor_user_id: 2, kind: 'daily_qa', action_type: null, content: '哼', parent_event_id: 100, created_at: 't' },
        ],
        stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 },
      }),
    ),
  )
  renderWithProviders(<ChatScreen coupleId={1} myUserId={1} partnerId={2} />)
  expect(await screen.findByText('今天想我了吗?')).toBeInTheDocument()
  expect(screen.getByText('想了')).toBeInTheDocument()
  expect(screen.getByText('哼')).toBeInTheDocument()
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm -C frontend exec vitest run src/chat/ChatScreen.test.tsx`
Expected: FAIL(问答卡文案渲染不出来)

- [ ] **Step 3: 写实现** —— `frontend/src/chat/ChatScreen.tsx`

**(a)** 紧挨现有 `const byId = new Map(events.map((e) => [e.id, e]))`(约第 46 行)下面,加一段:把 `daily_qa` 的答案子事件按父题归组。

```tsx
  // daily_qa：答案子事件按父题 id 归组，父题出卡时并入渲染
  const qaChildren = new Map<number, GameEvent[]>()
  for (const e of events) {
    if (e.kind === 'daily_qa' && e.parent_event_id != null) {
      const arr = qaChildren.get(e.parent_event_id) ?? []
      arr.push(e)
      qaChildren.set(e.parent_event_id, arr)
    }
  }
```

**(b)** 在 `renderEvent` 函数体最前面(现有 `if (ev.kind === 'system')` 之前)加一个分支:父题出问答卡、子答案 `return null`(已并入父卡)。

```tsx
    if (ev.kind === 'daily_qa') {
      if (ev.parent_event_id != null) return null // 子答案并入父卡渲染
      const answers = qaChildren.get(ev.id) ?? []
      return (
        <div key={ev.id} className="qa-card">
          <div className="qa-title">📮 今日一问</div>
          <div className="qa-q">{ev.content}</div>
          {answers.map((a) => (
            <div key={a.id} className={`qa-a ${a.actor_user_id === myUserId ? 'mine' : 'partner'}`}>
              {a.content}
            </div>
          ))}
        </div>
      )
    }
```

（`myUserId`、`GameEvent`、`events` 均是本组件已有的 prop / import,无需新增。)

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm -C frontend exec vitest run src/chat/ChatScreen.test.tsx`
Expected: PASS(含新增 `renders a daily_qa card with both answers`)

- [ ] **Step 5: 全前端回归 + 类型检查**

Run: `pnpm -C frontend exec tsc --noEmit && pnpm -C frontend exec vitest run`
Expected: 全过

- [ ] **Step 6: 提交**

```bash
git add frontend/src/chat/ChatScreen.tsx frontend/src/chat/ChatScreen.test.tsx
git commit -m "feat(chat): 时间线渲染 daily_qa 问答卡"
```

---

## Task 10: 收尾——README + 端到端手测

**Files:**
- Modify: `README.md`（核心功能加"火苗 + 每日一问"一节)
- Modify: `docs/couple-playtest-checklist.md`（加两条自查)

- [ ] **Step 1: README 加一节** —— `README.md` 的"核心功能"区加:

```markdown
### 🔥 情侣火苗 + 每日一问
- **火苗**:两人**每天都露面**(任一互动或答题)才续上,连续天数越攒越高;一方完成、另一方没动时进入"就差你了"状态(将来接推送召回)。漏一天可花点亲密"续火"。
- **每日一问**:每天一道 AI 混味题(暧昧 / 深度 / 沙雕轮换),**双方都答完才解锁对方答案**——答完在等 TA,就是每天回来的理由。解锁后落进聊天时间线可回看。
```

- [ ] **Step 2: 手测清单加两条** —— `docs/couple-playtest-checklist.md` 末尾:

```markdown
- [ ] 两人各做一次互动/答题 → 首页火苗 🔥 从 0 变 1;只有一方动时保持 0。
- [ ] 各自答"今日一问":先答的一方看到"就等 TA";双方答完两边同时解锁、聊天里出现问答卡。
```

- [ ] **Step 3: 端到端手测(两设备/两隐身窗)**

启动:`./start.sh -d` → 打开 `http://localhost`。用两个号配对后:
1. A 答今日一问 → A 看到"✅ 就等 TA";B 首页今日一问卡显示未答。
2. B 答 → 两边刷新后都解锁、并排显示两人答案;两边聊天页出现"📮 今日一问"卡。
3. 两边首页火苗显示 `🔥 1 天`。

- [ ] **Step 4: 提交**

```bash
git add README.md docs/couple-playtest-checklist.md
git commit -m "docs: 火苗🔥+每日一问 功能说明与手测清单"
```

---

## 落地后(非本计划,后续 spec)

- **B — Web Push**:把 `streak.at_risk`/`lagging_user_id` 与"TA 答完了今日一问"变成真正的离线推送(PWA + service worker + 订阅端点)。HTTPS 由用户解决。
- **AI 出题**:在 `_get_or_create_question` 里,有 key 时先试 DeepSeek 按 flavor + 双方 persona 生成个性化题,失败/无 key 落 `pick_local`。接现有 `app/ai/` 客户端与额度兜底。
- **C — 养成升级 + 沙雕恋爱周报**:火苗里程碑(7/30/100/365)接 `Avatar.evolution` 解锁物;每周问答/互动汇总成可分享周报。
