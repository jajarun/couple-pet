# 情侣火苗 🔥 + 每日一问 设计

> **背景**：现有玩法(捏分身 / 七种动作 / 四个数值 / AI 回应 / 分身撩你)缺一个**每日回访钩子**——用户点几下就走,没有"明天必须回来"的理由,也没利用好"屏幕另一头是真人"这个最强资产。本计划做**留存三件套(A/B/C)**里的 **A**:情侣火苗 streak + 每日一问,把"两个真人互相牵制 + 答完在等对方"变成每天回来的动力。

**一句话目标**:让每天来的理由变成——「不上会断了 TA 的火苗🔥」+「我答完了今日一问,想知道 TA 答了没」。

---

## §1 目标 & 范围

**范围内**
- **火苗 streak(规则③:双人 + 宽限)**:两人当天都有效互动才续上,漏了警告 / 可续火。纯函数 `rules/streak.py` + 新表 `couple_streaks` + 结算钩子。
- **每日一问**:每对每天一道 AI 混味出题;各自独立作答;**双方都答完前互相看不到**,答完同时解锁。新表 `daily_questions` / `daily_answers` + 新路由。
- 首页 🏠 顶部展示火苗条 + 今日一问卡(三态);解锁后往聊天时间线落一条可回看的问答卡。
- 无 key / 超额时出题走本地题库兜底(延续现有离线可玩哲学);全程离线可测。

**范围外(各自留后续)**
- **B — Web Push 投递**:A 只**算出并暴露**"该催谁"(`at_risk` / `lagging_user`)和"TA 答完了"这些状态点;真正把通知推给一个**没开页面**的用户属于 B(PWA + Web Push,HTTPS 由用户解决)。没有后台定时任务,离线投递必须靠服务端主动推 = B。
- **C — 养成升级 + 沙雕恋爱周报**:下一个 spec。`Avatar.evolution`(JSON,已存在但未用)留给它;火苗里程碑(7/30/100/365)将来接 C 的解锁,本计划只发一条庆祝事件、不做解锁物。
- **异地跨时区情侣**:v1 用固定时区判日界,假设两人同区。

**契约不变**:现有 `POST /actions`、`GET /events`(feed 轮询)、幂等 `client_key`、`CoupleStats` 时间衰减等一律不动;火苗结算是在动作 / 答题成功后**追加**一次纯函数调用。

---

## §2 火苗 streak —— `rules/streak.py`(纯函数)+ `couple_streaks`(新表)

### 数据模型 `CoupleStreak`(一 couple 一行,懒 get-or-create)

| 列 | 类型 | 含义 |
|---|---|---|
| `couple_id` | PK, FK couples | |
| `count` | int, default 0 | 当前火苗天数(存储值;读时按存活重算"有效值") |
| `last_both_day` | Date, null | 最近一次**两人都完成**的日期 |
| `a_active_day` | Date, null | user_a 最近活跃日 |
| `b_active_day` | Date, null | user_b 最近活跃日 |
| `rescue_day` | Date, null | 最近一次"续火"日期(限流用) |

> 不靠扫 events 判活跃——在每次有效互动点**显式** `touch()`,直接更新 `*_active_day`。更干净、也不必按日期查事件。

### "有效互动"的定义
7 个动作任一(`POST /actions` 成功)**或**答今日一问(`POST /daily/answer` 成功)。用户 → 槽位映射:`user==couple.user_a_id → 'a'`,否则 `'b'`。

### 纯函数(无 DB / 无时钟,`today` 由调用方按配置时区算好传入)

```python
def touch(state: dict, slot: str, today: date) -> dict:
    """记一次某人今天的有效互动,必要时推进 count。返回新 state。"""
    # 1) 标记该槽今天活跃
    # 2) 若 a_active_day==today 且 b_active_day==today 且 last_both_day!=today：
    #      count = count+1 if last_both_day==today-1 else 1
    #      last_both_day = today
    # 3) 返回

def view(state: dict, today: date) -> dict:
    """读时结算,产出前端 / B 用的派生状态。不改存储。"""
    alive = state["last_both_day"] in (today, today - 1day)
    return {
        "count": state["count"] if alive else 0,   # 断了显示 0
        "i_did_today":       <该请求用户的 *_active_day == today>,
        "partner_did_today": <对方的 *_active_day == today>,
        "both_today": a_active_day==today and b_active_day==today,
        "at_risk":  alive and not both_today,        # 今天还没锁定,天黑前不续就断
        "lagging_slot": <today 没活跃的那个槽 / None>,  # B 据此决定推给谁
    }

def rescue(state: dict, today: date) -> dict:
    """只漏一天(last_both_day==today-2)可补救一次：把 last_both_day 补成 today-1。
    代价(扣亲密)与限流在 router 层做。"""
```

**存活 / 断裂**:懒判——`last_both_day ∈ {今天, 昨天}` 则火苗在;`< 昨天` 则断,`view` 里有效值归 0(存储 `count` 可在下次 `touch` 起点自然重置为 1)。

**结算钩子**:`/actions` 与 `/daily/answer` 成功后各调一次:`state = touch(state, slot, today); db.commit()`。

**里程碑**:`count` 跨过 7/30/100/365 时,往 timeline 落一条 `kind='system'` 庆祝事件(如「🔥 你们的火苗满 30 天啦!」)。解锁物留给 C。

**续火(最低优先,可砍)**:`POST /streak/rescue` → 若 `view` 显示可补救(漏一天)且 `rescue_day != today`,扣 `CoupleStats.intimacy` 固定值(如 −5)+ `rescue(state, today)`。前端在"火苗断了"卡上给个"花点亲密续火"按钮。**若排期紧,先只做 at_risk 警告,砍掉 rescue。**

### 时区
新配置 `streak_timezone: str = "Asia/Shanghai"`。`today` = `utcnow()` 转该时区取 date。集中在一个 `rules/streak.py::today_in(tz)` 或 router 辅助里,便于测试注入。

---

## §3 每日一问 —— 新表 + 新路由

### 数据模型
- `DailyQuestion(id, couple_id, day: Date, question: Text, flavor: str, created_at)`,唯一约束 `(couple_id, day)`。
- `DailyAnswer(id, question_id FK, user_id FK, content: Text, client_key, created_at)`,唯一约束 `(question_id, user_id)`;`client_key` 供幂等。

### 机制(解锁逻辑是核心钩子)
1. 每对每天一道**共享**题;当天首次 `GET /daily` 时生成并持久化(之后当天不变)。
2. 双方各自独立作答。
3. **双方都答完前,互相看不到对方答案**;`GET /daily` 只有在 `both_answered` 时才返回 `partner_answer`。
4. 答完瞬间双方同时解锁,并往 timeline 落一条 reveal 事件(见下),聊天里可回看。

### 出题
- **有 key**:AI 混味——当天在 {暧昧, 深度了解, 沙雕无厘头} 里随机挑一种 `flavor`,喂 persona / 双方性别做轻个性化,生成一句情侣问题。走现有 `app/ai/` 客户端;失败即兜底。
- **无 key / 超额 / 出错**:本地题库兜底,按 flavor 分组(仿 `rules/actions.py::NUDGE_LINES` 的组织),随机挑;为避免同一天重取变题,**首次生成即持久化**,后续读同一行。
- 成本:1 题 / 天 / couple,忽略不计,**不占用户聊天额度**(`ai_count` 不动)。
- 弱去重:AI 分支可把最近 N 天问题塞进 prompt 让其避开;本地题库足够大,v1 接受低概率重复。

### reveal 事件
双方答完时,插入一条父事件 `Event(kind='daily_qa', actor_user_id=None, content=<题目>)` 作为时间线锚点,**两条答案各作一条子事件**(`parent_event_id=<父>`,`actor_user_id=<答者>`,`content=<答案>`)——与现有 action→ai_reaction 的父/子结构一致。**新增事件 kind `'daily_qa'`**(`kind` 列 `String(16)` 够用),前端据此渲染问答卡(父题 + 两答按 `actor_user_id` 上色/左右分)。聊天 tab 已有红点机制,可复用提示新解锁。

---

## §4 接口(尽量少)

| 方法 & 路径 | 作用 | 返回 |
|---|---|---|
| `GET /daily` | 拉今天的问答 + 火苗一趟给全 | `{ question:{text,flavor}, my_answer:string\|null, partner_answer:string\|null, both_answered:bool, streak:{count,i_did_today,partner_did_today,at_risk,lagging_user_id\|null} }` |

> `streak.*` 由 `view()` 的派生值直接映射:`lagging_slot` 在 router 层转成 `lagging_user_id`(按 §2 的 user↔slot 映射);前端据 `at_risk`/`i_did_today`/`partner_did_today` 三个布尔自行拼文案,故**不设** `status` 字段。
| `POST /daily/answer` | 存我的答案(幂等 `client_key`),触发火苗结算 | 同 `GET /daily` 的最新态(等对方 / 已解锁) |
| `POST /streak/rescue` | 续火(可选,可砍) | 更新后的 streak 态 |

- `GET /daily` 首次调用负责**懒生成**当天题(并按需 get-or-create `couple_streaks` 行)。
- 火苗结算钩子加在既有 `POST /actions` 成功路径末尾(`touch` + commit),对现有契约零破坏。
- 鉴权 / 取 active couple 复用 `deps.get_current_user` / `get_active_couple`。

---

## §5 前端(React + TanStack Query)

**首页 🏠 TA 顶部**(`HomeScreen` 顶部,`StatDashboard` 之上)加:
- **火苗条**:`🔥 {count} 天` + 状态文案。
  - 未 at_risk:`🔥 23 天`;
  - `at_risk && !i_did_today`:「🔥 快断了!今天还没露面」;
  - `at_risk && i_did_today && !partner_did_today`:「🔥 今天你搞定了,就等 TA」;
  - 断了(count 0 且曾有火苗):给续火入口(若做了 rescue)。
- **今日一问卡**(三态):
  1. 未答:题目 + 输入框 + 提交(幂等 key,仿 `useIdempotencyKey` / `useAction`)。
  2. 已答未解锁:「✅ 你答完啦,就等 TA 了…」——**核心钩子**。
  3. 双方解锁:并排两人答案 + 小甜点动画(framer-motion,延续现有手感)。

**数据获取**:新 hook `useDaily(coupleId)` —— TanStack Query 拉 `GET /daily`,带 `refetchInterval`(约 15–30s,复用现有轮询风格),这样对方在我开着页面时答完能自动解锁。提交走 `POST /daily/answer` 的 mutation,成功后写缓存。
**聊天时间线**:`daily_qa` 事件渲染成问答卡(已解锁才显示双方答案),复用 feed 轮询;红点复用 `shell/badge`。

---

## §6 测试(沿用现有套路)

- **`rules/streak.py` 纯函数单测**(镜像 `rules/stats.py` 测法):
  - 连续续火 count+1;隔天重置为 1;同日多次 touch 不重复 +1。
  - `view`:存活 / 断裂(有效值归 0)、`at_risk`、`i/partner_did_today`、`lagging_slot`。
  - 日界边界(今天 / 昨天 / 前天);`rescue` 仅漏一天可用、扣费、限流(`rescue_day`)。
- **每日一问**:兜底出题确定性(无 key 走题库、当天持久化不变)、"双方答完才解锁"、答题幂等(同 `client_key` 不重复)。
- **API 测试**:内存 SQLite(现有 pytest 套路),`GET /daily` 懒生成、`POST /daily/answer` 解锁流转、`/actions` 后火苗被 touch。
- **前端**:MSW + Vitest 覆盖今日一问卡三态、火苗条各状态文案、解锁自动刷新。

---

## §7 已定决策(此前留的三问)

1. **日界时区**:固定 `Asia/Shanghai`(v1 假设两人同区)。
2. **续火**:v1 做,但列为**最低优先、可砍**;排期紧则先只留 `at_risk` 警告。
3. **每日一问位置**:首页 🏠 顶部卡片。

---

## §8 数据流一图流

```
开 App → 首页 → GET /daily ──► 火苗条 + 今日一问卡
  │                              └─(未答)输入 → POST /daily/answer → touch 火苗 → "等 TA"
  ├─ 点 7 动作之一 → POST /actions → (末尾) touch 火苗
  ▼
对方稍后答题/互动 → 其 GET/POST 触发解锁 & touch
  → 双方 both_answered=true → 落 daily_qa reveal 事件(聊天可回看)
  → view.at_risk / lagging_user_id  ──►（B）Web Push:「🔥就差你了」/「TA 答完了今日一问」
```

## §9 后续衔接(非本计划)
- **B**:订阅/推送端点 + service worker;把 §8 右下角的状态点变成真正的离线通知。
- **C**:`Avatar.evolution` 养成向量、关系升级解锁(火苗里程碑接入)、每周沙雕恋爱周报。
