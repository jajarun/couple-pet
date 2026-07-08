# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 沟通约定

- **始终用中文输出**：回复、代码注释、提交信息、文档一律中文，与现有代码风格保持一致（本仓库注释全为中文口语，动作/文案也是中文）。

## 项目是什么

情侣两人玩的手机网页小游戏：各自捏一只**代表对方**的 AI 分身宠物，用互动动作（骂/戳/喂狗粮/抱/想你/道歉/唠嗑）隔空撩拨，共享「委屈/狗粮/想你/亲密」四个关系数值，外加「情侣火苗🔥 + 每日一问」留存玩法。分身平时由 DeepSeek 驱动、始终在人设里，真人也能「本尊回应」顶替 AI。详见 `README.md`。

技术栈：**前端** Vite + React 18 + TS + TanStack Query；**后端** FastAPI + SQLAlchemy 2.0 + MySQL（本地/测试默认 SQLite）+ JWT；**AI** DeepSeek（httpx，OpenAI 兼容）；**部署** Docker Compose（db + backend + nginx）。

## 常用命令

本机工具不在全局 PATH 上：Python 用 `backend/.venv`，Node/pnpm 在 `~/Library/pnpm/bin`。

### 后端（在 `backend/` 下）

```bash
./.venv/bin/python -m pytest -q                 # 跑全部测试（默认内存 SQLite，无需起 MySQL）
./.venv/bin/pytest tests/test_daily.py -q       # 单个测试文件
./.venv/bin/pytest tests/test_daily.py::test_rescue_restores_streak_and_costs_intimacy   # 单个用例
./.venv/bin/uvicorn app.main:app --reload       # 本地起后端（config 默认 sqlite:///./dev.db，启动自动建表）
```

### 前端（在 `frontend/` 下，pnpm）

```bash
pnpm dev                       # vite dev，自动把 /api 反代到 http://localhost:8000
pnpm build                     # tsc -b && vite build（tsc 是唯一静态门禁，无独立 lint）
pnpm test                      # vitest run（全部）
pnpm test src/home/FireBar.test.tsx     # 单文件
pnpm vitest run -t "可救时"             # 按标题过滤单个用例
pnpm exec tsc --noEmit         # 只做类型检查
```

> **没有 ESLint / Prettier / 后端 linter**——类型正确性靠 `tsc`，别去找 lint 脚本。

### 一键起全栈

```bash
cp .env.example .env     # 可选：改端口/密码/填 DEEPSEEK_API_KEY
./start.sh -d            # 打包前端 dist + docker compose 起 db+backend+web；入口 http://localhost
```

## 架构总览

### 后端严格三层（改后端务必遵守）

1. **`app/rules/*.py` — 纯函数**：无 DB / 无时钟 / 无 settings / 无 AI，`today` 一律由调用方传入，不改入参、返回新值。业务规则都在这里、单元测试也在这里最容易覆盖。
   - `streak.py`：火苗状态机（`touch`/`view`/`can_rescue`/`rescue`，`today_for` 做时区换算）。
   - `stats.py`：四数值的 `clamp`(0–100)、`DEFAULT_STATS`、随时间漂移（`intimacy` 不衰减）。
   - `actions.py`：七种动作对数值的增量表 + 每个动作 50+ 条本地沙雕文案 + 主动撩人文案；`AI_ACTIONS = {scold, chat}`。
   - `daily_questions.py`：flavor 轮换选题 + **本地题库(现作 AI 出题的兜底)**。
2. **`app/streak_service.py`（及 router 内的编排段）— DB 编排**：行 ↔ 纯函数 state 的转换、落里程碑事件等。**关键：service 层不 commit**（注释「事务由 router 掌管」），只 `flush`。
3. **`app/routers/*.py` — HTTP + 事务边界**：唯一 `db.commit()` 的地方；并发首建（同一对同一天/同一 client_key 几乎同时到）会撞唯一约束，路由统一 `except IntegrityError → rollback → 重试一次`（见 `daily.py` 的 `_run()`）。

注册的路由（`app/main.py`，无前缀者路径即函数上写的）：`auth`、`couples`、`avatars`、`actions`、`events`、`daily`、`push`，外加 `/health`。**无 Alembic**——启动时 `Base.metadata.create_all(engine)` 幂等建表（`docker-entrypoint.sh` / 应用启动）。`main.py` 有 `lifespan`：仅当配了 VAPID 私钥时起 APScheduler 跑火苗定时提醒——**跑在 uvicorn 进程内、依赖单 worker**（改多 worker 会重复触发）。

### 数据模型（`app/models.py`）

- `User`：含 `gender`、`ai_count` / `ai_count_date`（AI 每日额度）。
- `Couple`：`user_a_id` / `user_b_id` / `status`(active/pending) / `pair_code`。
- `Avatar`：配对后生成**两只镜像分身**，靠 `subject_user_id`（代表谁）+ `keeper_user_id`（谁在养）区分；`appearance` / `persona` 为 JSON。
- `CoupleStats`：PK=`couple_id`，`stats` **JSON 列**存 `{grievance,dogfood,miss,intimacy}`（改数值 = 复制 dict 再整体赋值，别原地改）。
- `CoupleStreak`：PK=`couple_id`，`count` + 四个日期字段（`last_both_day`/`a_active_day`/`b_active_day`/`rescue_day`）。
- `Event`：统一时间线，`kind ∈ {action, ai_reaction, real_response, system, daily_qa}`，`parent_event_id` 串起「每日一问父题 + 两条答案」。
- `DailyQuestion`(唯一约束 couple+day) / `DailyAnswer`(唯一约束 question+user，带 `client_key`)。
- `PushSubscription`：一个浏览器的 Web Push 订阅（`user_id` + `endpoint`(唯一) + `p256dh`/`auth`）；一个 user 可多设备多行，发推遇 404/410 按 endpoint 删。

### AI 集成（`app/ai/`，DeepSeek）

分层同样清晰、且**核心承诺是「永不因 AI 失败而报错」**：

- `client.py`：`chat_completion(messages)` 纯调用+解析，失败抛 `AIError`，不兜底。
- `prompt.py`：纯函数把 **人设 + 基调 + 性别 + 此刻心情（某值≥60 就带情绪）+ 最近对话** 拼成 messages。
- `deepseek.py`：`generate_reaction(...)` 编排——**无 key 或任何异常都落本地兜底**，返回 `(text, used_ai)`，永不抛。
- `quota.py`：`ai_quota_available` / `record_ai_usage` 做每人每日上限（`daily_chat_cap`，跨 UTC 日归零）。
- `daily_question.py`：**每日一问的 AI 出题**（`generate_question`）。flavor 仍由 rules 轮换,AI 只生成该味的一句题；无 key/失败回落 `daily_questions.pick_local`。每对每天一次的共享资源,**不占个人额度**(不碰 quota),生成入口在 `daily.py:_get_or_create_question`(只在当天首建时调一次,之后读库)。

> 加任何新的 AI 能力，照 `deepseek.py` / `daily_question.py` 的范式走：先查 key（按需查额度）→ 拼 prompt → try 调用 → except 落本地兜底，保证离线可玩、CI 无 key 也绿。

### 消息推送（Web Push / PWA）

**契约同 AI：无 VAPID 私钥 = 整套静默关闭、绝不因推送失败而影响主流程、永不抛。** 分两类：

- **实时推送**：挂在现有路由 `db.commit()` 之后，用 FastAPI `BackgroundTasks` 异步发（不阻塞响应）。挂点：`actions.py`(对方发动作 / 委屈爆表)、`events.py`(本尊回应)、`daily.py`(每日一问首答催对方)。**partner_id 必须在 commit 前从 couple 取成 int**（`push_service.partner_of`），别把 ORM 对象丢进后台任务。
- **定时推送**：`push_scheduler.remind_dying_streaks()` 每天单次触发（`main.py` lifespan 的 APScheduler），扫活跃情侣的火苗，给「今晚会灭 / 已断可救」的人发；模块级 `_today()` 供测试注入。
- `push_service.send_to_user(user_id, payload)`：核心发送原语，**自开 `SessionLocal()`**（不走请求作用域，供后台任务/定时 job 复用），逐条 `pywebpush.webpush`，404/410 删失效订阅。payload=`{title,body,url,tag}`，`tag` 让 SW 折叠同类通知。
- **VAPID 密钥**：`app/gen_vapid.py` 生成（`python -m app.gen_vapid`），公钥走 `GET /push/public-key` 下发前端、私钥只在服务端；`config.py` 里空 key = 关闭（同 `deepseek_api_key`）。
- 前端：`public/sw.js`(手写最小 SW，只处理 push/notificationclick，前台聚焦时抑制)、`main.tsx` 注册、`hooks/usePush.ts`(开关逻辑 + `ensurePushSubscribed` 静默补订)、开关 UI 在「⚙️我」页签。**iOS 需装到主屏幕、需 HTTPS**。

### 前端外壳与流程（状态驱动，非路由驱动）

只有 `/login`、`/register` 走 React Router；登录后全部落在 catch-all `/*` 后面。`App.tsx` 的 `Gate` 是一条**靠服务端查询逐级放行的漏斗**：`login → 配对(PairScreen) → 捏自己的分身(AvatarCreateScreen) → MainShell`，每一步 gate 在一个 query 上（`useCouple` 状态 none/pending/active、`useMyAvatar` 名字是否为空），不是靠 URL。进 `MainShell` 后三个页签（🏠TA / 💬聊天 / ⚙️我）是本地 `useState`，也不走路由。新消息未读红点、分身主动撩你(`useNudge`)都挂在 `MainShell` 上跨页签生效。

### 前端数据层（这是理解前端的关键）

- **`src/api/client.ts`**：`apiRequest(method, path, body?)`，base=`/api`，自动注入 `Bearer` token，非 2xx 抛 `ApiError(status, detail)`，401 触发 `onUnauthorized`。各领域 API 拆在 `src/api/{daily,events,actions,couples,avatars,auth}.ts`。
- **`src/hooks/*` + TanStack Query**：query key 集中在 `dailyKey`/`feedKey`/`statsKey`。轮询：`useDaily` 20s（等对方答题解锁）、`useFeed` 3s（拉新消息）。写缓存的约定——**mutation 成功后把服务端返回直接 `qc.setQueryData` 回写**（如答题/续火），必要时才 `invalidateQueries`。
- **数值缓存是「被动镜像」**：`StatDashboard` 用 `enabled:false` 的 `useQuery(statsKey)` 只读，从不自己发请求；`useFeed`/`useAction` 成功时 `setQueryData(statsKey, ...)` 喂给它。改数值展示要顺着这条链。
- **幂等**：`useIdempotencyKey` 生成 `client_key` 放进 mutation variables，重试复用同一 key；`retry` 只在**非 `ApiError`**（即网络错误）时进行，4xx 立即冒泡。
- **时间线懒加载**：`useFeed` 的 `mergeEvents`/`appendToFeed`/`useLoadOlder`，`cursor`=最新 id 向前轮询、`oldestLoaded`=向上翻页游标。

### 性别主题（男蓝 / 女淡粉）

CSS 变量按 `<html data-theme>` 切换：`src/theme.ts` `applyTheme(gender)` 写 `document.documentElement.dataset.theme`，`AuthContext` 依登录者性别调用它；配色在 `src/styles/tokens.css`（`:root` 中性薰衣草、`[data-theme='male']` 蓝、`[data-theme='female']` 淡粉）。**新 UI 一律用 `var(--primary / --primary-soft / --primary-strong / --primary-ink / --aura)`，不要写死颜色**，才能自动跟随性别 + 心情光环。

## 测试约定

- **后端**：`tests/conftest.py` 用内存 SQLite + `StaticPool` + `dependency_overrides[get_db]`；`client` / `auth_headers` 是基础 fixture。控制「今天」用 `monkeypatch.setattr(app.streak_service, "_today", lambda: date(...))`（火苗/每日一问的日界都走它）。**`client` fixture 还把 `push_service` / `push_scheduler` 的 `SessionLocal` 重定向到同一个内存库**（它俩自开会话发推/扫库），并挂 `client.session_factory` 供测试开同库会话查数据；测推送时 `monkeypatch` 掉 `app.push_service.webpush`（绝不真发网）。
- **前端**：Vitest + jsdom + **MSW**。默认接口桩在 `src/test/handlers.ts`，单测里用 `server.use(http...)` 覆盖；渲染用 `src/test/utils.tsx` 的 `renderWithProviders`（内置 QueryClient `retry:false` + MemoryRouter）。注意 `setup.ts` 设了 `onUnhandledRequest:'error'`——**测试里发出的每个请求都必须有 mock**，否则直接失败。

## 易踩的坑

- 改 `CoupleStats.stats` / `Avatar.persona` 等 JSON 列：**复制成新 dict 再整体赋值**，SQLAlchemy 才认得脏（原地改字段不会触发更新）。
- 新增/改动纯函数的返回结构时，注意 `test_rules_streak.py` 里有**整字典相等**断言，会一并需要更新。
- 「可续火」的火苗态是 `count:0 / at_risk:false`（`view()` 判定为已断），UI 判断要用 `rescuable` 字段而非 `at_risk`。
- **建索引/唯一约束的列别用 `Text`**：SQLite（测试）不挑、能过，但 MySQL 建表直接报 `1170 BLOB/TEXT column used in key specification without a key length`，后端启动时 `create_all` 会一直失败、卡在"数据库还没准备好"。用定长 `String(N)`（见 `PushSubscription.endpoint = String(512)`）。改 schema 后记得 `docker compose up -d --build backend` 重建镜像,否则 `down -v` 清库重来会再炸。
