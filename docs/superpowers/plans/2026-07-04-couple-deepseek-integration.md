# 接 DeepSeek —— 活的分身回应 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `scold`(骂) / `chat`(聊天) 两个动作的确定性 stub 换成真 DeepSeek 调用，让分身用对方的人设 + 此刻心情 + 最近对话真人般沙雕地回应——同步返回、零前端改动、失败也可爱。

**Architecture:** 三层拆分放在 `app/ai/`：`prompt.py`（纯函数拼 messages）→ `client.py`（httpx 封装 DeepSeek，抛 `AIError`）→ `deepseek.py`（编排 + 兜底，`generate_reaction` 返回 `(text, used_ai)`）。`app/routers/actions.py` 只加「查最近上下文」与「额度成功才扣」。额度从一步 `consume_ai_quota` 拆成 `ai_quota_available` + `record_ai_usage`。无 key / 超时 / 出错一律落地为 tone-aware 本地兜底文案，动作永远成立、数值绝不回滚。

**Tech Stack:** FastAPI · SQLAlchemy · pydantic-settings · **httpx**（已在 `requirements.txt`，DeepSeek 与 OpenAI 兼容）· pytest（`httpx.MockTransport` 离线测网络层）。

## Global Constraints

- **命令**：所有测试从 `backend/` 跑，用 `cd /Users/majh/Cursor/lucas/backend && .venv/bin/pytest <file> -v`。基线：全套 `57 passed`。每个任务结束必须全绿。
- **同步**：在 `POST /actions` 内同步等 DeepSeek，回应随 bundle 返回。**不改前端、不改 API 契约**。
- **离线可测铁律**：CI 不出网、不烧真 key。测试默认 `deepseek_api_key=""`（走本地兜底）；网络层用 `httpx.MockTransport`；AI 成功/失败在 router 层 monkeypatch `generate_reaction`。
- **兜底铁律**：无 key / 超时 / 非 200 / 空返回 → tone-aware 本地文案。**绝不 500、绝不空屏、绝不回滚数值**；数值结算 / 动作落库 / 幂等 / 安抚触发都先于 AI 结果。
- **本地兜底必须含 `persona.tone`**：`tests/test_actions.py::test_scold_produces_action_and_ai_reaction` 断言 `"毒舌" in reaction["content"]`（空 key 路径）——兜底文案沿用现 stub 模板（含 tone + 内容回显）。
- **额度只在 AI 真成功时扣**：`used_ai is True` 才 `record_ai_usage`。DeepSeek 挂了不烧用户当日 `daily_chat_cap`（默认 50）次。
- **AI 动作只有两个**：`AI_ACTIONS = {"scold", "chat"}`；其余 5 个（poke/feed_dogfood/hug/miss_you/apologize）维持本地模板，不动。
- **范围外（不做）**：人设扩写、AI 记忆压缩、进化、流式打字机、重试/退避/熔断。`memory_summary` 参数保留但恒为 `""`。
- **配置默认值**（`app/config.py`，env 可覆盖，key 只在服务端）：`deepseek_base_url="https://api.deepseek.com"`、`deepseek_model="deepseek-chat"`、`deepseek_timeout_seconds=8`、`deepseek_max_tokens=200`、`deepseek_temperature=1.3`、`deepseek_recent_context=10`。

---

## File Structure

**新建**
- `backend/app/ai/prompt.py` — 纯函数：`build_messages` + `_mood_hint` + `_system_prompt`。无网络/DB。
- `backend/app/ai/client.py` — httpx 封装：`AIError` + `chat_completion`。只调用+解析+抛错，不兜底。
- `backend/.env.example` — 文档：DeepSeek 及既有 env 变量。
- `backend/tests/test_ai_prompt.py` — prompt 纯函数单测。
- `backend/tests/test_ai_client.py` — client 网络层单测（MockTransport）。
- `backend/tests/test_ai_deepseek.py` — `generate_reaction` 编排/兜底单测。

**修改**
- `backend/app/config.py` — 加 6 个 `deepseek_*` 字段。
- `backend/app/ai/quota.py` — `consume_ai_quota` 拆成 `ai_quota_available` + `record_ai_usage`。
- `backend/app/ai/deepseek.py` — `generate_reaction` 改为编排真调用 + tone-aware 兜底，返回 `(str, bool)`。
- `backend/app/routers/actions.py` — 加 `_recent_context`、改额度调用、解包 tuple、成功才扣。
- `backend/tests/test_ai.py` — 迁移额度测试到新 API；T4 移除旧 stub 反应测试。
- `backend/tests/test_actions.py` — 更新 `test_over_quota` 的 monkeypatch 目标；加 AI 成功/失败集成测试。

---

## Task 1: Prompt 编排（纯函数）

新增 `app/ai/prompt.py`：把人设 + 数值心情 + 动作 + 最近对话拼成 DeepSeek `messages`。完全隔离——尚无调用方，只加测试，全套保持绿。

**Files:**
- Create: `backend/app/ai/prompt.py`
- Test: `backend/tests/test_ai_prompt.py`

**Interfaces:**
- Produces:
  - `build_messages(persona: dict, stats: dict, action_type: str, content: str, recent: list[dict]) -> list[dict]`
    —— `recent` 每条形如 `{"speaker": "对方"|"分身", "text": str}`，升序。返回 `[{"role","content"}, ...]`。
  - `_mood_hint(stats: dict) -> str`（内部，测试可直接调）。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_ai_prompt.py`:

```python
from app.ai.prompt import build_messages, _mood_hint

LOW = {"grievance": 0, "dogfood": 0, "miss": 0, "intimacy": 0}


def test_system_carries_tone_and_seed():
    msgs = build_messages(
        {"tone": "毒舌", "seed": "爱吃醋的小恶魔"}, LOW, "chat", "在吗", []
    )
    sys = msgs[0]
    assert sys["role"] == "system"
    assert "毒舌" in sys["content"]
    assert "爱吃醋的小恶魔" in sys["content"]


def test_scold_final_turn_marks_being_scolded():
    msgs = build_messages({"tone": "毒舌"}, LOW, "scold", "大猪蹄子", [])
    last = msgs[-1]
    assert last["role"] == "user"
    assert "大猪蹄子" in last["content"]
    assert "骂" in last["content"]


def test_chat_final_turn_is_raw_content():
    msgs = build_messages({"tone": "憨憨"}, LOW, "chat", "在吗", [])
    assert msgs[-1] == {"role": "user", "content": "在吗"}


def test_recent_renders_as_alternating_turns():
    recent = [
        {"speaker": "对方", "text": "你好"},
        {"speaker": "分身", "text": "哼"},
    ]
    msgs = build_messages({"tone": "毒舌"}, LOW, "chat", "在吗", recent)
    assert msgs[1] == {"role": "user", "content": "你好"}
    assert msgs[2] == {"role": "assistant", "content": "哼"}
    assert msgs[-1]["content"] == "在吗"


def test_missing_seed_still_builds_system():
    msgs = build_messages({"tone": "高冷"}, LOW, "chat", "hi", [])
    assert "高冷" in msgs[0]["content"]


def test_mood_hint_reflects_high_grievance():
    assert "委屈" in _mood_hint({"grievance": 70, "dogfood": 0, "miss": 0, "intimacy": 0})


def test_mood_hint_default_when_all_low():
    assert _mood_hint(LOW) == "你心情平常"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/majh/Cursor/lucas/backend && .venv/bin/pytest tests/test_ai_prompt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ai.prompt'`

- [ ] **Step 3: 写实现**

Create `backend/app/ai/prompt.py`:

```python
"""纯函数：把人设 + 数值心情 + 动作 + 最近对话拼成 DeepSeek messages。无网络/DB/时钟。"""

_RULES = (
    "无厘头、沙雕、始终在角色里，绝不承认自己是 AI，绝不长篇大论，"
    "回应控制在 1-3 句，中文口语。"
)


def _mood_hint(stats: dict) -> str:
    hints = []
    if stats.get("grievance", 0) >= 60:
        hints.append("你此刻有点委屈、带刺，想被哄")
    if stats.get("miss", 0) >= 60:
        hints.append("你很想念对方")
    if stats.get("intimacy", 0) >= 60:
        hints.append("你和对方很亲密、黏人")
    if stats.get("dogfood", 0) >= 60:
        hints.append("你刚被喂饱，满足慵懒")
    return "；".join(hints) if hints else "你心情平常"


def _system_prompt(persona: dict, stats: dict) -> str:
    tone = persona.get("tone", "沙雕")
    seed = (persona.get("seed") or "").strip()
    seed_line = seed if seed else "（对方还没细说，你自己发挥）"
    return (
        "你在扮演对方养的「分身宠物」——代表 TA 眼里的另一半。\n"
        f"你的基调是「{tone}」。人设：{seed_line}。\n"
        f"规则：{_RULES}\n"
        f"此刻状态：{_mood_hint(stats)}。"
    )


def build_messages(
    persona: dict,
    stats: dict,
    action_type: str,
    content: str,
    recent: list[dict],
) -> list[dict]:
    messages = [{"role": "system", "content": _system_prompt(persona, stats)}]
    for turn in recent:
        role = "user" if turn.get("speaker") == "对方" else "assistant"
        messages.append({"role": role, "content": turn.get("text", "")})
    final = f"（对方在骂你）{content}" if action_type == "scold" else content
    messages.append({"role": "user", "content": final})
    return messages
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /Users/majh/Cursor/lucas/backend && .venv/bin/pytest tests/test_ai_prompt.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/ai/prompt.py backend/tests/test_ai_prompt.py
git commit -m "feat(ai): prompt builder — persona/mood/recent-context into DeepSeek messages"
```

---

## Task 2: DeepSeek 客户端 + 配置

新增 `app/ai/client.py`（httpx 封装 + `AIError`）与 6 个 `deepseek_*` 配置字段，并写 `backend/.env.example`。仍无调用方——纯新增，全套保持绿。网络层用 `httpx.MockTransport` 注入，**不出网**。

**Files:**
- Create: `backend/app/ai/client.py`, `backend/.env.example`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_ai_client.py`

**Interfaces:**
- Consumes: `app.config.settings`（下列新字段）。
- Produces:
  - `class AIError(Exception)`
  - `chat_completion(messages: list[dict], *, http_client: httpx.Client | None = None) -> str`
    —— 成功返回回复文本；超时/连接错误/非 200/坏 JSON/空 choices/空文本 → raise `AIError`。`http_client` 仅供测试注入 `MockTransport`；生产不传，内部自建自关。

- [ ] **Step 1: 写失败测试（config）**

Modify `backend/app/config.py` 的测试先行——先加断言配置的测试。Create/append `backend/tests/test_ai_client.py`:

```python
import httpx
import pytest

from app.ai.client import AIError, chat_completion
from app.config import settings


def test_deepseek_settings_have_defaults():
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_model == "deepseek-chat"
    assert settings.deepseek_timeout_seconds == 8
    assert settings.deepseek_max_tokens == 200
    assert settings.deepseek_temperature == 1.3
    assert settings.deepseek_recent_context == 10


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


def test_chat_completion_parses_reply():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "喵喵"}}]})

    text = chat_completion([{"role": "user", "content": "hi"}], http_client=_client(handler))
    assert text == "喵喵"


def test_chat_completion_raises_on_non_200():
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(AIError):
        chat_completion([{"role": "user", "content": "hi"}], http_client=_client(handler))


def test_chat_completion_raises_on_empty_choices():
    def handler(request):
        return httpx.Response(200, json={"choices": []})

    with pytest.raises(AIError):
        chat_completion([{"role": "user", "content": "hi"}], http_client=_client(handler))


def test_chat_completion_raises_on_blank_content():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]})

    with pytest.raises(AIError):
        chat_completion([{"role": "user", "content": "hi"}], http_client=_client(handler))


def test_chat_completion_raises_on_timeout():
    def handler(request):
        raise httpx.TimeoutException("slow")

    with pytest.raises(AIError):
        chat_completion([{"role": "user", "content": "hi"}], http_client=_client(handler))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/majh/Cursor/lucas/backend && .venv/bin/pytest tests/test_ai_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ai.client'`（且 config 断言失败）

- [ ] **Step 3: 写实现 —— config**

Modify `backend/app/config.py`，在 `deepseek_api_key` 下方补字段：

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 生产用 MySQL，例如 mysql+pymysql://user:pass@host:3306/petgame
    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = "dev-secret-change-me"
    daily_chat_cap: int = 50
    deepseek_api_key: str = ""
    # 空 key = 走本地兜底（dev/CI 离线）。key 只在服务端，前端永不可见。
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: int = 8
    deepseek_max_tokens: int = 200
    deepseek_temperature: float = 1.3
    deepseek_recent_context: int = 10  # 喂进 prompt 的最近事件条数


settings = Settings()
```

- [ ] **Step 4: 写实现 —— client**

Create `backend/app/ai/client.py`:

```python
"""DeepSeek 调用封装（与 OpenAI 兼容）。只调用+解析+抛 AIError，不做兜底。"""

import httpx

from app.config import settings


class AIError(Exception):
    """DeepSeek 调用失败——上层据此落地本地兜底。"""


def _build_client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.deepseek_base_url,
        timeout=settings.deepseek_timeout_seconds,
    )


def chat_completion(messages: list[dict], *, http_client: httpx.Client | None = None) -> str:
    client = http_client or _build_client()
    try:
        try:
            resp = client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": settings.deepseek_model,
                    "messages": messages,
                    "max_tokens": settings.deepseek_max_tokens,
                    "temperature": settings.deepseek_temperature,
                    "stream": False,
                },
            )
        except httpx.HTTPError as e:  # 超时 / 连接错误等（TimeoutException 是其子类）
            raise AIError(str(e)) from e
        if resp.status_code != 200:
            raise AIError(f"status {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as e:
            raise AIError("bad json") from e
        choices = data.get("choices") or []
        if not choices:
            raise AIError("no choices")
        text = ((choices[0].get("message") or {}).get("content") or "").strip()
        if not text:
            raise AIError("empty content")
        return text
    finally:
        if http_client is None:
            client.close()
```

- [ ] **Step 5: 写 `.env.example`**

Create `backend/.env.example`:

```bash
# 复制成 .env 并按需填写。空值走内置默认（见 app/config.py）。
DATABASE_URL=sqlite:///./dev.db
JWT_SECRET=dev-secret-change-me
DAILY_CHAT_CAP=50

# DeepSeek —— 留空则 scold/chat 走本地兜底文案（离线）。填了才走真 AI。
# key 只在服务端，前端永不可见。
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TIMEOUT_SECONDS=8
DEEPSEEK_MAX_TOKENS=200
DEEPSEEK_TEMPERATURE=1.3
DEEPSEEK_RECENT_CONTEXT=10
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd /Users/majh/Cursor/lucas/backend && .venv/bin/pytest tests/test_ai_client.py -v`
Expected: PASS（6 passed）

- [ ] **Step 7: 提交**

```bash
git add backend/app/ai/client.py backend/app/config.py backend/.env.example backend/tests/test_ai_client.py
git commit -m "feat(ai): DeepSeek httpx client + config + env example"
```

---

## Task 3: 额度拆两步 + router 改用新 API（行为保持）

把 `consume_ai_quota`（查+扣一步）拆成 `ai_quota_available`（只查+每日重置）与 `record_ai_usage`（只 +1）。同步更新唯一两个调用方：router 与额度单测。此任务**保持原行为**（有额度→调 stub→记一次；无额度→兜底），`generate_reaction` 仍是旧 stub（下个任务才换）。全套保持绿。

**Files:**
- Modify: `backend/app/ai/quota.py`, `backend/app/routers/actions.py:7-8,92-100`, `backend/tests/test_ai.py`, `backend/tests/test_actions.py:67-75`

**Interfaces:**
- Consumes: `app.config.settings.daily_chat_cap`。
- Produces（取代 `consume_ai_quota`）:
  - `ai_quota_available(user: User, db) -> bool` —— 跨 UTC 日把 `ai_count` 归零并 commit；返回 `ai_count < daily_chat_cap`。**不 +1**。
  - `record_ai_usage(user: User, db) -> None` —— `ai_count += 1` 并 commit。

- [ ] **Step 1: 改额度单测（先失败）**

Modify `backend/tests/test_ai.py`：把 import 与两个额度测试换成新 API（**保留** `test_generate_reaction_is_deterministic_and_in_persona` 不动——旧 stub 仍在）。改后文件：

```python
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.deepseek import generate_reaction
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


def test_generate_reaction_is_deterministic_and_in_persona():
    persona = {"tone": "毒舌"}
    a = generate_reaction(persona, {"grievance": 0}, "scold", "大猪蹄子")
    b = generate_reaction(persona, {"grievance": 0}, "scold", "大猪蹄子")
    assert a == b  # deterministic — safe for CI
    assert "毒舌" in a
    assert "大猪蹄子" in a


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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/majh/Cursor/lucas/backend && .venv/bin/pytest tests/test_ai.py -v`
Expected: FAIL — `ImportError: cannot import name 'ai_quota_available' from 'app.ai.quota'`

- [ ] **Step 3: 写实现 —— quota**

Replace `backend/app/ai/quota.py` 全文：

```python
from app.config import settings
from app.models import User
from app.time_utils import utcnow


def ai_quota_available(user: User, db) -> bool:
    """应用每日重置（跨 UTC 日归零并 commit）；返回是否还在额度内。只查不加。"""
    today = utcnow().date()
    if user.ai_count_date != today:
        user.ai_count = 0
        user.ai_count_date = today
        db.add(user)
        db.commit()
    return user.ai_count < settings.daily_chat_cap


def record_ai_usage(user: User, db) -> None:
    """AI 真成功后计一次数。"""
    user.ai_count += 1
    db.add(user)
    db.commit()
```

- [ ] **Step 4: 写实现 —— router（行为保持）**

Modify `backend/app/routers/actions.py`：

import 行（第 8 行）：

```python
from app.ai.quota import ai_quota_available, record_ai_usage
```

`needs_ai` 分支（当前第 92-100 行）改为：

```python
    if needs_ai:
        if ai_quota_available(user, db):
            reaction_text = generate_reaction(
                pet.persona, new_stats, body.action_type, body.content, pet.memory_summary
            )
            record_ai_usage(user, db)
        else:
            reaction_text = random.choice(_AI_FALLBACK)
    else:
        reaction_text = local_reaction
```

- [ ] **Step 5: 改 `test_over_quota` 的 monkeypatch 目标**

Modify `backend/tests/test_actions.py:71`——把打桩目标从 `consume_ai_quota` 换成 `ai_quota_available`：

```python
def test_over_quota_falls_back_to_local(client, monkeypatch):
    ha, hb = _pair(client)
    import app.routers.actions as actions_mod

    monkeypatch.setattr(actions_mod, "ai_quota_available", lambda user, db: False)
    r = _act(client, hb, "scold", "k1", "大猪蹄子")
    assert r.status_code == 200  # never errors on quota exhaustion
    reaction = next(e for e in r.json()["events"] if e["kind"] == "ai_reaction")
    assert reaction["content"]  # a fallback line, not empty
```

- [ ] **Step 6: 跑相关测试 + 全套**

Run: `cd /Users/majh/Cursor/lucas/backend && .venv/bin/pytest tests/test_ai.py tests/test_actions.py tests/test_safety_valve.py -v`
Expected: PASS

Run 全套: `cd /Users/majh/Cursor/lucas/backend && .venv/bin/pytest -q`
Expected: `57 passed`（数目不变——纯迁移）

- [ ] **Step 7: 提交**

```bash
git add backend/app/ai/quota.py backend/app/routers/actions.py backend/tests/test_ai.py backend/tests/test_actions.py
git commit -m "refactor(ai): split quota into check + record (charge-on-success prep)"
```

---

## Task 4: 真 DeepSeek 集成 + 最近上下文 + 成功才扣（收官）

把 `generate_reaction` 改成编排 `build_messages` → `chat_completion`，返回 `(text, used_ai)`，无 key/出错落地 tone-aware 兜底。router 加 `_recent_context`、解包 tuple、**仅 `used_ai` 时 `record_ai_usage`**。这是让核心「有灵魂」的收官任务。全套保持绿（默认空 key → 兜底；成功/失败在 router 层 monkeypatch）。

**Files:**
- Modify: `backend/app/ai/deepseek.py`, `backend/app/routers/actions.py`, `backend/tests/test_ai.py`, `backend/tests/test_actions.py`
- Create: `backend/tests/test_ai_deepseek.py`

**Interfaces:**
- Consumes: `build_messages`（Task 1）、`chat_completion` / `AIError`（Task 2）、`ai_quota_available` / `record_ai_usage`（Task 3）、`settings.deepseek_recent_context`。
- Produces:
  - `generate_reaction(persona, stats, action_type, content, recent: list[dict], memory_summary: str = "") -> tuple[str, bool]`
    —— key 空 → `(兜底, False)`；调用成功 → `(AI 文本, True)`；`AIError` → `(兜底, False)`。**永不抛**。
  - router 内部 `_recent_context(db, couple_id, n) -> list[dict]`（`{"speaker","text"}` 升序，排除 `system`）。

- [ ] **Step 1: 写失败测试 —— deepseek 编排**

Create `backend/tests/test_ai_deepseek.py`:

```python
from app.ai.client import AIError
from app.ai.deepseek import generate_reaction
from app.config import settings

LOW = {"grievance": 0, "dogfood": 0, "miss": 0, "intimacy": 0}


def test_empty_key_falls_back_in_persona(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    text, used = generate_reaction({"tone": "毒舌"}, LOW, "scold", "大猪蹄子", [])
    assert used is False
    assert "毒舌" in text  # tone-aware 兜底


def test_uses_ai_when_key_present(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    monkeypatch.setattr("app.ai.deepseek.chat_completion", lambda messages: "哼，本汪偏要理你")
    text, used = generate_reaction({"tone": "毒舌"}, LOW, "chat", "在吗", [])
    assert used is True
    assert text == "哼，本汪偏要理你"


def test_ai_error_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")

    def boom(messages):
        raise AIError("down")

    monkeypatch.setattr("app.ai.deepseek.chat_completion", boom)
    text, used = generate_reaction({"tone": "高冷"}, LOW, "chat", "在吗", [])
    assert used is False
    assert "高冷" in text
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/majh/Cursor/lucas/backend && .venv/bin/pytest tests/test_ai_deepseek.py -v`
Expected: FAIL — `test_uses_ai_when_key_present` 报 `ValueError: too many values to unpack` 或旧 stub 返回 str（未按 tuple）。

- [ ] **Step 3: 写实现 —— deepseek**

Replace `backend/app/ai/deepseek.py` 全文：

```python
"""DeepSeek 分身反应：编排 prompt + 调用 + 兜底。返回 (文本, used_ai)，永不抛。"""

from app.ai.client import AIError, chat_completion
from app.ai.prompt import build_messages
from app.config import settings


def _fallback(persona: dict, action_type: str, content: str) -> str:
    """tone-aware 本地兜底（无 key / 出错时用）。含 persona.tone 与内容回显。"""
    tone = persona.get("tone", "沙雕")
    said = content.strip() if content else ""
    tail = f"「{said}」" if said else ""
    return f"[{tone}分身] 收到你的 {action_type}{tail}，哼，本尊可不吃这套~"


def generate_reaction(
    persona: dict,
    stats: dict,
    action_type: str,
    content: str,
    recent: list[dict],
    memory_summary: str = "",  # 本计划恒为 ""，保留向前兼容
) -> tuple[str, bool]:
    if not settings.deepseek_api_key:
        return _fallback(persona, action_type, content), False
    try:
        messages = build_messages(persona, stats, action_type, content, recent)
        return chat_completion(messages), True
    except AIError:
        return _fallback(persona, action_type, content), False
```

- [ ] **Step 4: 跑 deepseek 测试确认通过**

Run: `cd /Users/majh/Cursor/lucas/backend && .venv/bin/pytest tests/test_ai_deepseek.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 移除 `test_ai.py` 里失效的旧 stub 反应测试**

`generate_reaction` 现在需要 `recent` 且返回 tuple，`test_ai.py::test_generate_reaction_is_deterministic_and_in_persona` 已失效（其覆盖已由 `test_ai_deepseek.py` 承接，且 router 层 `test_scold_produces_action_and_ai_reaction` 仍守 tone-in-content）。Modify `backend/tests/test_ai.py`：删除该测试函数，并删掉不再使用的 `from app.ai.deepseek import generate_reaction`。改后 `test_ai.py` 只余两个额度测试 + `_session` + 其余 import。

- [ ] **Step 6: 写失败测试 —— router 集成（AI 成功/失败）**

Append 到 `backend/tests/test_actions.py`：

```python
def test_ai_success_uses_ai_text_and_charges(client, monkeypatch):
    ha, hb = _pair(client)
    import app.routers.actions as m

    charged = []
    monkeypatch.setattr(m, "generate_reaction", lambda *a, **k: ("哼，本汪偏要理你", True))
    monkeypatch.setattr(m, "record_ai_usage", lambda user, db: charged.append(1))
    r = _act(client, hb, "chat", "k1", "在吗")
    assert r.status_code == 200
    reaction = next(e for e in r.json()["events"] if e["kind"] == "ai_reaction")
    assert reaction["content"] == "哼，本汪偏要理你"
    assert charged == [1]  # 成功才扣，且只扣一次


def test_ai_failure_does_not_charge(client, monkeypatch):
    ha, hb = _pair(client)
    import app.routers.actions as m

    charged = []
    monkeypatch.setattr(m, "generate_reaction", lambda *a, **k: ("（分身充电中）", False))
    monkeypatch.setattr(m, "record_ai_usage", lambda user, db: charged.append(1))
    r = _act(client, hb, "chat", "k1", "在吗")
    assert r.status_code == 200
    reaction = next(e for e in r.json()["events"] if e["kind"] == "ai_reaction")
    assert reaction["content"] == "（分身充电中）"
    assert charged == []  # 失败不烧额度
    assert r.json()["stats"]  # 动作照样成立、数值已结算
```

- [ ] **Step 7: 跑测试确认失败**

Run: `cd /Users/majh/Cursor/lucas/backend && .venv/bin/pytest tests/test_actions.py -k "ai_success or ai_failure" -v`
Expected: FAIL — router 仍按旧 5 参 str 调用 / 无条件 `record_ai_usage`，`charged` 断言不符 或 `ValueError: too many values to unpack`。

- [ ] **Step 8: 写实现 —— router（最近上下文 + 解包 + 成功才扣）**

Modify `backend/app/routers/actions.py`：

顶部 import 补 `settings` 与 `Event`（`Event` 已在 `from app.models import ... Event ...`，确认在列）：

```python
from app.config import settings
```

在 `_bundle` 函数下方新增 helper：

```python
def _recent_context(db: Session, couple_id: int, n: int) -> list[dict]:
    """同 couple 最近 n 条事件（排除 system 噪音），升序，映射成 prompt 上下文。"""
    rows = (
        db.query(Event)
        .filter(Event.couple_id == couple_id, Event.kind != "system")
        .order_by(Event.id.desc())
        .limit(n)
        .all()
    )
    out = []
    for ev in reversed(rows):
        speaker = "对方" if ev.kind == "action" else "分身"
        text = ev.content or (f"（{ev.action_type}）" if ev.action_type else "")
        out.append({"speaker": speaker, "text": text})
    return out
```

`needs_ai` 分支（Task 3 留下的版本）改为：

```python
    if needs_ai:
        if ai_quota_available(user, db):
            recent = _recent_context(db, couple.id, settings.deepseek_recent_context)
            reaction_text, used_ai = generate_reaction(
                pet.persona, new_stats, body.action_type, body.content, recent, pet.memory_summary
            )
            if used_ai:
                record_ai_usage(user, db)
        else:
            reaction_text = random.choice(_AI_FALLBACK)
    else:
        reaction_text = local_reaction
```

> 注：`_recent_context` 在写入本次 `action_event` **之前**调用，故取到的是本动作之前的历史；本次动作作为 `build_messages` 的末轮，不重复进上下文。

- [ ] **Step 9: 跑全套确认通过**

Run: `cd /Users/majh/Cursor/lucas/backend && .venv/bin/pytest -q`
Expected: PASS —— `57 - 1(删除的 stub 测试) + 3(deepseek) + 2(router 集成) = 61 passed`

- [ ] **Step 10: 提交**

```bash
git add backend/app/ai/deepseek.py backend/app/routers/actions.py backend/tests/test_ai_deepseek.py backend/tests/test_ai.py backend/tests/test_actions.py
git commit -m "feat(ai): real DeepSeek reactions with recent context + charge-on-success fallback"
```

---

## Self-Review

**1. Spec coverage**（对照 `2026-07-04-couple-deepseek-integration-design.md`）
- §2 三层拆分：prompt(T1) / client(T2) / deepseek(T4) ✓；router 两处小改(T3 额度、T4 上下文+解包) ✓。
- §3 数据流（额度门→上下文→生成→成功才扣→落库）：T4 router 块 ✓。
- §4 Prompt（system 含 tone/seed/规则/心情；scold vs chat 末轮；recent 交替）：T1 ✓。
- §5 健壮性（无 key/超时/非 200/空 → 兜底；动作永成立；成功才扣拆两步）：T2 client 抛错 + T4 兜底 + T3 拆分 + T4 成功才扣 ✓。
- §6 配置 6 字段 + key 服务端：T2 ✓（+ `.env.example`）。
- §7 测试（prompt 纯函数 / client MockTransport / deepseek 三态 / quota 两函数 / router 空key绿+成功+失败）：T1/T2/T4/T3/T4 ✓。
- §8 不做：无 retry/记忆/进化/流式/扩写——计划未涉及 ✓。

**2. Placeholder scan**：无 TBD/TODO；每个改码步骤都有完整代码块与确切命令/预期。✓

**3. Type consistency**：
- `generate_reaction` 全程 `(persona, stats, action_type, content, recent, memory_summary="") -> tuple[str, bool]`（T4 定义、T4 router 调用、T4 deepseek 测试一致）。⚠️ 注意：T3 的 `test_ai.py` 仍以旧 4 参 str 调用旧 stub（T3 时 stub 未换），T4 Step 5 删除该测试——顺序正确，无悬空。
- `chat_completion(messages, *, http_client=None) -> str`（T2 定义、T4 deepseek 调用、T2 测试一致）✓。
- `ai_quota_available(user, db) -> bool` / `record_ai_usage(user, db) -> None`（T3 定义、T3+T4 router 调用、T3 测试、T4 router 集成 monkeypatch 一致）✓。
- `build_messages(persona, stats, action_type, content, recent)`（T1 定义、T4 deepseek 调用一致）✓。
- `_recent_context` 产出 `{"speaker","text"}`，与 `build_messages` 消费的 `recent` 形状一致 ✓。

**结论**：计划自洽，逐任务全绿，收官后 `61 passed`。
