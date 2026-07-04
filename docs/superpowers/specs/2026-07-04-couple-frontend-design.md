# AI 情侣分身宠物游戏 · 前端设计文档

- **日期**：2026-07-04
- **状态**：设计已确认，待进入实现计划
- **一句话**：给已完成的后端核心（配对 + 分身 + 事件流）配一个移动端竖屏的像素电子宠物机前端，把「隔空互动」的双人试玩闭环整条打通——画面可以糙，但手感必须舒服。

> **前置**：后端核心已合并进 `main`（认证 / 配对 / 分身 / 统一动作流 / 事件流轮询 / 本尊附身回应 / DeepSeek 确定性 stub + 每日额度）。本前端直接消费这套 API。DeepSeek 目前是确定性 stub、聊天非流式——不影响前端搭建与试玩，接真 DeepSeek 是另一个计划。

---

## 1. 目标与范围

**目标**：一个可**双人真配对试玩**的前端。乐趣只有两个人把整条链路走一遍才验证得出来，所以这一版做**全量可玩闭环**：

登录/注册 → 创建/加入配对 → 捏分身 → 家（数值仪表盘 + 分身 + 7 个动作）→ 事件流（本尊附身回应）→ 随便唠聊天。

**明确不做（YAGNI）**：
- **进化全屏过场**——后端还没有进化触发逻辑，发不出 evolution 事件，无从驱动。
- **Web Push**——非目标（后端也未实现）。
- **AI 人设扩写**——后端 `PUT /avatars/mine` 只存原始 `persona` JSON，无 AI 扩写端点；捏分身 v1 = 收集基调/名字/emoji造型/种子答案后直接存，AI 扩写属于接真 DeepSeek 的计划。
- **真机精灵美术**——v1 用 emoji + 像素 CSS 脸 + transform 动画，真精灵图后续无痛替换。
- **音效**——避免移动端 autoplay 坑，新事件用视觉脉冲代替「叮」声。

---

## 2. 视觉与体验基调

**主视觉锚点：复古电子宠物机（像素风）**。整个 App 是一台像素掌机/电子宠物机的外壳：点阵屏显示分身、像素数值条、厚实像素按钮。像素风让「糙」变成**故意的风格**而非做不精致。**meme 沙雕文案 + 情侣软萌配色**作为点缀叠在上面。

**交互质感是产品体验底线（来自设计总纲 §7，前端必须满足）**：
- **操作有过渡**：点按钮/做动作要有即时微反馈（按压态、气泡弹出、数值滚动、分身抖一抖），绝不「点了没反应然后页面硬切」。
- **等待有戏**：任何加载/等对方/等 AI 的空窗用无厘头台词轮播顶上，把等待变笑点，绝不空屏干等。
- **失败也可爱**：AI 超时/报错用卖萌文案兜，不把报错糊脸上，且**失败不改数值**。
- **节奏克制**：动效短（<300ms）、不挡操作、可连点、照顾单手竖屏。

---

## 3. 技术选型（方案 A：轻依赖、手感优先）

| 维度 | 选择 | 理由 |
|---|---|---|
| 构建/框架 | **Vite + React + TypeScript** | 后端返回结构固定，TS 挡住轮询/游标/事件 kind 分支的低级错 |
| 服务端状态 | **TanStack Query** | `refetchInterval` 轮询、游标缓存、去重、失败退避重试、切后台自动暂停——事件流轮询与「失败兜底」几乎白送 |
| 动效 | **Framer Motion** | 按压态/气泡弹出/数值滚动/分身抖动——「操作有过渡」的直接落地 |
| 样式 | **手写 CSS / CSS Modules + 像素设计令牌** | 像素电子宠物机外壳太定制，工具类 CSS 帮不上；手写可控 keyframe 精灵动画 |
| 路由 | **React Router** | 登录 / 新手引导 / 三 tab 主壳 |
| 测试 | **Vitest + React Testing Library + MSW** | mock 整个 FastAPI，CI 不碰真后端/真 DeepSeek（§8） |

**代价**：两个额外依赖（TanStack Query + Framer Motion），各自精确对应一条产品体验底线，值得。

---

## 4. 后端 API 契约（前端消费的真实端点）

所有需要鉴权的端点带 `Authorization: Bearer <token>`。

### 认证
- `POST /auth/register {nickname, password}` → `{access_token, token_type:"bearer", user:{id, nickname}}`（重名 `409`）
- `POST /auth/login {nickname, password}` → 同上（错误 `401`）

### 配对
- `POST /couples` → `{couple_id, pair_code, status:"pending"}`（已在配对中 `409`）
- `POST /couples/join {pair_code}` → `{couple_id, status:"active"}`（无效码 `404` / 已 active `409` / 自配 `400` / 已在配对中 `409`）
- `GET /couples/me` → 三态之一：
  - `{couple_id, status:"active", partner_id}`
  - `{couple_id, status:"pending", pair_code}`
  - `{couple_id:null, status:"none"}`

### 分身
- `GET /avatars/mine` → `{id, couple_id, subject_user_id, keeper_user_id, name, appearance, persona}`（**你自己那只 = 对方看到的你**；未捏时 `name`/`persona` 为空）
- `PUT /avatars/mine {name?, appearance?, persona?}` → 更新后的分身
- `GET /avatars/pet` → 你饲养的那只（**对方的分身**；对方未捏时 `name`/`persona` 为空）
- 无 couple 时以上三个返回 `409`

### 动作（统一入口）
- `POST /actions {action_type, content, client_key}` → `{events:[...], stats:{...}}`
  - `events` = 该 action 事件 + 其 `ai_reaction` 子事件（+ 委屈爆表时的 `system` 旁白）
  - `action_type ∈ {scold, poke, feed_dogfood, hug, miss_you, apologize, chat}`
  - 未知动作 `422`；无 couple `409`
  - **幂等**：同一 `(couple, client_key, kind="action")` 直接返回既有 bundle

### 事件流
- `GET /events?since=<id>` → `{events:[...], stats:{...}}`（`events.id > since`，升序；`stats` 是只读 live 衰减值）
- `POST /events/{event_id}/respond {content, client_key}` → 单条 `real_response` 事件
  - 只能回应对方的 `action` 事件（`actor != caller`，否则 `403`）；事件不存在/不属于自己 `404`
  - **幂等**：同一 `(couple, client_key, kind="real_response")` 直接返回既有事件

### 事件结构 `event_out`
`{id, couple_id, actor_user_id, kind, action_type, content, parent_event_id, created_at}`
- `kind ∈ {action, ai_reaction, real_response, system}`
- `actor_user_id` 为 `null` 表示系统/AI 生成

### 共享数值 `stats`
4 键，均 0–100 整数：`grievance`(委屈) / `dogfood`(狗粮) / `miss`(想你) / `intimacy`(亲密度)。前端**从不自算**，永远显示服务端返回值。

---

## 5. 项目结构

新建 `frontend/`，与 `backend/` 平级。开发期 Vite proxy 把 `/api` 转发到 `localhost:8000`，生产用 `VITE_API_BASE`。

```
frontend/src/
  main.tsx              # 挂 QueryClientProvider + Router
  App.tsx               # 路由 + 三态引导网关
  api/
    client.ts           # fetch 封装：base URL、Bearer 头、错误→类型化异常
    auth.ts couples.ts avatars.ts actions.ts events.ts
    types.ts            # 与后端对齐的响应类型（Event/Stats/Avatar…）
  auth/
    AuthContext.tsx     # token 存 localStorage、当前 user
    LoginScreen.tsx  RegisterScreen.tsx
  onboarding/
    PairScreen.tsx      # 创建/加入配对、亮邀请码、等待轮询
    AvatarCreateScreen.tsx   # 捏分身向导（基调+名字+emoji造型+种子问题→PUT）
  home/    HomeScreen.tsx  StatDashboard.tsx  ActionBar.tsx
  feed/    FeedScreen.tsx  EventItem.tsx
  chat/    ChatScreen.tsx
  me/      MyAvatarScreen.tsx
  components/           # 手感层（一等公民，全局复用）
    PixelPanel.tsx PressButton.tsx StatGauge.tsx
    SpeechBubble.tsx LoadingBanter.tsx PetSprite.tsx TabBar.tsx
  hooks/   useCouple.ts useFeed.ts useAvatar.ts useAction.ts useIdempotencyKey.ts
  styles/  tokens.css global.css     # 像素令牌：像素字体、pixelated 渲染、厚边框
  banter.ts            # 无厘头等待台词库
```

每个文件一个清晰职责，方便隔离测试。

---

## 6. 路由与三态引导网关

`App.tsx` 按顺序判定落哪个屏，把业务错在网关层挡住而不是漏到屏幕：

1. **无 token** → 登录/注册。
2. 有 token → `GET /couples/me`：
   - `status:"none"` → **配对屏**（创建 → 亮 `pair_code` 发对方）。
   - `status:"pending"` → **配对等待屏**（显示邀请码 + 「催 TA 一下」，轮询 `/couples/me` 直到 active）。
   - `status:"active"` → `GET /avatars/mine`：`name`/`persona` 为空 → **捏分身向导**（本人只捏一次）；否则 → **主壳**。
3. **主壳** = 像素机身外框 `PixelPanel` 内含底部三 tab：🏠 TA / 🔔 事件流 / ⚙️ 我的分身；💬 聊天从家界面滑出。

**等待态（别对着空屏）**：
- 配对中 → 邀请码 + 催 TA 占位 + `LoadingBanter`。
- 已配对但**对方还没捏分身**（`GET /avatars/pet` 的 `name`/`persona` 为空）→ 家界面显示「对方分身孵化中 🥚 + 催 TA」占位，而非空宠物。

---

## 7. 数据流

**服务端状态全交给 TanStack Query，一份 `stats` 缓存两处写。**

### 事件流轮询 `useFeed()`
固定 queryKey `['feed', coupleId]`，`refetchInterval: 3000`。queryFn 内部：
1. 从 `cursor` ref 读上次最大 id → `GET /events?since=cursor`；
2. 增量事件**追加**进累积列表，`cursor` 推进到本批最大 id；
3. 把响应里的 `stats` 写进 `['stats', coupleId]`。

切后台标签自动暂停轮询，重新聚焦/断网重连自动补拉。返回 `{events, stats}` 全量时间线。

### stats 单一真源，两个写入者
- ① 每次 feed 轮询（带 live 衰减的最新值）；
- ② `/actions` 与 `/events/{id}/respond` 的 mutation 成功后：把 bundle 里 `stats` 写进 `['stats', coupleId]`，并把返回的新事件**追加进 feed 缓存 + `cursor` 推到这批最大 id**（避免下次轮询重复返回）。

`StatDashboard` 只订阅 `['stats', coupleId]`，值一变触发数字滚动。前端从不自算 stats → 两人并发操作的覆盖由后端事务兜底，前端只显示最新服务端值，天然无客户端竞态。

### 幂等键 `useIdempotencyKey`
用户发起动作/回应时 `crypto.randomUUID()` 生成 `client_key`，**重试复用同一个键**，成功后丢弃 → 重试不重复轰炸对方。

### 一次动作的乐观流（手感核心）
1. 点按钮 → 立刻：按压动效 + 生成 `client_key` + 分身头顶弹 `SpeechBubble` 挂 `LoadingBanter`。**不乐观改数字**（clamp/衰减会漂），只给即时微反馈。
2. `await POST /actions` 成功 → 气泡换成 `ai_reaction`（打字机逐字显）、`StatGauge` 滚到新值、分身放一次性反应动画；bundle 带回 `system` 委屈旁白 → 委屈条抖动变警戒色 + 弹旁白。
3. 失败 → 气泡换卖萌兜底台词、**数字不动**、给「再怼一次」（复用同一 `client_key` 重试）。

本地动作后端瞬回，AI 动作现在走 stub 也瞬回，但整条流按「有延迟」设计，接真 DeepSeek 时手感不用改。

### 本尊附身回应
FeedScreen 里，`actor_user_id === partner_id` 且还没有 `real_response` 子事件的 `action` 事件，显示「👤 本尊附身回应」入口 → 内联输入 → `POST /events/{event_id}/respond`（带 `client_key`）→ 成功后那条 `real_response` 带**醒目「👤 本尊回应」徽标 + 特殊动效**（心动峰值）。轮询新到的事件配轻脉冲 + 🔔 tab 角标。

### 聊天
`action_type:"chat"` 走 `POST /actions`，返回 `ai_reaction`。ChatScreen 是**同一份 feed 时间线的过滤投影**（挑 chat 相关事件），跟事件流同源不打架；打字机是客户端逐字揭示。

---

## 8. 手感层动效清单（§7 收敛到这几个组件，全屏复用）

| 组件 | 动效 | 服务的体验点 |
|---|---|---|
| `PressButton` | 按下缩放+内阴影、松开弹回；in-flight + ~800ms 客户端冷却禁用（防刷屏，可连点不轰炸） | 操作有过渡 / 节奏克制 |
| `StatGauge` | 像素条 + 数字滚动（Framer `useSpring`）、随填充变色；委屈过阈→抖动+警戒色 | 操作有过渡 |
| `SpeechBubble` | 弹入（缩放+回弹）、AI 文案打字机逐字显 | 操作有过渡 |
| `LoadingBanter` | 每 ~1.2s 轮播一条无厘头台词（`banter.ts`），用于 AI 等待/配对等待/孵化占位/聊天等待 | 等待有戏 |
| `PetSprite` | idle 循环（呼吸/眨眼/偶尔抖）、动作一次性反应动画；像素点阵脸 | 操作有过渡 |
| `PixelPanel` | 电子宠物机机身外框，包裹主壳与屏幕 | 视觉基调 |
| 失败态 | 统一走卖萌兜底文案，绝不糊报错；数字不动 | 失败也可爱 |

动效预算：全部 <300ms、不挡操作、可连点、照顾单手竖屏。

---

## 9. 错误与边界处理（映射设计总纲 §8）

**核心原则**：数值永远以服务端返回为准，前端从不自算 → 并发覆盖由后端事务兜底，前端无客户端竞态。

| 场景 | 后端信号 | 前端处理 |
|---|---|---|
| token 失效 | 任意 `401` | 清 token → 温和引导重登（无 refresh token，不假装静默刷新） |
| 注册重名 | 注册 `409` | 输入框内联「这名字被抢啦，换一个」 |
| 登录错 | 登录 `401` | 「账号或密码不对哦」 |
| 邀请码无效 | join `404` | 「邀请码不对或失效啦」 |
| 重复/已配对 | `409` | 路由回已有状态，不报错 |
| 自己配自己 | `400` | 「不能跟自己配对呀」 |
| 回应权限/事件不在 | respond `403`/`404` | 入口本就只挂对方动作上；竞态到了 toast + 隐藏入口 |
| 动作/回应网络失败 | — | 卖萌兜底 + 「再试一次」复用同一 `client_key`，数字不动 |
| AI 超额/超时 | 后端已回兜底文案 | 直接显示，不糊报错 |

**幂等实测点**：连点/重试用同一 `client_key` → 后端返回既有 bundle → UI 结果一致、对方只收到一条。**空态**：事件流空 → 友好空状态而非白屏；对方分身未捏 → 🥚 孵化占位。

---

## 10. 测试策略（设计总纲 §8 前端）

- **栈**：Vitest + React Testing Library + **MSW**（mock 整个 FastAPI，CI 不碰真后端/真 DeepSeek）。
- **流程/组件测**：
  - 配对：建 / 加入 / 无效码 / 等待轮询。
  - 捏分身：填表 → PUT → 落家。
  - 动作：点 → 乐观气泡 → 响应 → 数值滚动 → **幂等**（双击/重试同键只一条事件）。
  - 事件流：轮询追加、游标推进不重不漏、新事件高亮。
  - 本尊回应：入口只在对方动作上、提交 → 徽标。
  - 失败兜底：MSW 返 500 → 卖萌台词、数字不变。
- **hooks 单测**：`useFeed` 游标累积/去重、`useIdempotencyKey` 重试稳定。
- **动效**：只断言状态切换/元素出现，不测像素级时序（保测试健壮）。
- **不测**：真 DeepSeek（mock）、真双机试玩（手动——好不好玩只能靠两台设备真配对玩一遍）。

---

## 11. 任务分阶段（给 writing-plans 展开的骨架，~9 步 / 13+ 任务）

1. **地基**：Vite+React+TS 脚手架、装依赖（TanStack Query / Framer Motion / React Router）、Vite proxy、`tokens.css/global.css` 像素外壳、`api/client.ts`+`types.ts`、测试 harness（Vitest+RTL+MSW）。
2. **手感原语**：`PixelPanel/PressButton/StatGauge/SpeechBubble/LoadingBanter/PetSprite/TabBar` + `banter.ts`（先建成受测原语，后面屏幕直接消费）。
3. **鉴权**：AuthContext + 登录/注册 + 路由守卫。
4. **配对**：PairScreen 建/加入/等待 + `useCouple` + 边界。
5. **捏分身**：AvatarCreateScreen 向导 + `useAvatar`（PUT /avatars/mine）。
6. **家 + 动作**：HomeScreen + StatDashboard + ActionBar + `useFeed`/`useAction`（7 个动作 + 乐观流）。
7. **事件流 + 本尊回应**：FeedScreen + EventItem + respond。
8. **聊天**：ChatScreen（feed 投影 + 打字机）。
9. **整合打磨**：新事件脉冲 + 角标、各等待/空态、卖萌失败态、双机试玩自查清单。

---

## 12. 升级路径（留好的位）

- 接真 DeepSeek 后：聊天/骂改流式打字机（前端手感层已按流式设计，替换数据源即可）；捏分身接 AI 人设扩写端点。
- 轮询升级 SSE：`useFeed` 换数据源，屏幕不动。
- 进化全屏过场：后端补进化触发 + emit evolution 事件后，加一个全屏 overlay 组件消费。
- Web Push：接后端推送后加订阅引导。
- 音效：新事件「叮」等（避开 autoplay 后）。
