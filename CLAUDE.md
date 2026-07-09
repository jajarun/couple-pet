# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 沟通约定

- **始终用中文输出**：回复、代码注释、提交信息、文档一律中文，与现有代码风格保持一致（本仓库注释全为中文口语，动作/文案也是中文）。

## 项目是什么

情侣两人玩的手机网页小游戏：各自捏一只**代表对方**的 AI 分身宠物，用互动动作（骂/戳/喂狗粮/抱/想你/道歉/唠嗑/哄/摸头）隔空撩拨，共享「委屈/狗粮/想你/亲密」四个关系数值，外加「情侣火苗🔥 + 每日一问」「同框 ×2」「剧情副本」留存玩法。分身平时由 DeepSeek 驱动、始终在人设里，真人也能「本尊回应」顶替 AI。详见 `README.md`。

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
pnpm build                     # tsc -b && vite build（真正的静态门禁，无独立 lint）
pnpm test                      # vitest run（全部）
pnpm test src/home/FireBar.test.tsx     # 单文件
pnpm vitest run -t "可救时"             # 按标题过滤单个用例
pnpm exec tsc --noEmit         # 快速类型检查，但覆盖面比 pnpm build 窄（见下）
```

> **没有 ESLint / Prettier / 后端 linter**——类型正确性靠 `tsc`，别去找 lint 脚本。
>
> **提交前跑 `pnpm build`，别只跑 `pnpm exec tsc --noEmit`**：后者只查根 tsconfig，`tsc -b` 会沿 project references 把**测试文件**也一起查。实际漏过的例子：给只读的 `RefObject.current` 赋值、`import` 一个被 `exports` 挡住 .d.ts 的子路径——`--noEmit` 全绿，`pnpm build` 直接红。

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
   - `actions.py`：九种动作对数值的增量表 + 每个动作 50+ 条本地沙雕文案 + 主动撩人文案；`AI_ACTIONS = {scold, chat}`；`apply_action(stats, action, multiplier=1)` 的 `multiplier=2` 是「两人同框」（负面也翻倍）。
   - `presence.py`：`is_online(last_seen_at, now, ttl)` 一个纯函数，判「TA 此刻在不在」。
   - `stories.py`：剧情副本的**本地剧本库**（5 本 × 4 幕 + 结局），AI 出不来时的兜底。
   - `daily_questions.py`：flavor 轮换选题 + **本地题库(现作 AI 出题的兜底)**。
   - `evolution.py`：分身进化树（蛋/幼体/成体/完全体 + 5 个分支）。**驱动力是 `care`——「这只分身的饲养者对它做过什么」的动作累积，不碰 couple 级共享的四个数值**；否则两只镜像分身会同步长成一模一样。分支在首次进成体时按占比定型、此后不可逆。
   - `runaway.py`：离家出走判据 + 三态（`home`/`away`/`pending`）。**故意不看共享的 `grievance`**——它每小时自愈 −2（满值 100 只撑 10 小时，长窗口条件永远不成立），且是两人共享的（会让两只分身同时出走）。改成只看「这个饲养者在 **1 小时**窗口里骂了几次、哄了几次」。**`HOSTILE` 只有 `scold`**——首页点分身发的就是 `poke`，手滑五下不该把它逼走。`state_of()` 里 `coax` 只能把它带到 `pending`，要 `forgive` 才回 `home`。
   - `dreams.py`：梦话 / 出走纸条的本地文案池（按 branch 分组），AI 出不来时的兜底。
2. **`app/streak_service.py` / `evolution_service.py` / `runaway_service.py` / `presence_service.py`（及 router 内的编排段）— DB 编排**：行 ↔ 纯函数 state 的转换、落里程碑事件等。**关键：service 层不 commit**（注释「事务由 router 掌管」），只 `flush`。
   - `runaway_service.py`：出走三态**纯从事件流派生、零新增字段**——`runaway` / `coax` / `forgive` 三种事件的 `actor_user_id` 都记成 **keeper**（`forgive` 是**对方**点的头，但仍记 keeper：它标记的是「这只分身的事」，不是「谁按的按钮」），于是三个 `max(id)` 谁最新谁说了算，一次条件聚合查完，两只分身天然隔离。`provoked(..., pending_action=)` 让 `/actions` 在**这一下落库之前**就问出「它会不会走」。
   - `presence_service.py`：`touch()` / `partner_online()`。**全仓库只有 `POST /presence` 会 `touch`**，`GET /events`、`POST /actions` 一律只读——见「易踩的坑」。
3. **`app/routers/*.py` — HTTP + 事务边界**：唯一 `db.commit()` 的地方；并发首建（同一对同一天/同一 client_key 几乎同时到）会撞唯一约束，路由统一 `except IntegrityError → rollback → 重试一次`（见 `daily.py` 的 `_run()`）。

注册的路由（`app/main.py`，无前缀者路径即函数上写的）：`auth`、`couples`、`avatars`、`actions`、`events`、`daily`、`presence`、`story`、`runaway`、`push`，外加 `/health`。**无 Alembic**——启动时 `app/schema_sync.py` 的 `sync_schema()` 幂等对齐 schema（`docker-entrypoint.sh` 调）：先 `create_all` 建缺失的表，再按 `_ADDED_COLUMNS` 给**已存在的老表**补新增列。**给老模型加字段时，除了改 `models.py`，必须往 `_ADDED_COLUMNS` 补一行**——`create_all` 只建表、绝不加列，线上库表早就在了，漏了这步线上 `SELECT` 直接报 `Unknown column`。`main.py` 有 `lifespan`：`settings.enable_scheduler`（默认 True）时起 APScheduler，分两类挂 job —— **玩法 job 无条件挂**（`live_scheduler` 的分身梦话每天 1 次），**推送提醒 job 只在配了 VAPID 私钥时挂**（火苗每天 1 次 + 每日一问催答每天 N 次）。**离家出走没有 job**——判据是「1 小时内骂满 5 次」，第 5 次骂落库的那一刻当场生效，所以它长在 `POST /actions` 的事务里。**跑在 uvicorn 进程内、依赖单 worker**（改多 worker 会重复触发）。`conftest.py` 里 `enable_scheduler=False`——`with TestClient(app)` 会跑 lifespan，否则每个用例都拉起一个 APScheduler。

### 数据模型（`app/models.py`）

- `User`：含 `gender`、`ai_reply_enabled`（分身要不要自动接话，**默认 False**）、`ai_count` / `ai_count_date`（AI 每日额度）、`last_seen_at`（在线心跳）。
- `Couple`：`user_a_id` / `user_b_id` / `status`(active/pending) / `pair_code`。
- `Avatar`：配对后生成**两只镜像分身**，靠 `subject_user_id`（代表谁）+ `keeper_user_id`（谁在养）区分；`appearance` / `persona` / `evolution` 为 JSON。`evolution` 存 `{stage,branch,exp,care,history}`（见 `rules/evolution.py`），`GET /avatars/pet` = 我养的那只（我把 TA 养成了什么样），`GET /avatars/mine` = TA 养的那只（**我在 TA 眼里被养成了什么样**）。进化形态经 `_persona_for()` 注入 AI system prompt（`prompt.py` 的 `_BRANCH_HINT`），黑化版说话就真的毒舌。
- `CoupleStats`：PK=`couple_id`，`stats` **JSON 列**存 `{grievance,dogfood,miss,intimacy}`（改数值 = 复制 dict 再整体赋值，别原地改）。
- `CoupleStreak`：PK=`couple_id`，`count` + 四个日期字段（`last_both_day`/`a_active_day`/`b_active_day`/`rescue_day`）。
- `Event`：统一时间线，`kind ∈ {action, ai_reaction, real_response, system, daily_qa, story}`，`parent_event_id` 串起「每日一问父题 + 两条答案」。
- `DailyQuestion`(唯一约束 couple+day) / `DailyAnswer`(唯一约束 question+user，带 `client_key`)。
- `Story`(唯一约束 couple+day) / `StoryRound`(唯一约束 story+round_no，`options=[]` 即结局幕) / `StoryChoice`(唯一约束 round+user)。三个唯一约束同时兼作并发护栏。
- `PushSubscription`：一个浏览器的 Web Push 订阅（`user_id` + `endpoint`(唯一) + `p256dh`/`auth`）；一个 user 可多设备多行，发推遇 404/410 按 endpoint 删。

### AI 集成（`app/ai/`，DeepSeek）

分层同样清晰、且**核心承诺是「永不因 AI 失败而报错」**：

- `client.py`：`chat_completion(messages, *, max_tokens=None, temperature=None)` 纯调用+解析，失败抛 `AIError`，不兜底。**默认的 `deepseek_max_tokens=200` / `temperature=1.3` 是为「分身回一句话」调的**；要长文本或严格格式的调用方必须自己传（见 `ai/story.py`：200 token 会把故事截断，1.3 会把「场景：…／A. …」的格式写崩）。
- `prompt.py`：纯函数把 **人设 + 基调 + 性别 + 此刻心情（某值≥60 就带情绪）+ 最近对话** 拼成 messages。
- `deepseek.py`：`generate_reaction(...)` 编排——**无 key 或任何异常都落本地兜底**，返回 `(text, used_ai)`，永不抛。
- `quota.py`：`ai_quota_available` / `record_ai_usage` 做每人每日上限（`daily_chat_cap`，跨 UTC 日归零）。
- `daily_question.py`：**每日一问的 AI 出题**（`generate_question`）。flavor 仍由 rules 轮换,AI 只生成该味的一句题；无 key/失败回落 `daily_questions.pick_local`。每对每天一次的共享资源,**不占个人额度**(不碰 quota),生成入口在 `daily.py:_get_or_create_question`(只在当天首建时调一次,之后读库)。
- `story.py`：**剧情副本的开场/续写/结局**。要的不是一句话而是「场景 + 2~3 个选项」的**结构化输出** → 严格格式 + 正则解析（`_parse`），**解析失败等同调用失败**，一律落 `rules/stories.py` 的本地剧本。本地兜底时会把两人的选择回显进场景开头——**只能用昵称、不能写「你/TA」**，因为 scene 是存一份、两个人共读的。同样是情侣级共享资源，不碰 quota。

> 加任何新的 AI 能力，照 `deepseek.py` / `daily_question.py` 的范式走：先查 key（按需查额度）→ 拼 prompt → try 调用 → except 落本地兜底，保证离线可玩、CI 无 key 也绿。

### 同框（「TA 也在线」）

**核心不变式：全仓库只有 `POST /presence` 写 `users.last_seen_at`。** `GET /events`、`POST /actions` 都只**读**。别图省事把心跳挂进它们——`tests/test_feed.py` 里「alice 先 `GET /events`、bob 随后发动作」会让 alice 凭空"在线"、bob 的数值被 ×2，一片测试跟着变红，而且 GET 变写操作本身就脏。`tests/test_presence.py::test_only_the_presence_endpoint_writes_the_heartbeat` 钉死了这条。

- 前端 `hooks/usePresence.ts` 用 **`useQuery` + `refetchInterval: 10s`** 打心跳，**不是手写 `setInterval`**：TanStack 的 `refetchIntervalInBackground` 默认 false → 切后台自动停 → 我自动对 TA 显示为离线；全局 `refetchOnWindowFocus` 让回前台瞬间重新亮起。「切后台就下线」的语义是白捡的。
- 同框时 `apply_action(..., multiplier=2)`，**负面也翻倍**；`together` 由服务端算（读对方 `last_seen_at`），不信客户端。**但 `evolution_service.bump_care` 不翻倍**——care 数的是「做了几次」，翻倍会把分支占比算歪。
- `_bundle` 里的 `together` 是「TA 此刻在不在」的即时标志，不是这次动作的历史记录；**幂等重放返回的是当下值**。
- `headpat` 同框限定，后端 409 `not_together`；这道拦截放在**幂等早返回之后**（同框时发出的那一下，重放时不该因为 TA 刚下线被打回）。

### 剧情副本（`routers/story.py`）

同回合双人抉择：两人各选一个，**都选完才互看**，AI 同时写出两个选择的后果 + 下一幕。

**「推进下一幕」必须是自愈的。** `daily.py:129` 用 `len(answers) == 2` 判断「第二个人到齐」，但两人几乎同时提交时各自事务只看得见自己 `flush` 的那条（MySQL InnoDB 默认 REPEATABLE READ 快照隔离），**两边都数到 1**。每日一问顶多少落一条时间线事件，剧情副本却会**永远卡住不再续写**。所以抽出 `_advance_if_ready(db, couple, story)`，在 `POST /story/choose`（快路径）**和 `GET /story`（自愈路径）**里都调：写路径漏掉的那一幕，下一次任何一方轮询都会补上。`tests/test_story.py::test_a_get_heals_a_round_that_the_write_path_raced_past` 直接绕过 `choose` 插第二条 choice 来确定性复现这个竞态。

- 三个唯一约束兼作并发护栏，撞了就照 `daily.py` 的 `except IntegrityError → rollback → 重试一次`。
- **代价是有意接受的**：AI 调用那几秒里对方的轮询 GET 也会走到生成分支，两边各调一次 AI、一边 INSERT 撞唯一约束回滚。结果正确，偶尔多烧一次调用。**不加行锁**——锁 story 行做 AI 调用会把对方的 GET 一起阻塞几秒。
- `_get_or_create_story` 优先取 `status=='active'` 的那章（**不看 day** → 没打完的顺延），否则今天那章（已完结就是它），否则新建。`unique(couple_id, day)` 天然保证一天一章。
- 结局幕 `options == []`，落一条 `Event(kind="story", client_key=f"story-{id}")`，唯一约束保证只落一条。

### 离家出走（`rules/runaway.py` + `runaway_service.py` + `routers/runaway.py`）

**1 小时内骂满 5 次，第 5 次骂的响应还没返回，它就已经走了**——没有定时任务，触发点长在 `POST /actions` 里，跟那次动作同一个事务。三态：`home` →(骂满)→ `away` →(keeper 哄)→ `pending` →(**对方**点头)→ `home`。

- **`HOSTILE` 只有 `scold`**。`poke` 是首页点一下分身就会发的动作，把它算进敌意 = 手滑五下分身就跑了。
- **判据在 AI 之前问**：`provoked(..., pending_action=body.action_type)` 把「这一下还没落库的动作」算进窗口。它要走就不回嘴，那次 AI 调用直接省掉（`bolted or not user.ai_reply_enabled` → `reaction_text = None`）。
- **`coax` 只能把它带到门口。** 回不回家是「它代表的那个人」说了算 → `POST /runaway/forgive`，按钮长在**对方**的首页上（`GET /avatars/mine` 也带三态）。`pending` 期间**连 `coax` 都拦**（409 `awaiting_forgiveness`），否则 coax 的「委屈 −30 / 亲密 +5」能在等待期里无限刷。
- 纸条事件 `Event(kind="system", action_type="runaway")` **不挂 parent**（同进化旁白）：`_bundle` 只收 action 的子事件，挂上去会跟「委屈爆表」旁白抢 `HomeScreen` 的 `comfortText`。前端靠 `bundle.ran_away` 换屏。
- 前端：三态的三个标记有一半是**对面**落下的（TA 骂跑了我 / TA 来哄了 / TA 点了头），只能靠 `useFeed` 的 3 秒轮询发现——`HomeScreen` 盯住 `RUNAWAY_MARKERS` 的最大事件 id，见涨就 `invalidateQueries` 重取两只分身。**两只分身可能同时在外面**，所以 `ForgiveCard` 也要能塞进 `RunawayScreen` 里（`children`），否则谁都回不了家。

### 消息推送（Web Push / PWA）

**契约同 AI：无 VAPID 私钥 = 整套静默关闭、绝不因推送失败而影响主流程、永不抛。** 分两类：

- **实时推送**：挂在现有路由 `db.commit()` 之后，用 FastAPI `BackgroundTasks` 异步发（不阻塞响应）。挂点：`actions.py`(对方发动作 / 委屈爆表)、`events.py`(本尊回应)、`daily.py`(每日一问首答催对方)。**partner_id 必须在 commit 前从 couple 取成 int**（`push_service.partner_of`），别把 ORM 对象丢进后台任务。
- **定时推送**：`push_scheduler` 里两个 job，都自开 `SessionLocal()`、扫活跃情侣、模块级 `_today()` 供测试注入。① `remind_dying_streaks()` 每天单次触发（`streak_reminder_hour`），给火苗「今晚会灭 / 已断可救」的人发；② `remind_unanswered_daily()` 每天触发多次（`daily_reminder_hours`，默认 UTC+8 的 10 点/14 点各一次），给当天还没答每日一问的人发催答（题还没生成也算没答；`tag:"daily"` 和实时那条同 tag 会折叠）。
- `push_service.send_to_user(user_id, payload)`：核心发送原语，**自开 `SessionLocal()`**（不走请求作用域，供后台任务/定时 job 复用），逐条 `pywebpush.webpush`，404/410 删失效订阅。payload=`{title,body,url,tag}`，`tag` 让 SW 折叠同类通知。
- **VAPID 密钥**：`app/gen_vapid.py` 生成（`python -m app.gen_vapid`），公钥走 `GET /push/public-key` 下发前端、私钥只在服务端；`config.py` 里空 key = 关闭（同 `deepseek_api_key`）。
- 前端：`public/sw.js`(手写最小 SW，处理 push/notificationclick/message，前台聚焦时抑制)、`main.tsx` 注册、`hooks/usePush.ts`(开关逻辑 + `ensurePushSubscribed` 静默补订)、开关 UI 在「⚙️我」页签。**iOS 需装到主屏幕、需 HTTPS**。
- **主屏图标未读角标（Badging API）**：`navigator.setAppBadge(n)`，iOS 16.4+ 且装到主屏 + 已授通知权限才有（前提与 Web Push 完全重合），不支持则静默跳过。**Web Push 不像 APNs 能靠 payload 自动 +1，数字得自己算**：SW 每次被唤醒都可能是全新全局作用域，所以计数落在 IndexedDB(`couple-badge/kv/unread`)，收一条推送 +1；`notificationclick` 与页面回前台发来的 `postMessage({type:'clear-badge'})` 都会清零（`src/push/appBadge.ts` + `MainShell` 的 `visibilitychange`）。前台聚焦时既不弹通知也不涨角标。服务端全程不参与——它没记「谁读到哪条」，未读是纯客户端概念（另见 `shell/badge.ts` 的页内红点）。
- `sw.js` 不走打包、没法 import，单测靠把源码读进来在假的 `ServiceWorkerGlobalScope` 里 `new Function(...)` 跑（见 `src/push/sw.test.ts`，`indexedDB` 用 `fake-indexeddb` 的 `new IDBFactory()` 每例一份）。

### 前端外壳与流程（状态驱动，非路由驱动）

只有 `/login`、`/register` 走 React Router；登录后全部落在 catch-all `/*` 后面。`App.tsx` 的 `Gate` 是一条**靠服务端查询逐级放行的漏斗**：`login → 配对(PairScreen) → 捏自己的分身(AvatarCreateScreen) → MainShell`，每一步 gate 在一个 query 上（`useCouple` 状态 none/pending/active、`useMyAvatar` 名字是否为空），不是靠 URL。进 `MainShell` 后四个页签（🏠TA / 💬聊天 / 🎭剧情 / ⚙️我）是本地 `useState`，也不走路由。新消息未读红点、分身主动撩你(`useNudge`)、在线心跳(`usePresence`)、剧情轮到你的红点(`useStory().data.my_turn`)都挂在 `MainShell` 上跨页签生效。🎭 的红点**不走** `shell/badge.ts`——那套是「未读事件 id 游标」，语义不同。

### 前端数据层（这是理解前端的关键）

- **`src/api/client.ts`**：`apiRequest(method, path, body?)`，base=`/api`，自动注入 `Bearer` token，非 2xx 抛 `ApiError(status, detail)`，401 触发 `onUnauthorized`。各领域 API 拆在 `src/api/{daily,events,actions,couples,avatars,auth}.ts`。
- **`src/hooks/*` + TanStack Query**：query key 集中在 `dailyKey`/`feedKey`/`statsKey`/`storyKey`/`presenceKey`。轮询：`useDaily` 20s（等对方答题解锁）、`useStory` 20s（等对方抉择）、`useFeed` 3s（拉新消息）、`usePresence` 10s（心跳）。**这些 `refetchInterval` 切后台都会自动暂停**——`usePresence` 正是靠这个实现「关页面就下线」。写缓存的约定——**mutation 成功后把服务端返回直接 `qc.setQueryData` 回写**（如答题/续火/抉择），必要时才 `invalidateQueries`。
- **数值缓存是「被动镜像」**：`StatDashboard` 用 `enabled:false` 的 `useQuery(statsKey)` 只读，从不自己发请求；`useFeed`/`useAction` 成功时 `setQueryData(statsKey, ...)` 喂给它。改数值展示要顺着这条链。
- **幂等**：`useIdempotencyKey` 生成 `client_key` 放进 mutation variables，重试复用同一 key；`retry` 只在**非 `ApiError`**（即网络错误）时进行，4xx 立即冒泡。
- **时间线懒加载**：`useFeed` 的 `mergeEvents`/`appendToFeed`/`useLoadOlder`，`cursor`=最新 id 向前轮询、`oldestLoaded`=向上翻页游标。

### 性别主题（男蓝 / 女淡粉）

CSS 变量按 `<html data-theme>` 切换：`src/theme.ts` `applyTheme(gender)` 写 `document.documentElement.dataset.theme`，`AuthContext` 依登录者性别调用它；配色在 `src/styles/tokens.css`（`:root` 中性薰衣草、`[data-theme='male']` 蓝、`[data-theme='female']` 淡粉）。**新 UI 一律用 `var(--primary / --primary-soft / --primary-strong / --primary-ink / --aura)`，不要写死颜色**，才能自动跟随性别 + 心情光环。

## 测试约定

- **后端**：`tests/conftest.py` 用内存 SQLite + `StaticPool` + `dependency_overrides[get_db]`；`client` / `auth_headers` 是基础 fixture。控制「今天」用 `monkeypatch.setattr(app.streak_service, "_today", lambda: date(...))`（火苗/每日一问的日界都走它；`live_scheduler` / `routers.avatars` 各有自己的 `_today()`，同样可注入）。**`client` fixture 还把 `push_service` / `push_scheduler` / `live_scheduler` 的 `SessionLocal` 重定向到同一个内存库**（它们自开会话发推/扫库），并挂 `client.session_factory` 供测试开同库会话查数据；测推送时 `monkeypatch` 掉 `app.push_service.webpush`（绝不真发网）。
- **前端**：Vitest + jsdom + **MSW**。默认接口桩在 `src/test/handlers.ts`，单测里用 `server.use(http...)` 覆盖；渲染用 `src/test/utils.tsx` 的 `renderWithProviders`（内置 QueryClient `retry:false` + MemoryRouter，**返回值带 `queryClient`**：要模拟「轮询把新事件捞回来」就 `qc.setQueryData(feedKey(1), ...)`，别去等真实的 3 秒）。注意 `setup.ts` 设了 `onUnhandledRequest:'error'`——**测试里发出的每个请求都必须有 mock**，否则直接失败。

## 易踩的坑

- 改 `CoupleStats.stats` / `Avatar.persona` 等 JSON 列：**复制成新 dict 再整体赋值**，SQLAlchemy 才认得脏（原地改字段不会触发更新）。
- 新增/改动纯函数的返回结构时，注意 `test_rules_streak.py` / `test_rules_evolution.py` 里有**整字典相等**断言，会一并需要更新。
- **加新动作**（往 `ACTION_TYPES` 里塞）要连带改**六处**，少一处就红或白改：`ACTION_EFFECTS`、`LOCAL_REACTIONS`（非 AI 动作必须有，且 `test_actions.py` 强制**每个动作 ≥50 条不重样**）、`rules/evolution.py` 的 `CARE_WEIGHTS`（**不加就是 0 经验，白做**）和 `BRANCH_BUCKETS`（**不加就完全不影响分支**——`decide_branch` 的分母只是各桶之和）、`actions.py` 的 `_ACTION_PUSH`、前端 `src/actions.ts` 的 `ACTION_VERB`；还得同步 `test_rules_actions.py` 里 `set(ACTION_TYPES) == {...}` 的**整集合断言**。
- **后端测试里连骂 5 次，分身会当场跑掉**，之后所有动作都 409 `pet_away`。要压数值/刷经验的用例得先插一个安抚动作（`hug` 之类）——1 小时窗口里 `soothe > 0` 就既往不咎。`test_safety_valve.py` / `test_push_realtime.py` / `test_actions.py` 里那几行 `_act(..., "hug", ...)` 就是干这个的，别顺手删。
- **前端新接口必须补 MSW 桩**：`src/test/setup.ts` 设了 `onUnhandledRequest:'error'`。`MainShell` 会无条件拉 `POST /api/presence` 和 `GET /api/story`，`handlers.ts` 里都有默认桩——漏了会让**所有渲染 MainShell 的测试**（`App.test.tsx` 等）直接红。`/api/avatars/pet`、`/api/avatars/mine`、`POST /api/runaway/forgive` 同理（`HomeScreen` 现在**无条件**拉 `/avatars/mine`——它既管同框贴贴，也管「TA 把我气跑了」的点头卡）；改这些端点的返回结构时，各测试文件里 `server.use(...)` 的覆盖桩也要一起改。
- **两人同时提交时，各自事务里数不到对方那一条**（MySQL 快照隔离）。任何「等两个人都做完才解锁下一步」的功能，都不能只靠写路径的 `len(...) == 2`——要么像 `story.py` 那样在 GET 里加一条自愈路径，要么接受偶尔漏掉（`daily.py` 就是后者，只少一条时间线事件）。
- 「可续火」的火苗态是 `count:0 / at_risk:false`（`view()` 判定为已断），UI 判断要用 `rescuable` 字段而非 `at_risk`。
- **`global.css` 是一个全局命名空间，没有 CSS Modules**：新起的 class 名先 `grep` 一遍。同名后写的那条赢，而 jsdom 不算样式，**整套单测会全绿、页面却是烂的**（`.emoji-trigger` 撞过一次：聊天输入框的表情键 vs 换造型的分身按钮，后者被拽成了 `position:absolute` 的 30px 圆点）。改完 UI 至少截一次图。
- **弹层要 `createPortal` 到 body**：长在触发它的子树里，会把外面的 `text-align` / 字号一路继承进来（`.center` 就干过这事），且 `position:fixed` 一旦碰上带 `transform` 的祖先（framer-motion 到处都是）就改锚到那个祖先上。见 `components/EmojiPicker.tsx`。
- **建索引/唯一约束的列别用 `Text`**：SQLite（测试）不挑、能过，但 MySQL 建表直接报 `1170 BLOB/TEXT column used in key specification without a key length`，后端启动时 `create_all` 会一直失败、卡在"数据库还没准备好"。用定长 `String(N)`（见 `PushSubscription.endpoint = String(512)`）。改 schema 后记得 `docker compose up -d --build backend` 重建镜像,否则 `down -v` 清库重来会再炸。
