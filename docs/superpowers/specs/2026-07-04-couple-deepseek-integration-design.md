# 接 DeepSeek —— 活的分身回应 设计

> **前置**：后端核心 + 前端核心已合并进 `main`。`scold`(骂) / `chat`(聊天) 两个动作目前走 `app/ai/deepseek.py` 的**确定性 stub**（不联网），其余 5 个动作走本地模板。本计划把这两个动作的 stub 换成**真 DeepSeek 调用 + prompt 编排**，让分身回应有灵魂、像本尊、够沙雕。

**一句话目标**：让「骂 / 聊天」时分身用**对方的人设 + 此刻心情 + 最近对话**真人般沙雕地回你——同步返回、零前端改动、失败也可爱。

---

## §1 目标 & 范围

**范围内**
- 把 `generate_reaction` 从确定性 stub 换成真 DeepSeek 调用。
- Prompt 编排：吃 `persona`(tone + seed) + 当前数值心情 + 本次动作内容 + 同 couple **最近 N 条对话上下文**（让聊天连贯）。
- 健壮兜底：超时 / 出错 / 无 key 一律落地为可爱本地文案，**绝不 500、绝不空屏、绝不回滚数值**。
- 全程离线可测（CI 不出网、不烧真 key）。

**范围外（各自留后续计划）**
- **人设扩写**：把「一句话种子」AI 扩写成丰满人设。
- **AI 记忆压缩**：`memory_summary` 的滚动摘要循环（本计划只用即时"最近 N 条"，不做 AI 摘要）。
- **进化**：`evolution` 影响向量 + 进化事件文案。
- **流式打字机**：非流式一次性返回（前端手感层已按有延迟设计，后续换数据源即可）。
- 其余 5 个本地动作（poke / feed_dogfood / hug / miss_you / apologize）维持本地模板。

**同步 & 契约不变**：在 `POST /actions` 里同步等 DeepSeek 返回，`ai_reaction` 事件随 bundle 一起回。前端 `LoadingBanter` 已建好、专门顶等待，**前端与 API 契约零改动**。

---

## §2 架构 —— 干净三层，router 几乎不动

把现在的单个 stub 拆成职责清晰的三块，都在 `app/ai/`：

### `app/ai/prompt.py` —— 纯函数，可单测、无网络、无 DB

```python
def build_messages(
    persona: dict,
    stats: dict,
    action_type: str,   # "scold" | "chat"
    content: str,
    recent: list[dict],  # 最近对话，见下方形状，升序
) -> list[dict]:
    ...
```

产出 DeepSeek `chat/completions` 的 `messages`：
1. `{"role": "system", "content": <人设 + 规则 + 心情提示>}`
2. 把 `recent` 渲染成交替历史轮次：对方 → `{"role":"user"}`，分身 → `{"role":"assistant"}`
3. 末轮 `{"role": "user", "content": <本次动作渲染>}`
   - `scold` → `f"（对方在骂你）{content}"`
   - `chat` → `content`（自由文本）

`recent` 每条形状（由 router 构造）：`{"speaker": "对方" | "分身", "text": str}`。

心情提示辅助（纯函数，阈值可调）：`_mood_hint(stats) -> str`，把 grievance/dogfood/miss/intimacy 翻成一句"此刻状态"（**不报数字**）：委屈高→带刺/撒娇讨哄；亲密高→黏人；狗粮足→满足慵懒；想念高→黏人想见。

### `app/ai/client.py` —— 薄 httpx 封装（`httpx` 已在 requirements）

```python
class AIError(Exception): ...

def chat_completion(messages: list[dict]) -> str:
    """POST {base_url}/chat/completions（DeepSeek 与 OpenAI 兼容）。
    超时 / 非 200 / 无 choices / 空文本 → raise AIError。成功 → 返回回复文本。"""
```

- 请求体：`{"model": settings.deepseek_model, "messages": ..., "max_tokens": ..., "temperature": ...}`。
- Header：`Authorization: Bearer {settings.deepseek_api_key}`。
- `timeout=settings.deepseek_timeout_seconds`。
- 只封"调用 + 解析 + 抛 AIError"，**不做兜底**（兜底在 deepseek.py）。

### `app/ai/deepseek.py` —— 编排 + 兜底，永不抛

```python
def generate_reaction(
    persona: dict,
    stats: dict,
    action_type: str,
    content: str,
    recent: list[dict],
    memory_summary: str = "",   # 本计划恒为 ""，保留向前兼容
) -> tuple[str, bool]:
    """返回 (回应文本, used_ai)。
    - key 空 → (本地兜底文案, False)
    - 真调用成功 → (AI 文本, True)
    - AIError → (本地兜底文案, False)
    永远返回 str，永不抛。"""
```

- `used_ai` **只有真 DeepSeek 成功返回时为 True**——router 据此决定是否扣额度（§5）。
- 本地兜底文案：deepseek.py 自带一组可爱短句（"分身正在充电，先甩你个白眼~" 之类），key 空 / 出错都用它。

### `app/routers/actions.py` —— 两处小改
1. **查最近上下文**：命中 `needs_ai` 时，查同 couple 最近 ~N 条事件（排除 `system` 噪音），升序，映射成 `recent` 形状（`action` kind → `"对方"`，`ai_reaction`/`real_response` → `"分身"`），传给 `generate_reaction`。
2. **额度改"成功才扣"**（§5）：不再"查+扣一步"，改成"够额度才真调，真调成功才 +1"。

---

## §3 数据流（一次 scold / chat，同步）

```
前端 POST /actions {action_type:"chat", content, client_key}
  → 幂等命中? → 直接回既有 bundle（不变）
  → 时间衰减 + apply_action → new_stats, needs_ai=True
  → 额度够? 否 → reaction = 额度满兜底（不调 AI、不扣）
           是 → 查最近 N 条 → generate_reaction(...)
                  → 成功 (text, True) → 扣额度 +1
                  → 兜底 (text, False) → 不扣
  → 写 action_event（kind=action）
  → 写 reaction_event（kind=ai_reaction, content=reaction, parent=action）
  → 委屈爆表? → 写 system 安抚事件（不变）
  → commit → 返回 bundle {events, stats}
前端 LoadingBanter 顶住等待 → 拿到 bundle → 展示回应 + 滚动数值
```

**关键不变量**：数值结算、动作落库、幂等、安抚触发都**先于**AI 结果，AI 只决定 `ai_reaction` 的文案。DeepSeek 挂了，动作照样成立、数值照样已结算。

---

## §4 Prompt 设计（这就是灵魂）

**system 消息**（拼接）：
- 角色框：「你在扮演 <name>——你是对方（keeper）养的『分身宠物』，代表 TA 眼里的另一半。」
- 基调：`persona.tone`（毒舌 / 憨憨 / 舔狗 / 高冷 / 中二）。
- 人设种子：`persona.seed`（捏分身时"一句话形容对方眼里的你"）。
- 硬规则：无厘头 / 沙雕、**始终在角色里、绝不出戏、绝不解释自己是 AI**、1-3 句、中文、口语化。
- 心情提示：`_mood_hint(stats)` 的一句话（不报数字）。

**历史轮次**：`recent` 渲染成 user/assistant 交替，给连贯性。

**末轮 user**：本次动作
- `scold`：`（对方在骂你）<content>` → 俏皮反怼 / 卖惨 / 嘴硬，别真吵架。
- `chat`：`<content>` → 自然接话，带性格梗。

（动作特定的语气引导可放进 system 尾部或末轮前缀，实现时择一，保持 prompt 可单测。）

---

## §5 健壮性 & 兜底（§7 交互底线）

| 情形 | 行为 |
|---|---|
| 无 key（dev / CI） | `generate_reaction` 直接返回 (本地兜底, False)，不出网 |
| 超时（默认 8s） | client 抛 `AIError` → 本地兜底文案 |
| 非 200 / 无 choices / 空文本 | client 抛 `AIError` → 本地兜底文案 |
| 额度到顶 | router 用现有 `_AI_FALLBACK`，不调 AI |

**铁律**：
- **动作永远成立**：数值已结算、动作事件已落库，AI 失败只把 `ai_reaction` 换成兜底文案。绝不 500、绝不空屏、绝不回滚数值。
- **额度只在 AI 真成功时扣**：把额度拆成两步——
  - `ai_quota_available(user, db) -> bool`：应用每日重置（跨 UTC 日归零并 commit），只查不加。
  - `record_ai_usage(user, db) -> None`：`ai_count += 1` 并 commit。
  - DeepSeek 挂了不烧用户当日 50 次。

---

## §6 配置 & 密钥

新增 `Settings` 字段（全有默认、env 可覆盖，**key 只在服务端，前端永不可见**）：

| 字段 | 默认 |
|---|---|
| `deepseek_api_key` | `""`（已存在；空 = 走本地兜底） |
| `deepseek_base_url` | `https://api.deepseek.com` |
| `deepseek_model` | `deepseek-chat` |
| `deepseek_timeout_seconds` | `8` |
| `deepseek_max_tokens` | `200` |
| `deepseek_temperature` | `1.3` |
| `deepseek_recent_context` | `10`（最近 N 条上下文） |

---

## §7 测试（全程离线）

- **`prompt.py` 纯函数单测**：system 含 tone/seed；`scold` vs `chat` 末轮分支；`_mood_hint` 各阈值；`recent` 渲染成正确的 user/assistant 交替。
- **`client.py`**：用 httpx `MockTransport` 测——成功解析文本 / 超时→`AIError` / 非 200→`AIError` / 空 `choices`→`AIError`。**不碰真网络**。
- **`generate_reaction`**：key 空→(兜底, False)；有 key + monkeypatch client 成功→(AI 文本, True)；monkeypatch client 抛 `AIError`→(兜底, False)。
- **quota 拆分**：`ai_quota_available` 跨日重置 / 到顶返回 False；`record_ai_usage` 只 +1。
- **router 集成**（`tests/` 现有风格，SQLite in-memory + `TestClient`）：
  - key 空下现有 actions 测试**保持绿**（自动走兜底）。
  - monkeypatch AI 成功：`ai_reaction.content == AI 文本` 且额度 +1。
  - monkeypatch AI 失败：`ai_reaction.content == 兜底` 且额度不变、数值/动作照常落库。

---

## §8 不做（YAGNI）

人设扩写、AI 记忆压缩、进化、流式打字机、其余 5 个本地动作改 AI、重试 / 退避 / 熔断（两人量级，一次超时直接兜底即可）。

---

## §9 判断点（已定）

1. **同步**返回（前端 LoadingBanter 顶等待，零契约改动）。
2. **只接活回应**（chat/scold），人设扩写 / 记忆 / 进化留后续。
3. **超时上限 8s** → 到点给兜底。
4. **额度只在 AI 真成功时扣**（失败不烧额度，需拆 quota 两步）。
5. **最近 N=10 条**上下文喂 prompt。
