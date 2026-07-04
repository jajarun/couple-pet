# 情侣分身宠物 · 前端核心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用像素电子宠物机风格的移动端 React 前端，把已合并的后端核心（认证/配对/分身/动作流/事件流/本尊回应）打通成可双人真配对试玩的完整闭环。

**Architecture:** 纯客户端 SPA，Vite + React + TS。服务端状态全交给 TanStack Query（轮询事件流、游标累积、失败退避重试）；手感层用 Framer Motion 做微动效并收敛成一组全局复用组件；样式手写 CSS + 像素设计令牌。前端从不自算数值，永远显示服务端返回的 `stats`。

**Tech Stack:** Vite 5, React 18, TypeScript 5, @tanstack/react-query 5, framer-motion 11, react-router-dom 6；测试 Vitest + @testing-library/react + @testing-library/user-event + jsdom + MSW 2。

## Global Constraints

以下为项目级约束，每个任务隐含包含：

- **目录**：前端全部代码在 `frontend/`（与 `backend/` 平级）。所有路径以 `frontend/` 为根。
- **API 接入**：`import.meta.env.VITE_API_BASE ?? '/api'` 为 base；开发期 Vite proxy 把 `/api/*` 转发到 `http://localhost:8000/*`（去掉 `/api` 前缀）。所有鉴权请求带 `Authorization: Bearer <token>`。
- **后端错误体**：FastAPI `HTTPException` 返回 `{"detail": "..."}`；`ApiError` 从中取 `detail`。
- **数值 `stats`**：4 键 `grievance` / `dogfood` / `miss` / `intimacy`，均 0–100 整数。**前端从不自算，永远显示服务端返回值。**
- **动作类型**：`scold` / `poke` / `feed_dogfood` / `hug` / `miss_you` / `apologize` / `chat`（共 7 个）。
- **事件 kind**：`action` / `ai_reaction` / `real_response` / `system`；`actor_user_id` 为 `null` 表示系统/AI。
- **幂等**：每次动作/回应用 `crypto.randomUUID()` 生成 `client_key`，**重试复用同一个键**，成功后丢弃。
- **交互质感（体验底线，来自设计总纲 §7）**：动效 <300ms、不挡操作、可连点；任何加载/等待用 `LoadingBanter` 无厘头台词轮播顶上，绝不空屏；失败用卖萌文案兜底、**绝不糊报错、绝不改数值**。
- **视觉**：像素电子宠物机主壳 + meme 文案 + 情侣软萌配色；文案全中文。
- **DeepSeek 现状**：后端是确定性 stub、聊天非流式；前端打字机是客户端逐字揭示（数据源以后无痛替换成流式）。
- **每个任务走 TDD**：写失败测试 → 跑确认失败 → 最小实现 → 跑确认通过 → 提交。测试用 Vitest + RTL + MSW，**不碰真后端/真 DeepSeek**。
- **测试命令**：`npx vitest run <file>`（一次性跑，不进 watch）。

---

## 文件结构总览

```
frontend/
  package.json  vite.config.ts  tsconfig.json  index.html  .gitignore
  src/
    main.tsx  App.tsx  vite-env.d.ts
    api/     client.ts  types.ts  auth.ts  couples.ts  avatars.ts  actions.ts  events.ts
    auth/    AuthContext.tsx  LoginScreen.tsx  RegisterScreen.tsx
    onboarding/  PairScreen.tsx  AvatarCreateScreen.tsx
    home/    HomeScreen.tsx  StatDashboard.tsx  ActionBar.tsx
    feed/    FeedScreen.tsx  EventItem.tsx
    chat/    ChatScreen.tsx
    me/      MyAvatarScreen.tsx
    shell/   MainShell.tsx
    components/  PixelPanel.tsx  TabBar.tsx  PressButton.tsx  StatGauge.tsx
                 SpeechBubble.tsx  LoadingBanter.tsx  PetSprite.tsx
    hooks/   useCouple.ts  useAvatar.ts  useFeed.ts  useAction.ts  useIdempotencyKey.ts
    styles/  tokens.css  global.css
    banter.ts
    test/    setup.ts  server.ts  handlers.ts  utils.tsx
```

---

## Task 1: 脚手架与工具链

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/index.html`, `frontend/.gitignore`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/vite-env.d.ts`
- Create: `frontend/src/test/setup.ts`, `frontend/src/test/server.ts`, `frontend/src/test/handlers.ts`, `frontend/src/test/utils.tsx`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- Produces: `renderWithProviders(ui)` from `src/test/utils.tsx` — wraps a fresh `QueryClient` (retry:false) + `MemoryRouter`; `server` from `src/test/server.ts` (MSW node server); `handlers` array from `src/test/handlers.ts`.

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "couple-pet-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.51.0",
    "framer-motion": "^11.3.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.24.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.6",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^24.1.0",
    "msw": "^2.3.1",
    "typescript": "^5.5.3",
    "vite": "^5.3.3",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: Create config files**

`frontend/vite.config.ts`:
```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

`frontend/tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <title>分身宠物</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/.gitignore`:
```
node_modules
dist
*.local
.DS_Store
```

`frontend/src/vite-env.d.ts`:
```ts
/// <reference types="vite/client" />
```

- [ ] **Step 3: Create app entry + minimal App**

`frontend/src/App.tsx`:
```tsx
export default function App() {
  return <div>分身宠物孵化中…</div>
}
```

`frontend/src/main.tsx`:
```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './styles/tokens.css'
import './styles/global.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 2, refetchOnWindowFocus: true } },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
```

> Note: `styles/tokens.css` and `styles/global.css` are created in Task 3. For now create empty placeholder files so the import resolves:
> `frontend/src/styles/tokens.css` (empty), `frontend/src/styles/global.css` (empty).

- [ ] **Step 4: Create MSW + test harness**

`frontend/src/test/handlers.ts`:
```ts
import { http, HttpResponse } from 'msw'

// Per-test handlers are added via server.use(...). Base handlers empty by default.
export const handlers = []
```

`frontend/src/test/server.ts`:
```ts
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
```

`frontend/src/test/setup.ts`:
```ts
import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

`frontend/src/test/utils.tsx`:
```tsx
import { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

export function renderWithProviders(ui: ReactElement, route = '/') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}
```

- [ ] **Step 5: Write the smoke test**

`frontend/src/App.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import { renderWithProviders } from './test/utils'
import App from './App'

test('renders the app root', () => {
  renderWithProviders(<App />)
  expect(screen.getByText(/分身宠物孵化中/)).toBeInTheDocument()
})
```

- [ ] **Step 6: Install and run**

Run:
```bash
cd frontend && npm install
```
Then:
```bash
cd frontend && npx vitest run src/App.test.tsx
```
Expected: 1 passed.

- [ ] **Step 7: Commit**

```bash
cd frontend && git add -A && git commit -m "chore(frontend): scaffold vite+react+ts with vitest/msw harness"
```

---

## Task 2: API 客户端与类型

**Files:**
- Create: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Produces:
  - `types.ts`: `AuthUser`, `AuthResponse`, `Stats`, `EventKind`, `GameEvent`, `Avatar`, `CoupleState`, `ActionBundle`, `FeedResponse`
  - `client.ts`: `class ApiError extends Error { status: number; detail: string }`; `setAuthToken(t: string | null): void`; `apiRequest<T>(method: string, path: string, body?: unknown): Promise<T>`

- [ ] **Step 1: Write the failing test**

`frontend/src/api/client.test.ts`:
```ts
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { apiRequest, ApiError, setAuthToken } from './client'

test('GET returns parsed JSON and sends bearer token when set', async () => {
  let seenAuth: string | null = null
  server.use(
    http.get('/api/ping', ({ request }) => {
      seenAuth = request.headers.get('authorization')
      return HttpResponse.json({ ok: true })
    }),
  )
  setAuthToken('tok123')
  const data = await apiRequest<{ ok: boolean }>('GET', '/ping')
  expect(data.ok).toBe(true)
  expect(seenAuth).toBe('Bearer tok123')
  setAuthToken(null)
})

test('non-2xx throws ApiError carrying status and detail', async () => {
  server.use(
    http.post('/api/auth/login', () =>
      HttpResponse.json({ detail: 'bad credentials' }, { status: 401 }),
    ),
  )
  await expect(apiRequest('POST', '/auth/login', { nickname: 'x' })).rejects.toMatchObject({
    status: 401,
    detail: 'bad credentials',
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/api/client.test.ts`
Expected: FAIL — cannot find module `./client`.

- [ ] **Step 3: Write minimal implementation**

`frontend/src/api/types.ts`:
```ts
export interface AuthUser {
  id: number
  nickname: string
}
export interface AuthResponse {
  access_token: string
  token_type: string
  user: AuthUser
}
export interface Stats {
  grievance: number
  dogfood: number
  miss: number
  intimacy: number
}
export type EventKind = 'action' | 'ai_reaction' | 'real_response' | 'system'
export interface GameEvent {
  id: number
  couple_id: number
  actor_user_id: number | null
  kind: EventKind
  action_type: string | null
  content: string
  parent_event_id: number | null
  created_at: string
}
export interface Avatar {
  id: number
  couple_id: number
  subject_user_id: number
  keeper_user_id: number
  name: string
  appearance: Record<string, unknown>
  persona: Record<string, unknown>
}
export type CoupleState =
  | { couple_id: number; status: 'active'; partner_id: number }
  | { couple_id: number; status: 'pending'; pair_code: string }
  | { couple_id: null; status: 'none' }
export interface ActionBundle {
  events: GameEvent[]
  stats: Stats
}
export interface FeedResponse {
  events: GameEvent[]
  stats: Stats
}
```

`frontend/src/api/client.ts`:
```ts
export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail)
    this.name = 'ApiError'
  }
}

const BASE = import.meta.env.VITE_API_BASE ?? '/api'

let authToken: string | null = null
export function setAuthToken(t: string | null) {
  authToken = t
}

export async function apiRequest<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = await res.json()
      if (j && typeof j.detail === 'string') detail = j.detail
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/api/client.test.ts`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): typed api client with bearer + ApiError"
```

---

## Task 3: 外壳原语（tokens / PixelPanel / TabBar）

**Files:**
- Create: `frontend/src/styles/tokens.css`, `frontend/src/styles/global.css` (replace the empty placeholders from Task 1)
- Create: `frontend/src/components/PixelPanel.tsx`, `frontend/src/components/TabBar.tsx`
- Test: `frontend/src/components/TabBar.test.tsx`

**Interfaces:**
- Produces:
  - `PixelPanel({ children }: { children: ReactNode })` — 机身外框容器
  - `TabItem = { key: string; label: string }`; `TabBar({ tabs, active, onChange }: { tabs: TabItem[]; active: string; onChange: (key: string) => void })`

- [ ] **Step 1: Write the failing test**

`frontend/src/components/TabBar.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { test, expect, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { TabBar } from './TabBar'

const tabs = [
  { key: 'home', label: '🏠 TA' },
  { key: 'feed', label: '🔔 事件流' },
]

test('marks the active tab and reports clicks', async () => {
  const onChange = vi.fn()
  renderWithProviders(<TabBar tabs={tabs} active="home" onChange={onChange} />)
  expect(screen.getByRole('tab', { name: '🏠 TA' })).toHaveAttribute('aria-selected', 'true')
  await userEvent.click(screen.getByRole('tab', { name: '🔔 事件流' }))
  expect(onChange).toHaveBeenCalledWith('feed')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/TabBar.test.tsx`
Expected: FAIL — cannot find module `./TabBar`.

- [ ] **Step 3: Write minimal implementation**

`frontend/src/styles/tokens.css`:
```css
:root {
  --bg: #0f1020;
  --machine: #6c7cff;
  --screen: #cde8b4;      /* 复古点阵绿屏 */
  --screen-ink: #1c2a14;
  --panel: #2a2c47;
  --ink: #f4f4ff;
  --accent: #ff6b9d;      /* 情侣软萌粉 */
  --warn: #ff5252;
  --good: #7be0a0;
  --radius: 10px;
  --shadow-press: inset 0 3px 0 rgba(0, 0, 0, 0.35);
  --font-pixel: 'Courier New', ui-monospace, monospace;
}
* { box-sizing: border-box; }
html, body, #root { height: 100%; margin: 0; }
body {
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font-pixel);
  -webkit-font-smoothing: none;
  image-rendering: pixelated;
}
```

`frontend/src/styles/global.css`:
```css
button { font-family: inherit; cursor: pointer; }
input, textarea { font-family: inherit; }
.screen {
  background: var(--screen);
  color: var(--screen-ink);
  border: 4px solid #101010;
  border-radius: 6px;
}
```

`frontend/src/components/PixelPanel.tsx`:
```tsx
import { ReactNode } from 'react'

export function PixelPanel({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        maxWidth: 440,
        margin: '0 auto',
        minHeight: '100dvh',
        background: 'var(--machine)',
        border: '6px solid #101010',
        borderRadius: 'var(--radius)',
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {children}
    </div>
  )
}
```

`frontend/src/components/TabBar.tsx`:
```tsx
export type TabItem = { key: string; label: string }

export function TabBar({
  tabs,
  active,
  onChange,
}: {
  tabs: TabItem[]
  active: string
  onChange: (key: string) => void
}) {
  return (
    <div role="tablist" style={{ display: 'flex', gap: 6, marginTop: 8 }}>
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={t.key === active}
          onClick={() => onChange(t.key)}
          style={{
            flex: 1,
            padding: '10px 4px',
            border: '3px solid #101010',
            borderRadius: 6,
            background: t.key === active ? 'var(--accent)' : 'var(--panel)',
            color: 'var(--ink)',
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/TabBar.test.tsx`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): pixel shell tokens + PixelPanel + TabBar"
```

---

## Task 4: 交互原语（PressButton / StatGauge）

**Files:**
- Create: `frontend/src/components/PressButton.tsx`, `frontend/src/components/StatGauge.tsx`
- Test: `frontend/src/components/PressButton.test.tsx`, `frontend/src/components/StatGauge.test.tsx`

**Interfaces:**
- Produces:
  - `PressButton({ children, onPress, disabled, cooldownMs }: { children: ReactNode; onPress: () => void; disabled?: boolean; cooldownMs?: number })` — 点击后进入 `cooldownMs`（默认 800）冷却，冷却期禁用，防连点轰炸。
  - `StatGauge({ label, value, alarm }: { label: string; value: number; alarm?: boolean })` — 显示 0–100 数值 + 比例条；`alarm` 时加 `data-alarm="true"`。

- [ ] **Step 1: Write the failing tests**

`frontend/src/components/PressButton.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { test, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { PressButton } from './PressButton'

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }))
afterEach(() => vi.useRealTimers())

test('fires onPress then disables during cooldown, re-enables after', async () => {
  const onPress = vi.fn()
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
  renderWithProviders(
    <PressButton onPress={onPress} cooldownMs={800}>
      骂
    </PressButton>,
  )
  const btn = screen.getByRole('button', { name: '骂' })
  await user.click(btn)
  expect(onPress).toHaveBeenCalledTimes(1)
  expect(btn).toBeDisabled()
  await user.click(btn)
  expect(onPress).toHaveBeenCalledTimes(1) // still disabled, no second fire
  vi.advanceTimersByTime(800)
  expect(btn).not.toBeDisabled()
})
```

`frontend/src/components/StatGauge.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { StatGauge } from './StatGauge'

test('renders value and alarm flag', () => {
  renderWithProviders(<StatGauge label="委屈" value={85} alarm />)
  expect(screen.getByText('委屈')).toBeInTheDocument()
  expect(screen.getByText('85')).toBeInTheDocument()
  expect(screen.getByTestId('gauge-委屈')).toHaveAttribute('data-alarm', 'true')
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/PressButton.test.tsx src/components/StatGauge.test.tsx`
Expected: FAIL — modules not found.

- [ ] **Step 3: Write minimal implementations**

`frontend/src/components/PressButton.tsx`:
```tsx
import { ReactNode, useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

export function PressButton({
  children,
  onPress,
  disabled,
  cooldownMs = 800,
}: {
  children: ReactNode
  onPress: () => void
  disabled?: boolean
  cooldownMs?: number
}) {
  const [cooling, setCooling] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current)
  }, [])

  const handle = () => {
    if (disabled || cooling) return
    onPress()
    setCooling(true)
    timer.current = setTimeout(() => setCooling(false), cooldownMs)
  }

  return (
    <motion.button
      whileTap={{ scale: 0.9 }}
      onClick={handle}
      disabled={disabled || cooling}
      style={{
        padding: '12px 8px',
        border: '3px solid #101010',
        borderRadius: 8,
        background: disabled || cooling ? '#8a8aa0' : 'var(--panel)',
        color: 'var(--ink)',
        boxShadow: cooling ? 'var(--shadow-press)' : 'none',
      }}
    >
      {children}
    </motion.button>
  )
}
```

`frontend/src/components/StatGauge.tsx`:
```tsx
import { motion } from 'framer-motion'

export function StatGauge({
  label,
  value,
  alarm,
}: {
  label: string
  value: number
  alarm?: boolean
}) {
  const rounded = Math.round(value)
  const clamped = Math.max(0, Math.min(100, value))
  return (
    <div data-testid={`gauge-${label}`} data-alarm={alarm ? 'true' : 'false'} style={{ flex: 1 }}>
      <div style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between' }}>
        <span>{label}</span>
        {/* Plain text keeps the value deterministic for tests; key remount gives a pop on change. */}
        <motion.span
          key={rounded}
          initial={{ y: -6, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.25 }}
        >
          {rounded}
        </motion.span>
      </div>
      <div style={{ height: 8, border: '2px solid #101010', background: '#0003' }}>
        <motion.div
          animate={{ width: `${clamped}%` }}
          transition={{ duration: 0.4 }}
          style={{ height: '100%', background: alarm ? 'var(--warn)' : 'var(--good)' }}
        />
      </div>
    </div>
  )
}
```

> Note: the number is rendered as plain text (`{rounded}`) so RTL assertions are deterministic; the `key={rounded}` remount + bar `animate` supply the §7 "数值有过渡" feel without depending on animation timing in jsdom.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/PressButton.test.tsx src/components/StatGauge.test.tsx`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): PressButton (cooldown) + StatGauge (rolling number)"
```

---

## Task 5: 叙事原语（SpeechBubble / LoadingBanter / PetSprite）

**Files:**
- Create: `frontend/src/banter.ts`, `frontend/src/components/SpeechBubble.tsx`, `frontend/src/components/LoadingBanter.tsx`, `frontend/src/components/PetSprite.tsx`
- Test: `frontend/src/components/SpeechBubble.test.tsx`, `frontend/src/components/LoadingBanter.test.tsx`

**Interfaces:**
- Produces:
  - `banter.ts`: `export const BANTER_LINES: string[]`
  - `SpeechBubble({ text, typing }: { text: string; typing?: boolean })` — `typing` 时逐字揭示 `text`，否则整段显示
  - `LoadingBanter({ intervalMs }: { intervalMs?: number })` — 每 `intervalMs`（默认 1200）从 `BANTER_LINES` 轮播一条
  - `PetSprite({ face, reaction }: { face?: string; reaction?: string | null })` — 像素脸；`reaction` 变化时播放一次性抖动，`data-reaction` 反映当前反应

- [ ] **Step 1: Write the failing tests**

`frontend/src/components/SpeechBubble.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { test, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { SpeechBubble } from './SpeechBubble'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

test('typing mode eventually reveals the full text', () => {
  renderWithProviders(<SpeechBubble text="大猪蹄子" typing />)
  vi.advanceTimersByTime(2000)
  expect(screen.getByText('大猪蹄子')).toBeInTheDocument()
})

test('non-typing mode shows text immediately', () => {
  renderWithProviders(<SpeechBubble text="哼" />)
  expect(screen.getByText('哼')).toBeInTheDocument()
})
```

`frontend/src/components/LoadingBanter.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { test, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { LoadingBanter } from './LoadingBanter'
import { BANTER_LINES } from '../banter'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

test('cycles to a different banter line over time', () => {
  renderWithProviders(<LoadingBanter intervalMs={1200} />)
  const first = screen.getByTestId('banter').textContent
  vi.advanceTimersByTime(1200)
  const second = screen.getByTestId('banter').textContent
  expect(BANTER_LINES).toContain(second)
  expect(second).not.toBe(first)
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/SpeechBubble.test.tsx src/components/LoadingBanter.test.tsx`
Expected: FAIL — modules not found.

- [ ] **Step 3: Write minimal implementations**

`frontend/src/banter.ts`:
```ts
export const BANTER_LINES: string[] = [
  '分身正在偷偷补妆…',
  '正在把你的话翻译成人话…',
  '本尊正在酝酿一句诛心的…',
  '正在给分身充能，别催…',
  '正在翻旧账，稍等…',
  '分身卡了一下，正在重启灵魂…',
]
```

`frontend/src/components/SpeechBubble.tsx`:
```tsx
import { useEffect, useState } from 'react'

export function SpeechBubble({ text, typing }: { text: string; typing?: boolean }) {
  const [shown, setShown] = useState(typing ? '' : text)

  useEffect(() => {
    if (!typing) {
      setShown(text)
      return
    }
    setShown('')
    let i = 0
    const id = setInterval(() => {
      i += 1
      setShown(text.slice(0, i))
      if (i >= text.length) clearInterval(id)
    }, 45)
    return () => clearInterval(id)
  }, [text, typing])

  return (
    <div
      style={{
        display: 'inline-block',
        background: '#fff',
        color: '#111',
        border: '3px solid #101010',
        borderRadius: 10,
        padding: '8px 12px',
        maxWidth: '80%',
      }}
    >
      {shown}
    </div>
  )
}
```

`frontend/src/components/LoadingBanter.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { BANTER_LINES } from '../banter'

export function LoadingBanter({ intervalMs = 1200 }: { intervalMs?: number }) {
  const [i, setI] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setI((n) => (n + 1) % BANTER_LINES.length), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs])
  return (
    <div data-testid="banter" style={{ opacity: 0.85, fontSize: 13 }}>
      {BANTER_LINES[i]}
    </div>
  )
}
```

`frontend/src/components/PetSprite.tsx`:
```tsx
import { motion } from 'framer-motion'

export function PetSprite({ face = '◕‿◕', reaction }: { face?: string; reaction?: string | null }) {
  return (
    <motion.div
      data-testid="pet"
      data-reaction={reaction ?? ''}
      animate={reaction ? { rotate: [0, -8, 8, -4, 0], scale: [1, 1.05, 1] } : { y: [0, -2, 0] }}
      transition={reaction ? { duration: 0.4 } : { duration: 2, repeat: Infinity }}
      style={{ fontSize: 56, textAlign: 'center', padding: 16 }}
    >
      {face}
    </motion.div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/SpeechBubble.test.tsx src/components/LoadingBanter.test.tsx`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): SpeechBubble typewriter + LoadingBanter + PetSprite"
```

---

## Task 6: 认证上下文（AuthContext + api/auth）

> **环境要求**：Node ≥ 20（用到 `crypto.randomUUID`，Task 11 也依赖）。

**Files:**
- Create: `frontend/src/api/auth.ts`, `frontend/src/auth/AuthContext.tsx`
- Test: `frontend/src/auth/AuthContext.test.tsx`

**Interfaces:**
- Produces:
  - `auth.ts`: `registerUser(nickname, password): Promise<AuthResponse>`, `loginUser(nickname, password): Promise<AuthResponse>`
  - `AuthContext.tsx`: `AuthProvider({ children })`; `useAuth(): { user: AuthUser | null; token: string | null; login(nickname, password): Promise<void>; register(nickname, password): Promise<void>; logout(): void }`. Persists token/user to `localStorage` (`couple.token` / `couple.user`) and calls `setAuthToken`.

- [ ] **Step 1: Write the failing test**

`frontend/src/auth/AuthContext.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect, beforeEach } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { AuthProvider, useAuth } from './AuthContext'

function Harness() {
  const { user, login } = useAuth()
  return (
    <div>
      <button onClick={() => login('mimi', 'secret1').catch(() => {})}>login</button>
      <span>user:{user?.nickname ?? 'none'}</span>
    </div>
  )
}

beforeEach(() => localStorage.clear())

test('login stores the user and token', async () => {
  server.use(
    http.post('/api/auth/login', () =>
      HttpResponse.json({
        access_token: 'tok',
        token_type: 'bearer',
        user: { id: 1, nickname: 'mimi' },
      }),
    ),
  )
  renderWithProviders(
    <AuthProvider>
      <Harness />
    </AuthProvider>,
  )
  expect(screen.getByText('user:none')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'login' }))
  expect(await screen.findByText('user:mimi')).toBeInTheDocument()
  expect(localStorage.getItem('couple.token')).toBe('tok')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/auth/AuthContext.test.tsx`
Expected: FAIL — cannot find module `./AuthContext`.

- [ ] **Step 3: Write minimal implementation**

`frontend/src/api/auth.ts`:
```ts
import { apiRequest } from './client'
import { AuthResponse } from './types'

export function registerUser(nickname: string, password: string) {
  return apiRequest<AuthResponse>('POST', '/auth/register', { nickname, password })
}
export function loginUser(nickname: string, password: string) {
  return apiRequest<AuthResponse>('POST', '/auth/login', { nickname, password })
}
```

`frontend/src/auth/AuthContext.tsx`:
```tsx
import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { setAuthToken } from '../api/client'
import { registerUser, loginUser } from '../api/auth'
import { AuthUser } from '../api/types'

const TOKEN_KEY = 'couple.token'
const USER_KEY = 'couple.user'

interface AuthValue {
  user: AuthUser | null
  token: string | null
  login: (nickname: string, password: string) => Promise<void>
  register: (nickname: string, password: string) => Promise<void>
  logout: () => void
}
const AuthCtx = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState<AuthUser | null>(() => {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as AuthUser) : null
  })

  useEffect(() => {
    setAuthToken(token)
  }, [token])

  const apply = (t: string, u: AuthUser) => {
    localStorage.setItem(TOKEN_KEY, t)
    localStorage.setItem(USER_KEY, JSON.stringify(u))
    setAuthToken(t)
    setToken(t)
    setUser(u)
  }

  const login = async (nickname: string, password: string) => {
    const res = await loginUser(nickname, password)
    apply(res.access_token, res.user)
  }
  const register = async (nickname: string, password: string) => {
    const res = await registerUser(nickname, password)
    apply(res.access_token, res.user)
  }
  const logout = () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setAuthToken(null)
    setToken(null)
    setUser(null)
  }

  return (
    <AuthCtx.Provider value={{ user, token, login, register, logout }}>{children}</AuthCtx.Provider>
  )
}

export function useAuth() {
  const v = useContext(AuthCtx)
  if (!v) throw new Error('useAuth must be used within AuthProvider')
  return v
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/auth/AuthContext.test.tsx`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): AuthContext with token persistence"
```

---

## Task 7: 登录 / 注册屏

**Files:**
- Create: `frontend/src/auth/LoginScreen.tsx`, `frontend/src/auth/RegisterScreen.tsx`
- Test: `frontend/src/auth/LoginScreen.test.tsx`, `frontend/src/auth/RegisterScreen.test.tsx`

**Interfaces:**
- Consumes: `useAuth()` (Task 6); `ApiError` (Task 2); `react-router-dom` `Link`/`useNavigate`.
- Produces: `LoginScreen()`, `RegisterScreen()` — 表单，成功后 `useNavigate('/')`；失败按状态映射中文友好提示（不糊报错）。

- [ ] **Step 1: Write the failing tests**

`frontend/src/auth/LoginScreen.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect, beforeEach } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { AuthProvider } from './AuthContext'
import { LoginScreen } from './LoginScreen'

beforeEach(() => localStorage.clear())

test('wrong credentials show a friendly message, not a raw error', async () => {
  server.use(
    http.post('/api/auth/login', () =>
      HttpResponse.json({ detail: 'bad credentials' }, { status: 401 }),
    ),
  )
  renderWithProviders(
    <AuthProvider>
      <LoginScreen />
    </AuthProvider>,
  )
  await userEvent.type(screen.getByLabelText('昵称'), 'mimi')
  await userEvent.type(screen.getByLabelText('密码'), 'wrongpw')
  await userEvent.click(screen.getByRole('button', { name: '进去' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('账号或密码不对哦~')
})
```

`frontend/src/auth/RegisterScreen.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect, beforeEach } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { AuthProvider } from './AuthContext'
import { RegisterScreen } from './RegisterScreen'

beforeEach(() => localStorage.clear())

test('duplicate nickname shows a friendly message', async () => {
  server.use(
    http.post('/api/auth/register', () =>
      HttpResponse.json({ detail: 'nickname already taken' }, { status: 409 }),
    ),
  )
  renderWithProviders(
    <AuthProvider>
      <RegisterScreen />
    </AuthProvider>,
  )
  await userEvent.type(screen.getByLabelText('昵称'), 'mimi')
  await userEvent.type(screen.getByLabelText('密码'), 'secret1')
  await userEvent.click(screen.getByRole('button', { name: '注册' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('这名字被抢啦，换一个')
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/auth/LoginScreen.test.tsx src/auth/RegisterScreen.test.tsx`
Expected: FAIL — modules not found.

- [ ] **Step 3: Write minimal implementations**

`frontend/src/auth/LoginScreen.tsx`:
```tsx
import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { ApiError } from '../api/client'

export function LoginScreen() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [nickname, setNickname] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      await login(nickname, password)
      nav('/')
    } catch (e2) {
      setErr(
        e2 instanceof ApiError && e2.status === 401
          ? '账号或密码不对哦~'
          : '登录出了点岔子，再试一次~',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} style={{ display: 'grid', gap: 10, padding: 16 }}>
      <h2>登录</h2>
      <input aria-label="昵称" value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="昵称" />
      <input aria-label="密码" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="密码" />
      {err && (
        <div role="alert" style={{ color: 'var(--warn)' }}>
          {err}
        </div>
      )}
      <button type="submit" disabled={busy}>进去</button>
      <Link to="/register">还没账号？去注册</Link>
    </form>
  )
}
```

`frontend/src/auth/RegisterScreen.tsx`:
```tsx
import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { ApiError } from '../api/client'

export function RegisterScreen() {
  const { register } = useAuth()
  const nav = useNavigate()
  const [nickname, setNickname] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      await register(nickname, password)
      nav('/')
    } catch (e2) {
      if (e2 instanceof ApiError && e2.status === 409) setErr('这名字被抢啦，换一个')
      else if (e2 instanceof ApiError && e2.status === 422) setErr('密码至少 6 位哦')
      else setErr('注册出了点岔子，再试一次~')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} style={{ display: 'grid', gap: 10, padding: 16 }}>
      <h2>注册</h2>
      <input aria-label="昵称" value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="起个昵称" />
      <input aria-label="密码" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="密码（≥6 位）" />
      {err && (
        <div role="alert" style={{ color: 'var(--warn)' }}>
          {err}
        </div>
      )}
      <button type="submit" disabled={busy}>注册</button>
      <Link to="/login">已有账号？去登录</Link>
    </form>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/auth/LoginScreen.test.tsx src/auth/RegisterScreen.test.tsx`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): login + register screens with friendly errors"
```

---

## Task 8: 配对 / 分身数据层（api + hooks）

**Files:**
- Create: `frontend/src/api/couples.ts`, `frontend/src/api/avatars.ts`, `frontend/src/hooks/useCouple.ts`, `frontend/src/hooks/useAvatar.ts`
- Test: `frontend/src/hooks/useCouple.test.tsx`

**Interfaces:**
- Produces:
  - `couples.ts`: `getMyCouple(): Promise<CoupleState>`; `createCouple(): Promise<{couple_id, pair_code, status}>`; `joinCouple(pair_code): Promise<{couple_id, status}>`
  - `avatars.ts`: `getMyAvatar(): Promise<Avatar>`; `getPetAvatar(): Promise<Avatar>`; `updateMyAvatar(patch): Promise<Avatar>`
  - `useCouple(enabled): UseQueryResult<CoupleState>` — queryKey `['couple']`, pending 态每 2500ms 轮询直到非 pending
  - `useMyAvatar(enabled)` / `usePetAvatar(enabled)` — queryKeys `['avatar','mine']` / `['avatar','pet']`

- [ ] **Step 1: Write the failing test**

`frontend/src/hooks/useCouple.test.tsx`:
```tsx
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { ReactNode } from 'react'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { useCouple } from './useCouple'

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

test('useCouple fetches the active couple state', async () => {
  server.use(
    http.get('/api/couples/me', () =>
      HttpResponse.json({ couple_id: 7, status: 'active', partner_id: 2 }),
    ),
  )
  const { result } = renderHook(() => useCouple(true), { wrapper })
  await waitFor(() => expect(result.current.data).toBeDefined())
  expect(result.current.data).toMatchObject({ status: 'active', partner_id: 2 })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/useCouple.test.tsx`
Expected: FAIL — cannot find module `./useCouple`.

- [ ] **Step 3: Write minimal implementations**

`frontend/src/api/couples.ts`:
```ts
import { apiRequest } from './client'
import { CoupleState } from './types'

export function getMyCouple() {
  return apiRequest<CoupleState>('GET', '/couples/me')
}
export function createCouple() {
  return apiRequest<{ couple_id: number; pair_code: string; status: string }>('POST', '/couples')
}
export function joinCouple(pair_code: string) {
  return apiRequest<{ couple_id: number; status: string }>('POST', '/couples/join', { pair_code })
}
```

`frontend/src/api/avatars.ts`:
```ts
import { apiRequest } from './client'
import { Avatar } from './types'

export function getMyAvatar() {
  return apiRequest<Avatar>('GET', '/avatars/mine')
}
export function getPetAvatar() {
  return apiRequest<Avatar>('GET', '/avatars/pet')
}
export function updateMyAvatar(patch: {
  name?: string
  appearance?: Record<string, unknown>
  persona?: Record<string, unknown>
}) {
  return apiRequest<Avatar>('PUT', '/avatars/mine', patch)
}
```

`frontend/src/hooks/useCouple.ts`:
```ts
import { useQuery } from '@tanstack/react-query'
import { getMyCouple } from '../api/couples'

export function useCouple(enabled: boolean) {
  return useQuery({
    queryKey: ['couple'],
    queryFn: getMyCouple,
    enabled,
    refetchInterval: (q) => (q.state.data?.status === 'pending' ? 2500 : false),
  })
}
```

`frontend/src/hooks/useAvatar.ts`:
```ts
import { useQuery } from '@tanstack/react-query'
import { getMyAvatar, getPetAvatar } from '../api/avatars'

export function useMyAvatar(enabled: boolean) {
  return useQuery({ queryKey: ['avatar', 'mine'], queryFn: getMyAvatar, enabled })
}
export function usePetAvatar(enabled: boolean) {
  return useQuery({ queryKey: ['avatar', 'pet'], queryFn: getPetAvatar, enabled })
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/hooks/useCouple.test.tsx`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): couples/avatars api + useCouple/useAvatar hooks"
```

---

## Task 9: 配对屏（PairScreen）

**Files:**
- Create: `frontend/src/onboarding/PairScreen.tsx`
- Test: `frontend/src/onboarding/PairScreen.test.tsx`

**Interfaces:**
- Consumes: `createCouple`/`joinCouple` (Task 8), `ApiError` (Task 2), `LoadingBanter` (Task 5), `CoupleState` (Task 2).
- Produces: `PairScreen({ couple }: { couple: CoupleState })` — `pending` 显示邀请码 + 催 TA + LoadingBanter；`none` 显示「创建情侣」按钮 + 「输入邀请码加入」表单。成功后 `invalidateQueries(['couple'])`。

- [ ] **Step 1: Write the failing test**

`frontend/src/onboarding/PairScreen.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { PairScreen } from './PairScreen'

test('pending state shows the pair code and nudges the partner', () => {
  renderWithProviders(<PairScreen couple={{ couple_id: 1, status: 'pending', pair_code: 'A1B2C3' }} />)
  expect(screen.getByTestId('pair-code')).toHaveTextContent('A1B2C3')
  expect(screen.getByText(/催 TA/)).toBeInTheDocument()
})

test('invalid pair code shows a friendly message', async () => {
  server.use(
    http.post('/api/couples/join', () => HttpResponse.json({ detail: 'invalid pair code' }, { status: 404 })),
  )
  renderWithProviders(<PairScreen couple={{ couple_id: null, status: 'none' }} />)
  await userEvent.type(screen.getByLabelText('邀请码'), 'zzzzzz')
  await userEvent.click(screen.getByRole('button', { name: '加入' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('邀请码不对或失效啦')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/onboarding/PairScreen.test.tsx`
Expected: FAIL — cannot find module `./PairScreen`.

- [ ] **Step 3: Write minimal implementation**

`frontend/src/onboarding/PairScreen.tsx`:
```tsx
import { FormEvent, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createCouple, joinCouple } from '../api/couples'
import { CoupleState } from '../api/types'
import { ApiError } from '../api/client'
import { LoadingBanter } from '../components/LoadingBanter'

export function PairScreen({ couple }: { couple: CoupleState }) {
  const qc = useQueryClient()
  const [code, setCode] = useState('')
  const [err, setErr] = useState('')

  const create = useMutation({
    mutationFn: createCouple,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['couple'] }),
  })
  const join = useMutation({
    mutationFn: (c: string) => joinCouple(c),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['couple'] }),
    onError: (e) => {
      if (e instanceof ApiError && e.status === 404) setErr('邀请码不对或失效啦')
      else if (e instanceof ApiError && e.status === 400) setErr('不能跟自己配对呀')
      else if (e instanceof ApiError && e.status === 409) setErr('这对已经凑齐啦')
      else setErr('配对出了点岔子，再试一次~')
    },
  })

  if (couple.status === 'pending') {
    return (
      <div style={{ padding: 16, textAlign: 'center' }}>
        <h2>等对方进门…</h2>
        <p>把邀请码发给 TA：</p>
        <div data-testid="pair-code" style={{ fontSize: 32, letterSpacing: 4 }}>
          {couple.pair_code}
        </div>
        <p>催 TA 一下 👉「就等你了，快输码！」</p>
        <LoadingBanter />
      </div>
    )
  }

  const submitJoin = (e: FormEvent) => {
    e.preventDefault()
    setErr('')
    join.mutate(code.trim().toUpperCase())
  }

  return (
    <div style={{ padding: 16, display: 'grid', gap: 16 }}>
      <div>
        <h2>开一段关系</h2>
        <button onClick={() => create.mutate()} disabled={create.isPending}>
          创建情侣，拿邀请码
        </button>
      </div>
      <div>或</div>
      <form onSubmit={submitJoin} style={{ display: 'grid', gap: 8 }}>
        <input aria-label="邀请码" value={code} onChange={(e) => setCode(e.target.value)} placeholder="输入对方邀请码" />
        {err && (
          <div role="alert" style={{ color: 'var(--warn)' }}>
            {err}
          </div>
        )}
        <button type="submit" disabled={join.isPending}>加入</button>
      </form>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/onboarding/PairScreen.test.tsx`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): PairScreen create/join/waiting with edge handling"
```

---

## Task 10: 捏分身屏（AvatarCreateScreen）

**Files:**
- Create: `frontend/src/onboarding/AvatarCreateScreen.tsx`
- Test: `frontend/src/onboarding/AvatarCreateScreen.test.tsx`

**Interfaces:**
- Consumes: `updateMyAvatar` (Task 8).
- Produces: `AvatarCreateScreen()` — 选基调（radio）+ 名字 + emoji 造型 + 种子设定 → `PUT /avatars/mine { name, appearance:{emoji,tone}, persona:{tone,seed} }` → `invalidateQueries(['avatar','mine'])`。名字为空时禁用提交。

- [ ] **Step 1: Write the failing test**

`frontend/src/onboarding/AvatarCreateScreen.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { AvatarCreateScreen } from './AvatarCreateScreen'

test('submitting captures name/appearance/persona via PUT', async () => {
  let body: { name: string; appearance: Record<string, unknown>; persona: Record<string, unknown> } | null = null
  server.use(
    http.put('/api/avatars/mine', async ({ request }) => {
      body = (await request.json()) as typeof body
      return HttpResponse.json({
        id: 1, couple_id: 1, subject_user_id: 1, keeper_user_id: 2,
        name: body!.name, appearance: body!.appearance, persona: body!.persona,
      })
    }),
  )
  renderWithProviders(<AvatarCreateScreen />)
  await userEvent.click(screen.getByRole('radio', { name: '毒舌' }))
  await userEvent.type(screen.getByLabelText('名字'), '臭宝')
  await userEvent.click(screen.getByRole('button', { name: '就它了' }))
  await waitFor(() => expect(body).not.toBeNull())
  expect(body).toMatchObject({ name: '臭宝', appearance: { tone: '毒舌' }, persona: { tone: '毒舌' } })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/onboarding/AvatarCreateScreen.test.tsx`
Expected: FAIL — cannot find module `./AvatarCreateScreen`.

- [ ] **Step 3: Write minimal implementation**

`frontend/src/onboarding/AvatarCreateScreen.tsx`:
```tsx
import { FormEvent, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { updateMyAvatar } from '../api/avatars'

const TONES = ['毒舌', '憨憨', '舔狗', '高冷', '中二']
const EMOJIS = ['🐷', '🐶', '🐱', '🐹', '👾', '🦖']

export function AvatarCreateScreen() {
  const qc = useQueryClient()
  const [tone, setTone] = useState(TONES[0])
  const [name, setName] = useState('')
  const [emoji, setEmoji] = useState(EMOJIS[0])
  const [seed, setSeed] = useState('')

  const save = useMutation({
    mutationFn: () =>
      updateMyAvatar({ name: name.trim(), appearance: { emoji, tone }, persona: { tone, seed } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['avatar', 'mine'] }),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    save.mutate()
  }

  return (
    <form onSubmit={submit} style={{ padding: 16, display: 'grid', gap: 12 }}>
      <h2>捏一个「对方眼里的你」</h2>
      <div>
        基调：
        <div role="radiogroup" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {TONES.map((t) => (
            <button
              type="button" key={t} role="radio" aria-checked={t === tone} onClick={() => setTone(t)}
              style={{ background: t === tone ? 'var(--accent)' : 'var(--panel)', color: 'var(--ink)', border: '2px solid #101010', borderRadius: 6, padding: '6px 10px' }}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      <input aria-label="名字" value={name} onChange={(e) => setName(e.target.value)} placeholder="给它起个名" />
      <div>
        造型：
        <div style={{ display: 'flex', gap: 6 }}>
          {EMOJIS.map((em) => (
            <button
              type="button" key={em} aria-label={`emoji-${em}`} aria-pressed={em === emoji} onClick={() => setEmoji(em)}
              style={{ fontSize: 24, background: em === emoji ? 'var(--accent)' : 'transparent', border: '2px solid #101010', borderRadius: 6 }}
            >
              {em}
            </button>
          ))}
        </div>
      </div>
      <textarea aria-label="种子设定" value={seed} onChange={(e) => setSeed(e.target.value)} placeholder="一句话形容对方眼里的你（AI 之后会扩写）" rows={3} />
      <button type="submit" disabled={save.isPending || !name.trim()}>就它了</button>
    </form>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/onboarding/AvatarCreateScreen.test.tsx`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): AvatarCreateScreen 捏分身 wizard"
```

---

## Task 11: 事件流数据层（api/events + api/actions + useFeed + useIdempotencyKey）

**Files:**
- Create: `frontend/src/api/actions.ts`, `frontend/src/api/events.ts`, `frontend/src/hooks/useFeed.ts`, `frontend/src/hooks/useIdempotencyKey.ts`
- Test: `frontend/src/hooks/useFeed.test.tsx`, `frontend/src/hooks/useIdempotencyKey.test.tsx`

**Interfaces:**
- Produces:
  - `actions.ts`: `postAction(action_type, content, client_key): Promise<ActionBundle>`
  - `events.ts`: `getEvents(since): Promise<FeedResponse>`; `respondToEvent(eventId, content, client_key): Promise<GameEvent>`
  - `useFeed.ts`: `mergeEvents(prev, incoming): GameEvent[]` (dedup by id, asc sort); `feedKey(coupleId)`, `statsKey(coupleId)`; `FeedData = { events: GameEvent[]; cursor: number }`; `useFeed(coupleId): UseQueryResult<FeedData>` — 每 3s 轮询，游标累积，把 `stats` 写进 `statsKey`。
  - `useIdempotencyKey.ts`: `useIdempotencyKey(): { next(): string; current(): string; clear(): void }`

- [ ] **Step 1: Write the failing tests**

`frontend/src/hooks/useFeed.test.tsx`:
```tsx
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { ReactNode } from 'react'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { useFeed, mergeEvents, statsKey } from './useFeed'
import { GameEvent } from '../api/types'

function ev(id: number): GameEvent {
  return { id, couple_id: 1, actor_user_id: 1, kind: 'action', action_type: 'poke', content: '', parent_event_id: null, created_at: '2026-07-04T00:00:00Z' }
}

test('mergeEvents dedups by id and sorts ascending', () => {
  const out = mergeEvents([ev(3), ev(1)], [ev(1), ev(2)])
  expect(out.map((e) => e.id)).toEqual([1, 2, 3])
})

test('useFeed accumulates deltas and advances the cursor', async () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  server.use(
    http.get('/api/events', ({ request }) => {
      const since = Number(new URL(request.url).searchParams.get('since'))
      if (since === 0)
        return HttpResponse.json({ events: [ev(1), ev(2)], stats: { grievance: 10, dogfood: 0, miss: 0, intimacy: 0 } })
      return HttpResponse.json({ events: since < 3 ? [ev(3)] : [], stats: { grievance: 12, dogfood: 0, miss: 0, intimacy: 0 } })
    }),
  )
  const { result } = renderHook(() => useFeed(1), { wrapper })
  await waitFor(() => expect(result.current.data?.events.length).toBe(2))
  await result.current.refetch()
  await waitFor(() => expect(result.current.data?.events.map((e) => e.id)).toEqual([1, 2, 3]))
  expect(result.current.data?.cursor).toBe(3)
  expect(qc.getQueryData(statsKey(1))).toMatchObject({ grievance: 12 })
})
```

`frontend/src/hooks/useIdempotencyKey.test.tsx`:
```tsx
import { renderHook } from '@testing-library/react'
import { test, expect } from 'vitest'
import { useIdempotencyKey } from './useIdempotencyKey'

test('current is stable until cleared; next rotates', () => {
  const { result } = renderHook(() => useIdempotencyKey())
  const a = result.current.current()
  expect(result.current.current()).toBe(a)
  const b = result.current.next()
  expect(b).not.toBe(a)
  result.current.clear()
  expect(result.current.current()).not.toBe(b)
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/hooks/useFeed.test.tsx src/hooks/useIdempotencyKey.test.tsx`
Expected: FAIL — modules not found.

- [ ] **Step 3: Write minimal implementations**

`frontend/src/api/actions.ts`:
```ts
import { apiRequest } from './client'
import { ActionBundle } from './types'

export function postAction(action_type: string, content: string, client_key: string) {
  return apiRequest<ActionBundle>('POST', '/actions', { action_type, content, client_key })
}
```

`frontend/src/api/events.ts`:
```ts
import { apiRequest } from './client'
import { FeedResponse, GameEvent } from './types'

export function getEvents(since: number) {
  return apiRequest<FeedResponse>('GET', `/events?since=${since}`)
}
export function respondToEvent(eventId: number, content: string, client_key: string) {
  return apiRequest<GameEvent>('POST', `/events/${eventId}/respond`, { content, client_key })
}
```

`frontend/src/hooks/useFeed.ts`:
```ts
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getEvents } from '../api/events'
import { GameEvent, Stats } from '../api/types'

export interface FeedData {
  events: GameEvent[]
  cursor: number
}

export function mergeEvents(prev: GameEvent[], incoming: GameEvent[]): GameEvent[] {
  const byId = new Map<number, GameEvent>()
  for (const e of prev) byId.set(e.id, e)
  for (const e of incoming) byId.set(e.id, e)
  return [...byId.values()].sort((a, b) => a.id - b.id)
}

export function feedKey(coupleId: number) {
  return ['feed', coupleId] as const
}
export function statsKey(coupleId: number) {
  return ['stats', coupleId] as const
}

export function useFeed(coupleId: number | null) {
  const qc = useQueryClient()
  return useQuery({
    queryKey: coupleId == null ? (['feed', 'none'] as const) : feedKey(coupleId),
    enabled: coupleId != null,
    refetchInterval: 3000,
    queryFn: async (): Promise<FeedData> => {
      const prev = qc.getQueryData<FeedData>(feedKey(coupleId!))
      const cursor = prev?.cursor ?? 0
      const res = await getEvents(cursor)
      const events = mergeEvents(prev?.events ?? [], res.events)
      const nextCursor = events.length ? events[events.length - 1].id : cursor
      qc.setQueryData<Stats>(statsKey(coupleId!), res.stats)
      return { events, cursor: nextCursor }
    },
  })
}
```

`frontend/src/hooks/useIdempotencyKey.ts`:
```ts
import { useRef } from 'react'

export function useIdempotencyKey() {
  const ref = useRef<string | null>(null)
  return {
    next() {
      ref.current = crypto.randomUUID()
      return ref.current
    },
    current() {
      if (!ref.current) ref.current = crypto.randomUUID()
      return ref.current
    },
    clear() {
      ref.current = null
    },
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/hooks/useFeed.test.tsx src/hooks/useIdempotencyKey.test.tsx`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): feed data layer (useFeed cursor + idempotency key)"
```

---

## Task 12: 家 + 动作（HomeScreen / StatDashboard / ActionBar / useAction）

**Files:**
- Create: `frontend/src/hooks/useAction.ts`, `frontend/src/home/StatDashboard.tsx`, `frontend/src/home/ActionBar.tsx`, `frontend/src/home/HomeScreen.tsx`
- Test: `frontend/src/home/HomeScreen.test.tsx`

**Interfaces:**
- Consumes: `postAction` (Task 11); `FeedData`/`feedKey`/`statsKey`/`mergeEvents` (Task 11); `usePetAvatar` (Task 8); `useIdempotencyKey` (Task 11); `StatGauge`/`PressButton`/`PetSprite`/`SpeechBubble`/`LoadingBanter` (Tasks 4/5).
- Produces:
  - `useAction(coupleId): UseMutationResult<ActionBundle, ..., {action_type, content, client_key}>` — 成功后把 bundle 事件并进 feed 缓存并推进 cursor、把 `stats` 写进 `statsKey`。
  - `StatDashboard({ coupleId })` — 订阅 `statsKey`，渲染 4 条 gauge；委屈 ≥ 80 报警。
  - `ActionBar({ onAction, disabled })` — 6 个动作按钮（不含 chat）。
  - `HomeScreen({ coupleId })` — 组合仪表盘 + 分身 + 气泡 + 动作；对方未捏分身时显示孵化占位。

- [ ] **Step 1: Write the failing test**

`frontend/src/home/HomeScreen.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { HomeScreen } from './HomeScreen'

function pet(name: string) {
  return { id: 2, couple_id: 1, subject_user_id: 2, keeper_user_id: 1, name, appearance: { emoji: '🐷' }, persona: {} }
}

test('firing an action shows the AI reaction and updates stats', async () => {
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.post('/api/actions', () =>
      HttpResponse.json({
        events: [
          { id: 10, couple_id: 1, actor_user_id: 1, kind: 'action', action_type: 'scold', content: '', parent_event_id: null, created_at: 't' },
          { id: 11, couple_id: 1, actor_user_id: null, kind: 'ai_reaction', action_type: 'scold', content: '骂我？重新组织语言。', parent_event_id: 10, created_at: 't' },
        ],
        stats: { grievance: 15, dogfood: 0, miss: 0, intimacy: 0 },
      }),
    ),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  await screen.findByText('臭宝')
  await userEvent.click(screen.getByRole('button', { name: '骂一顿' }))
  expect(await screen.findByText('骂我？重新组织语言。')).toBeInTheDocument()
  await waitFor(() => expect(screen.getByTestId('gauge-委屈')).toHaveTextContent('15'))
})

test('shows hatching placeholder when partner has not captured their avatar', async () => {
  server.use(http.get('/api/avatars/pet', () => HttpResponse.json(pet(''))))
  renderWithProviders(<HomeScreen coupleId={1} />)
  expect(await screen.findByText(/孵化中/)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/home/HomeScreen.test.tsx`
Expected: FAIL — cannot find module `./HomeScreen`.

- [ ] **Step 3: Write minimal implementations**

`frontend/src/hooks/useAction.ts`:
```ts
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { postAction } from '../api/actions'
import { ActionBundle, Stats } from '../api/types'
import { FeedData, feedKey, statsKey, mergeEvents } from './useFeed'

export function useAction(coupleId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { action_type: string; content: string; client_key: string }) =>
      postAction(v.action_type, v.content, v.client_key),
    onSuccess: (bundle: ActionBundle) => {
      qc.setQueryData<FeedData>(feedKey(coupleId), (old) => {
        const merged = mergeEvents(old?.events ?? [], bundle.events)
        const cursor = merged.length ? merged[merged.length - 1].id : old?.cursor ?? 0
        return { events: merged, cursor }
      })
      qc.setQueryData<Stats>(statsKey(coupleId), bundle.stats)
    },
  })
}
```

`frontend/src/home/StatDashboard.tsx`:
```tsx
import { useQuery } from '@tanstack/react-query'
import { statsKey } from '../hooks/useFeed'
import { Stats } from '../api/types'
import { StatGauge } from '../components/StatGauge'

const GRIEVANCE_ALARM = 80

const DEFAULT_STATS: Stats = { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 }

export function StatDashboard({ coupleId }: { coupleId: number }) {
  // enabled:false → queryFn never runs; this observer only reads what
  // useFeed / useAction write via setQueryData(statsKey(...)).
  const { data } = useQuery<Stats>({
    queryKey: statsKey(coupleId),
    queryFn: () => DEFAULT_STATS,
    enabled: false,
  })
  const s = data ?? DEFAULT_STATS
  return (
    <div style={{ display: 'flex', gap: 8 }}>
      <StatGauge label="委屈" value={s.grievance} alarm={s.grievance >= GRIEVANCE_ALARM} />
      <StatGauge label="狗粮" value={s.dogfood} />
      <StatGauge label="想你" value={s.miss} />
      <StatGauge label="亲密" value={s.intimacy} />
    </div>
  )
}
```

`frontend/src/home/ActionBar.tsx`:
```tsx
import { PressButton } from '../components/PressButton'

const ACTIONS: { type: string; label: string }[] = [
  { type: 'scold', label: '骂一顿' },
  { type: 'poke', label: '戳一戳' },
  { type: 'feed_dogfood', label: '喂狗粮' },
  { type: 'hug', label: '抱抱' },
  { type: 'miss_you', label: '想你' },
  { type: 'apologize', label: '道歉' },
]

export function ActionBar({ onAction, disabled }: { onAction: (type: string) => void; disabled?: boolean }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
      {ACTIONS.map((a) => (
        <PressButton key={a.type} onPress={() => onAction(a.type)} disabled={disabled}>
          {a.label}
        </PressButton>
      ))}
    </div>
  )
}
```

`frontend/src/home/HomeScreen.tsx`:
```tsx
import { useState } from 'react'
import { StatDashboard } from './StatDashboard'
import { ActionBar } from './ActionBar'
import { PetSprite } from '../components/PetSprite'
import { SpeechBubble } from '../components/SpeechBubble'
import { LoadingBanter } from '../components/LoadingBanter'
import { useAction } from '../hooks/useAction'
import { useIdempotencyKey } from '../hooks/useIdempotencyKey'
import { usePetAvatar } from '../hooks/useAvatar'
import { GameEvent } from '../api/types'

function reactionText(events: GameEvent[]): string {
  return events.find((e) => e.kind === 'ai_reaction')?.content ?? '（分身没接话，装死中…）'
}
function comfortText(events: GameEvent[]): string | null {
  return events.find((e) => e.kind === 'system')?.content ?? null
}

export function HomeScreen({ coupleId }: { coupleId: number }) {
  const pet = usePetAvatar(true)
  const action = useAction(coupleId)
  const key = useIdempotencyKey()
  const [reaction, setReaction] = useState<string | null>(null)
  const [bubble, setBubble] = useState<{ text: string; typing: boolean } | null>(null)
  const [comfort, setComfort] = useState<string | null>(null)

  const petCaptured = pet.data && pet.data.name !== ''
  const face = (pet.data?.appearance?.emoji as string) ?? '👾'

  const fire = (type: string) => {
    setComfort(null)
    setReaction(type)
    setBubble(null)
    action.mutate(
      { action_type: type, content: '', client_key: key.next() },
      {
        onSuccess: (bundle) => {
          setBubble({ text: reactionText(bundle.events), typing: true })
          setComfort(comfortText(bundle.events))
          key.clear()
        },
        onError: () => setBubble({ text: '（分身卡壳了，喝口水再战~）', typing: false }),
      },
    )
  }

  if (pet.isLoading)
    return (
      <div style={{ padding: 16 }}>
        <LoadingBanter />
      </div>
    )
  if (!petCaptured)
    return (
      <div style={{ padding: 16, textAlign: 'center' }}>
        <div style={{ fontSize: 48 }}>🥚</div>
        <p>对方分身孵化中…</p>
        <p>催 TA 一下：「快去捏你自己啊！」</p>
        <LoadingBanter />
      </div>
    )

  return (
    <div style={{ padding: 8, display: 'grid', gap: 12 }}>
      <StatDashboard coupleId={coupleId} />
      <div style={{ minHeight: 40, textAlign: 'center' }}>
        {action.isPending ? <LoadingBanter /> : bubble ? <SpeechBubble text={bubble.text} typing={bubble.typing} /> : null}
      </div>
      <div className="screen" style={{ padding: 8 }}>
        <div style={{ textAlign: 'center' }}>{pet.data?.name || 'TA 的分身'}</div>
        <PetSprite face={face} reaction={action.isPending ? null : reaction} />
      </div>
      {comfort && (
        <div role="status" style={{ color: 'var(--warn)', textAlign: 'center' }}>
          {comfort}
        </div>
      )}
      <ActionBar onAction={fire} disabled={action.isPending} />
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/home/HomeScreen.test.tsx`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): home screen with stats dashboard + action bar + optimistic reactions"
```

---

## Task 13: 事件流 + 本尊回应（FeedScreen / EventItem / useRespond）

**Files:**
- Create: `frontend/src/hooks/useRespond.ts`, `frontend/src/feed/EventItem.tsx`, `frontend/src/feed/FeedScreen.tsx`
- Test: `frontend/src/feed/FeedScreen.test.tsx`

**Interfaces:**
- Consumes: `useFeed` (Task 11); `respondToEvent` (Task 11); `FeedData`/`feedKey`/`mergeEvents` (Task 11); `useIdempotencyKey` (Task 11); `LoadingBanter` (Task 5).
- Produces:
  - `useRespond(coupleId): UseMutationResult<GameEvent, ..., {eventId, content, client_key}>` — 成功后把返回事件并进 feed 缓存并推进 cursor。
  - `EventItem({ ev, mine })` — 按 kind 渲染；`real_response` 带「👤 本尊回应」徽标。
  - `FeedScreen({ coupleId, myUserId, partnerId })` — 渲染时间线；对方的 `action` 且无 `real_response` 子事件时给「👤 本尊附身回应」入口。

- [ ] **Step 1: Write the failing test**

`frontend/src/feed/FeedScreen.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { FeedScreen } from './FeedScreen'

test('offers 本尊附身回应 on the partner action and posts the response', async () => {
  server.use(
    http.get('/api/events', () =>
      HttpResponse.json({
        events: [
          { id: 5, couple_id: 1, actor_user_id: 2, kind: 'action', action_type: 'scold', content: '大猪蹄子', parent_event_id: null, created_at: 't' },
        ],
        stats: { grievance: 15, dogfood: 0, miss: 0, intimacy: 0 },
      }),
    ),
    http.post('/api/events/5/respond', () =>
      HttpResponse.json({ id: 6, couple_id: 1, actor_user_id: 1, kind: 'real_response', action_type: null, content: '你才是！', parent_event_id: 5, created_at: 't' }),
    ),
  )
  renderWithProviders(<FeedScreen coupleId={1} myUserId={1} partnerId={2} />)
  const respondBtn = await screen.findByRole('button', { name: '👤 本尊附身回应' })
  await userEvent.click(respondBtn)
  await userEvent.type(screen.getByLabelText('回应内容'), '你才是！')
  await userEvent.click(screen.getByRole('button', { name: '发送' }))
  expect(await screen.findByLabelText('本尊回应')).toBeInTheDocument()
  await waitFor(() => expect(screen.getByText('你才是！')).toBeInTheDocument())
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/feed/FeedScreen.test.tsx`
Expected: FAIL — cannot find module `./FeedScreen`.

- [ ] **Step 3: Write minimal implementations**

`frontend/src/hooks/useRespond.ts`:
```ts
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { respondToEvent } from '../api/events'
import { GameEvent } from '../api/types'
import { FeedData, feedKey, mergeEvents } from './useFeed'

export function useRespond(coupleId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { eventId: number; content: string; client_key: string }) =>
      respondToEvent(v.eventId, v.content, v.client_key),
    onSuccess: (ev: GameEvent) => {
      qc.setQueryData<FeedData>(feedKey(coupleId), (old) => {
        const merged = mergeEvents(old?.events ?? [], [ev])
        const cursor = merged.length ? merged[merged.length - 1].id : old?.cursor ?? 0
        return { events: merged, cursor }
      })
    },
  })
}
```

`frontend/src/feed/EventItem.tsx`:
```tsx
import { GameEvent } from '../api/types'

const ACTION_LABEL: Record<string, string> = {
  scold: '骂了你', poke: '戳了你', feed_dogfood: '喂了狗粮', hug: '抱了你',
  miss_you: '说想你', apologize: '道了歉', chat: '找你唠',
}

export function EventItem({ ev, mine }: { ev: GameEvent; mine: boolean }) {
  if (ev.kind === 'ai_reaction') return <div style={{ opacity: 0.9 }}>🤖 {ev.content}</div>
  if (ev.kind === 'system')
    return (
      <div role="note" style={{ color: 'var(--warn)' }}>
        {ev.content}
      </div>
    )
  if (ev.kind === 'real_response')
    return (
      <div style={{ border: '2px solid var(--accent)', borderRadius: 8, padding: 6, background: '#ffffff22', fontWeight: 'bold' }}>
        <span aria-label="本尊回应">👤 本尊回应</span>：<span>{ev.content}</span>
      </div>
    )
  const who = mine ? '你' : 'TA'
  const label = ev.action_type ? ACTION_LABEL[ev.action_type] ?? '做了个动作' : '做了个动作'
  return (
    <div>
      {who}
      {label}
      {ev.content ? `：「${ev.content}」` : ''}
    </div>
  )
}
```

`frontend/src/feed/FeedScreen.tsx`:
```tsx
import { useState } from 'react'
import { useFeed } from '../hooks/useFeed'
import { useRespond } from '../hooks/useRespond'
import { useIdempotencyKey } from '../hooks/useIdempotencyKey'
import { EventItem } from './EventItem'
import { LoadingBanter } from '../components/LoadingBanter'
import { GameEvent } from '../api/types'

export function FeedScreen({ coupleId, myUserId, partnerId }: { coupleId: number; myUserId: number; partnerId: number }) {
  const feed = useFeed(coupleId)
  const respond = useRespond(coupleId)
  const key = useIdempotencyKey()
  const [openFor, setOpenFor] = useState<number | null>(null)
  const [text, setText] = useState('')

  const events = feed.data?.events ?? []
  const hasResponse = (actionId: number) =>
    events.some((e) => e.kind === 'real_response' && e.parent_event_id === actionId)

  if (feed.isLoading)
    return (
      <div style={{ padding: 16 }}>
        <LoadingBanter />
      </div>
    )
  if (events.length === 0)
    return <div style={{ padding: 16, textAlign: 'center' }}>还没有故事，去戳戳 TA 吧~</div>

  const submit = (actionId: number) => {
    respond.mutate(
      { eventId: actionId, content: text, client_key: key.next() },
      { onSuccess: () => { setOpenFor(null); setText(''); key.clear() } },
    )
  }

  return (
    <div style={{ padding: 8, display: 'grid', gap: 8 }}>
      {events.map((ev: GameEvent) => {
        const canRespond = ev.kind === 'action' && ev.actor_user_id === partnerId && !hasResponse(ev.id)
        return (
          <div key={ev.id} className="screen" style={{ padding: 8 }}>
            <EventItem ev={ev} mine={ev.actor_user_id === myUserId} />
            {canRespond && openFor !== ev.id && (
              <button onClick={() => setOpenFor(ev.id)} style={{ marginTop: 6 }}>👤 本尊附身回应</button>
            )}
            {canRespond && openFor === ev.id && (
              <div style={{ display: 'grid', gap: 6, marginTop: 6 }}>
                <input aria-label="回应内容" value={text} onChange={(e) => setText(e.target.value)} placeholder="亲自回怼/服软…" />
                <button onClick={() => submit(ev.id)} disabled={respond.isPending}>发送</button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/feed/FeedScreen.test.tsx`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): event feed with 本尊附身 real-response"
```

---

## Task 14: 聊天（ChatScreen）

**Files:**
- Create: `frontend/src/chat/ChatScreen.tsx`
- Test: `frontend/src/chat/ChatScreen.test.tsx`

**Interfaces:**
- Consumes: `useFeed` (Task 11); `useAction` (Task 12); `useIdempotencyKey` (Task 11); `SpeechBubble`/`LoadingBanter` (Task 5).
- Produces: `ChatScreen({ coupleId })` — 从 feed 时间线过滤出 `action_type==='chat'` 的动作及其 `ai_reaction`，渲染成对话线程；发送走 `useAction('chat')`。

- [ ] **Step 1: Write the failing test**

`frontend/src/chat/ChatScreen.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { ChatScreen } from './ChatScreen'

test('sending a chat message shows the avatar reply', async () => {
  server.use(
    http.get('/api/events', () => HttpResponse.json({ events: [], stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 } })),
    http.post('/api/actions', () =>
      HttpResponse.json({
        events: [
          { id: 20, couple_id: 1, actor_user_id: 1, kind: 'action', action_type: 'chat', content: '在吗', parent_event_id: null, created_at: 't' },
          { id: 21, couple_id: 1, actor_user_id: null, kind: 'ai_reaction', action_type: 'chat', content: '在的在的，永远在。', parent_event_id: 20, created_at: 't' },
        ],
        stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 },
      }),
    ),
  )
  renderWithProviders(<ChatScreen coupleId={1} />)
  await userEvent.type(screen.getByLabelText('聊天输入'), '在吗')
  await userEvent.click(screen.getByRole('button', { name: '发' }))
  expect(await screen.findByText('在的在的，永远在。')).toBeInTheDocument()
  await waitFor(() => expect(screen.getByText(/在吗/)).toBeInTheDocument())
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/chat/ChatScreen.test.tsx`
Expected: FAIL — cannot find module `./ChatScreen`.

- [ ] **Step 3: Write minimal implementation**

`frontend/src/chat/ChatScreen.tsx`:
```tsx
import { useState } from 'react'
import { useFeed } from '../hooks/useFeed'
import { useAction } from '../hooks/useAction'
import { useIdempotencyKey } from '../hooks/useIdempotencyKey'
import { SpeechBubble } from '../components/SpeechBubble'
import { LoadingBanter } from '../components/LoadingBanter'
import { GameEvent } from '../api/types'

export function ChatScreen({ coupleId }: { coupleId: number }) {
  const feed = useFeed(coupleId)
  const action = useAction(coupleId)
  const key = useIdempotencyKey()
  const [text, setText] = useState('')

  const events = feed.data?.events ?? []
  const chatActionIds = new Set(
    events.filter((e) => e.kind === 'action' && e.action_type === 'chat').map((e) => e.id),
  )
  const thread = events.filter(
    (e) =>
      (e.kind === 'action' && e.action_type === 'chat') ||
      (e.kind === 'ai_reaction' && e.parent_event_id != null && chatActionIds.has(e.parent_event_id)),
  )

  const send = () => {
    if (!text.trim()) return
    action.mutate(
      { action_type: 'chat', content: text.trim(), client_key: key.next() },
      { onSuccess: () => { setText(''); key.clear() } },
    )
  }

  return (
    <div style={{ padding: 8, display: 'grid', gap: 8 }}>
      <div style={{ display: 'grid', gap: 6 }}>
        {thread.map((e: GameEvent) =>
          e.kind === 'action' ? (
            <div key={e.id} style={{ textAlign: 'right' }}>🧑 {e.content}</div>
          ) : (
            <div key={e.id} style={{ textAlign: 'left' }}>
              <SpeechBubble text={e.content} />
            </div>
          ),
        )}
        {action.isPending && <LoadingBanter />}
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <input aria-label="聊天输入" style={{ flex: 1 }} value={text} onChange={(e) => setText(e.target.value)} placeholder="随便唠两句…" />
        <button onClick={send} disabled={action.isPending}>发</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/chat/ChatScreen.test.tsx`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): chat screen as feed projection"
```

---

## Task 15: App 网关 + 主壳（App / MainShell / MyAvatarScreen）

**Files:**
- Modify: `frontend/src/App.tsx` (replace the Task 1 placeholder), `frontend/src/main.tsx` (wrap `AuthProvider`)
- Modify: `frontend/src/App.test.tsx` (replace the Task 1 smoke test)
- Create: `frontend/src/shell/MainShell.tsx`, `frontend/src/shell/badge.ts`, `frontend/src/me/MyAvatarScreen.tsx`
- Test: `frontend/src/shell/badge.test.ts`

**Interfaces:**
- Consumes: `useAuth` (Task 6); `useCouple` (Task 8); `useMyAvatar` (Task 8); `useFeed` (Task 11); `PairScreen`/`AvatarCreateScreen`/`LoginScreen`/`RegisterScreen`/`HomeScreen`/`FeedScreen`/`ChatScreen`; `PixelPanel`/`TabBar`/`LoadingBanter`.
- Produces:
  - `badge.ts`: `hasUnseen(maxEventId: number, seenEventId: number, activeTab: string): boolean`
  - `MyAvatarScreen({ onLogout })`
  - `MainShell({ coupleId, myUserId, partnerId })` — 四 tab（home/feed/chat/me）+ 事件流未读红点
  - `App()` — 路由 + 三态引导网关

- [ ] **Step 1: Write the failing tests**

`frontend/src/shell/badge.test.ts`:
```ts
import { test, expect } from 'vitest'
import { hasUnseen } from './badge'

test('flags unseen only when a newer event exists and feed is not the active tab', () => {
  expect(hasUnseen(10, 8, 'home')).toBe(true)
  expect(hasUnseen(10, 10, 'home')).toBe(false)
  expect(hasUnseen(10, 8, 'feed')).toBe(false)
})
```

Replace `frontend/src/App.test.tsx` with:
```tsx
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { test, expect, beforeEach } from 'vitest'
import { server } from './test/server'
import { renderWithProviders } from './test/utils'
import { AuthProvider } from './auth/AuthContext'
import App from './App'

beforeEach(() => localStorage.clear())

test('unauthenticated users land on login', async () => {
  renderWithProviders(
    <AuthProvider>
      <App />
    </AuthProvider>,
  )
  expect(await screen.findByRole('button', { name: '进去' })).toBeInTheDocument()
})

test('authenticated active couple with a captured avatar lands on home', async () => {
  localStorage.setItem('couple.token', 'tok')
  localStorage.setItem('couple.user', JSON.stringify({ id: 1, nickname: 'mimi' }))
  server.use(
    http.get('/api/couples/me', () => HttpResponse.json({ couple_id: 1, status: 'active', partner_id: 2 })),
    http.get('/api/avatars/mine', () => HttpResponse.json({ id: 1, couple_id: 1, subject_user_id: 1, keeper_user_id: 2, name: '本尊', appearance: {}, persona: {} })),
    http.get('/api/avatars/pet', () => HttpResponse.json({ id: 2, couple_id: 1, subject_user_id: 2, keeper_user_id: 1, name: '臭宝', appearance: { emoji: '🐷' }, persona: {} })),
    http.get('/api/events', () => HttpResponse.json({ events: [], stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 } })),
  )
  renderWithProviders(
    <AuthProvider>
      <App />
    </AuthProvider>,
  )
  expect(await screen.findByRole('button', { name: '骂一顿' })).toBeInTheDocument()
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/shell/badge.test.ts src/App.test.tsx`
Expected: FAIL — `./shell/badge` missing; App still renders the placeholder so the login/home assertions fail.

- [ ] **Step 3: Write minimal implementations**

`frontend/src/shell/badge.ts`:
```ts
export function hasUnseen(maxEventId: number, seenEventId: number, activeTab: string): boolean {
  return maxEventId > seenEventId && activeTab !== 'feed'
}
```

`frontend/src/me/MyAvatarScreen.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useMyAvatar } from '../hooks/useAvatar'
import { updateMyAvatar } from '../api/avatars'

export function MyAvatarScreen({ onLogout }: { onLogout: () => void }) {
  const mine = useMyAvatar(true)
  const qc = useQueryClient()
  const [name, setName] = useState('')
  useEffect(() => {
    if (mine.data) setName(mine.data.name)
  }, [mine.data])
  const save = useMutation({
    mutationFn: () => updateMyAvatar({ name: name.trim() }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['avatar', 'mine'] }),
  })
  const emoji = (mine.data?.appearance?.emoji as string) ?? '👾'
  return (
    <div style={{ padding: 16, display: 'grid', gap: 12 }}>
      <h2>我的分身（对方眼里的你）</h2>
      <div style={{ fontSize: 48, textAlign: 'center' }}>{emoji}</div>
      <input aria-label="分身名字" value={name} onChange={(e) => setName(e.target.value)} />
      <button onClick={() => save.mutate()} disabled={save.isPending || !name.trim()}>保存</button>
      <button onClick={onLogout} style={{ marginTop: 24 }}>退出登录</button>
    </div>
  )
}
```

`frontend/src/shell/MainShell.tsx`:
```tsx
import { useEffect, useRef, useState } from 'react'
import { TabBar } from '../components/TabBar'
import { HomeScreen } from '../home/HomeScreen'
import { FeedScreen } from '../feed/FeedScreen'
import { ChatScreen } from '../chat/ChatScreen'
import { MyAvatarScreen } from '../me/MyAvatarScreen'
import { useAuth } from '../auth/AuthContext'
import { useFeed } from '../hooks/useFeed'
import { hasUnseen } from './badge'

export function MainShell({ coupleId, myUserId, partnerId }: { coupleId: number; myUserId: number; partnerId: number }) {
  const [tab, setTab] = useState('home')
  const { logout } = useAuth()
  const feed = useFeed(coupleId)
  const maxId = (feed.data?.events ?? []).reduce((m, e) => Math.max(m, e.id), 0)
  const seenRef = useRef(0)
  useEffect(() => {
    if (tab === 'feed') seenRef.current = maxId
  }, [tab, maxId])
  const unseen = hasUnseen(maxId, seenRef.current, tab)

  const tabs = [
    { key: 'home', label: '🏠 TA' },
    { key: 'feed', label: unseen ? '🔔 事件流 🔴' : '🔔 事件流' },
    { key: 'chat', label: '💬 唠' },
    { key: 'me', label: '⚙️ 我' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <div style={{ flex: 1 }}>
        {tab === 'home' && <HomeScreen coupleId={coupleId} />}
        {tab === 'feed' && <FeedScreen coupleId={coupleId} myUserId={myUserId} partnerId={partnerId} />}
        {tab === 'chat' && <ChatScreen coupleId={coupleId} />}
        {tab === 'me' && <MyAvatarScreen onLogout={logout} />}
      </div>
      <TabBar tabs={tabs} active={tab} onChange={setTab} />
    </div>
  )
}
```

`frontend/src/App.tsx` (replace placeholder):
```tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import { LoginScreen } from './auth/LoginScreen'
import { RegisterScreen } from './auth/RegisterScreen'
import { PixelPanel } from './components/PixelPanel'
import { LoadingBanter } from './components/LoadingBanter'
import { useCouple } from './hooks/useCouple'
import { useMyAvatar } from './hooks/useAvatar'
import { PairScreen } from './onboarding/PairScreen'
import { AvatarCreateScreen } from './onboarding/AvatarCreateScreen'
import { MainShell } from './shell/MainShell'

function Gate() {
  const { user } = useAuth()
  const couple = useCouple(!!user)
  const isActive = couple.data?.status === 'active'
  const myAvatar = useMyAvatar(isActive)

  if (couple.isLoading) return <LoadingBanter />
  if (!couple.data || couple.data.status === 'none')
    return <PairScreen couple={couple.data ?? { couple_id: null, status: 'none' }} />
  if (couple.data.status === 'pending') return <PairScreen couple={couple.data} />
  if (myAvatar.isLoading) return <LoadingBanter />
  if (!myAvatar.data || myAvatar.data.name === '') return <AvatarCreateScreen />
  return <MainShell coupleId={couple.data.couple_id} myUserId={user!.id} partnerId={couple.data.partner_id} />
}

export default function App() {
  const { user } = useAuth()
  return (
    <PixelPanel>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" /> : <LoginScreen />} />
        <Route path="/register" element={user ? <Navigate to="/" /> : <RegisterScreen />} />
        <Route path="/*" element={user ? <Gate /> : <Navigate to="/login" />} />
      </Routes>
    </PixelPanel>
  )
}
```

`frontend/src/main.tsx` (wrap `AuthProvider` around `App`):
```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './auth/AuthContext'
import './styles/tokens.css'
import './styles/global.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 2, refetchOnWindowFocus: true } },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/shell/badge.test.ts src/App.test.tsx`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "feat(frontend): app gate + main shell tabs + my-avatar + unseen badge"
```

---

## Task 16: 整合验证 + 运行文档 + 试玩清单

**Files:**
- Create: `frontend/.env.example`, `frontend/README.md`, `docs/couple-playtest-checklist.md`

**Interfaces:**
- Consumes: everything. No new runtime code — this task wires up docs and runs the whole-suite + typecheck gate.

- [ ] **Step 1: Create env + run docs**

`frontend/.env.example`:
```
# 生产环境后端地址；开发期留空走 Vite proxy (/api → localhost:8000)
VITE_API_BASE=
```

`frontend/README.md`:
```markdown
# 情侣分身宠物 · 前端

像素电子宠物机风格的移动端 web 前端，消费 `../backend` 的 FastAPI。

## 本地运行

1. 起后端（另一个终端）：
   ```bash
   cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
   ```
2. 起前端：
   ```bash
   cd frontend && npm install && npm run dev
   ```
   开发期 Vite 把 `/api/*` 代理到 `http://localhost:8000/*`。

## 测试

```bash
cd frontend && npm test        # vitest 一次性跑
npx tsc -b                      # 类型检查
```

## 双人真配对试玩

见 `../docs/couple-playtest-checklist.md`。需要两个账号 / 两台设备（或两个隐身窗口）。
```

`docs/couple-playtest-checklist.md`:
```markdown
# 双人真配对试玩自查清单

单人测不出隔空互动的爽点——用两个账号（两台设备或两个隐身窗口）走一遍。

- [ ] A 注册 → 创建情侣 → 拿到邀请码
- [ ] B 注册 → 输入邀请码 → 配对成功（A 的等待屏自动跳走）
- [ ] A、B 各自捏分身（基调 + 名字 + emoji + 种子设定）
- [ ] A 在家界面对分身「骂一顿」→ 立刻看到 AI 回怼气泡 + 委屈值滚动上涨
- [ ] B 的事件流轮询到「A 骂了你」→ 出现「👤 本尊附身回应」入口
- [ ] B 本尊回应 → A 的事件流看到带「👤 本尊回应」徽标的那条 + 特殊样式
- [ ] 连点动作按钮：有冷却、不刷屏；重试同一动作对方只收到一条（幂等）
- [ ] 喂狗粮/抱抱/道歉：狗粮值/亲密度上涨、委屈值下降
- [ ] 把委屈值刷过 80 → 出现系统旁白「该哄了」
- [ ] 随便唠：发消息 → 分身用人设回（打字机）→ 对方事件流也能看到
- [ ] 断网/后端停一下：失败是卖萌台词、数字不变、恢复后自动补拉
- [ ] 对方还没捏分身时：家界面是「🥚 孵化中 + 催 TA」而非空屏
```

- [ ] **Step 2: Run the whole suite**

Run: `cd frontend && npx vitest run`
Expected: all test files pass (Tasks 1–15).

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd frontend && git add -A && git commit -m "docs(frontend): run instructions, env example, two-device playtest checklist"
```

---

## 附：自查（写计划后对照 spec）

- **§1 范围**：登录/注册(T6/7)、配对(T8/9)、捏分身(T10)、家+7动作(T12 六个 + T14 chat)、事件流+本尊回应(T13)、聊天(T14) — 全覆盖；进化过场/Web Push/AI 扩写按 spec 明确不做。
- **§2 视觉/§7 交互质感**：像素外壳(T3)、PressButton 冷却(T4)、StatGauge 滚动(T4)、SpeechBubble 打字机(T5)、LoadingBanter 等待台词(T5)、PetSprite(T5)、失败卖萌不改数值(T12)。
- **§3 技术栈**：TanStack Query 轮询(T11)、Framer Motion(T4/5)、React Router(T15)、Vitest+RTL+MSW(T1)。
- **§4 API 契约**：auth(T6)、couples(T8)、avatars(T8)、actions(T11/12)、events(T11/13) 全部按真实端点与状态码接。
- **§6 三态引导网关 / §9 边界**：网关(T15)、pairing 边界(T9)、token 失效/登录注册友好错(T7)、幂等键(T11)、并发以服务端为准(T11/12)。
- **§10 测试策略**：组件/流程测覆盖配对/捏分身/动作/幂等/事件流/本尊回应/失败兜底；hooks 单测(useFeed/useIdempotencyKey)。
- **类型一致性**：`Stats`/`GameEvent`/`Avatar`/`CoupleState`/`FeedData` 全程同名；`feedKey`/`statsKey`/`mergeEvents` 跨 T11–T14 一致。
