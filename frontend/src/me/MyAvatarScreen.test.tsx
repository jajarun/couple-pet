import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { MyAvatarScreen } from './MyAvatarScreen'

// appearance 里除了 emoji 还躺着捏分身时选的 tone——保存造型时不能把它冲掉
const MINE = {
  id: 1, couple_id: 1, subject_user_id: 1, keeper_user_id: 2,
  name: '小恶魔', appearance: { emoji: '🐷', tone: ['毒舌'] }, persona: {},
}

function me(ai_reply_enabled: boolean) {
  return { id: 1, nickname: 'alice', gender: 'female', ai_reply_enabled }
}

function mountable(ai_reply_enabled = false) {
  server.use(
    http.get('/api/avatars/mine', () => HttpResponse.json(MINE)),
    http.get('/api/auth/me', () => HttpResponse.json(me(ai_reply_enabled))),
  )
}

/** 桩住 PUT /avatars/mine，回显收到的改动，并把请求体录下来 */
function captureSave() {
  const bodies: Record<string, unknown>[] = []
  server.use(
    http.put('/api/avatars/mine', async ({ request }) => {
      const patch = (await request.json()) as Record<string, unknown>
      bodies.push(patch)
      return HttpResponse.json({ ...MINE, ...patch })
    }),
  )
  return bodies
}

test('当前造型在选格里高亮', async () => {
  mountable()
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  await waitFor(() => expect(screen.getByLabelText('emoji-🐷')).toHaveAttribute('aria-pressed', 'true'))
  expect(screen.getByLabelText('emoji-🐶')).toHaveAttribute('aria-pressed', 'false')
})

test('换个造型再保存：PUT 带上新 emoji，且不冲掉 appearance 里的 tone', async () => {
  mountable()
  const bodies = captureSave()
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  await userEvent.click(await screen.findByLabelText('emoji-🦊'))
  await userEvent.click(screen.getByRole('button', { name: '保存' }))

  await waitFor(() => expect(bodies).toHaveLength(1))
  expect(bodies[0]).toEqual({
    name: '小恶魔',
    appearance: { emoji: '🦊', tone: ['毒舌'] }, // tone 原样带回去，别把它冲没了
  })
})

test('保存成功后新造型留在页面上，不会被重拉的旧数据顶回去', async () => {
  mountable() // GET /avatars/mine 永远返回旧的 🐷
  captureSave()
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  await userEvent.click(await screen.findByLabelText('emoji-🦊'))
  await userEvent.click(screen.getByRole('button', { name: '保存' }))

  await waitFor(() => expect(screen.getByRole('button', { name: '已保存' })).toBeDisabled())
  expect(screen.getByLabelText('emoji-🦊')).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByLabelText('emoji-🐷')).toHaveAttribute('aria-pressed', 'false')
})

test('没改动时保存键是禁用的', async () => {
  mountable()
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  const btn = await screen.findByRole('button', { name: '已保存' })
  expect(btn).toBeDisabled()
})

test('只改名字也能保存', async () => {
  mountable()
  const bodies = captureSave()
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  const input = await screen.findByLabelText('分身名字')
  await waitFor(() => expect(input).toHaveValue('小恶魔'))
  await userEvent.type(input, '子')
  await userEvent.click(screen.getByRole('button', { name: '保存' }))

  await waitFor(() => expect(bodies).toHaveLength(1))
  expect(bodies[0]).toEqual({ name: '小恶魔子', appearance: { emoji: '🐷', tone: ['毒舌'] } })
})

test('老数据没存过 emoji 时，回落到 👾', async () => {
  server.use(
    http.get('/api/avatars/mine', () => HttpResponse.json({ ...MINE, appearance: {} })),
    http.get('/api/auth/me', () => HttpResponse.json(me(false))),
  )
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  // 等名字落地才算数据到了——👾 是 useState 的初值，一上来就 pressed，等它等于没等
  await waitFor(() => expect(screen.getByLabelText('分身名字')).toHaveValue('小恶魔'))

  expect(screen.getByLabelText('emoji-👾')).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: '已保存' })).toBeDisabled() // 回落值不算「改过」
})

test('保存失败时给一句人话，不假装成功', async () => {
  mountable()
  server.use(http.put('/api/avatars/mine', () => new HttpResponse(null, { status: 500 })))
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  await userEvent.click(await screen.findByLabelText('emoji-🦊'))
  await userEvent.click(screen.getByRole('button', { name: '保存' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('没存上')
  expect(screen.getByRole('button', { name: '保存' })).toBeEnabled() // 还能再试
})

// 这只分身归 TA 养——形态是 TA 一次次互动养出来的，跟你自己捏的造型是两回事
const DARK = { stage: 3, branch: 'dark', exp: 130, next_exp: null, progress: 1, emoji: '😈', title: '黑化完全体', use_form_emoji: true }

test('「TA 把你养成了什么样」照出 TA 的养法', async () => {
  server.use(
    http.get('/api/avatars/mine', () => HttpResponse.json({ ...MINE, evolution: DARK })),
    http.get('/api/auth/me', () => HttpResponse.json(me(false))),
  )
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  expect(await screen.findByText('TA 把你养成了什么样')).toBeInTheDocument()
  expect(screen.getByLabelText('形态 黑化完全体')).toHaveTextContent('😈')
  expect(screen.getByText(/性格已经定型/)).toBeInTheDocument()
})

test('还没养出个性时说「还在长」，形态位仍显示你自己捏的造型', async () => {
  mountable() // MINE 没有 evolution → 当一颗蛋看
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  expect(await screen.findByText(/还在长/)).toBeInTheDocument()
  expect(screen.getByLabelText('形态 一颗蛋')).toHaveTextContent('🐷')
})

test('分身回复默认关闭，按钮邀请你「开启」', async () => {
  mountable(false)
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  expect(await screen.findByText('分身回复')).toBeInTheDocument()
  await waitFor(() => expect(screen.getByRole('button', { name: '开启' })).toBeInTheDocument())
})

test('点开关会 PATCH /auth/me，文案翻成「已开启」', async () => {
  mountable(false)
  const patched: unknown[] = []
  server.use(
    http.patch('/api/auth/me', async ({ request }) => {
      patched.push(await request.json())
      return HttpResponse.json(me(true))
    }),
  )
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  await userEvent.click(await screen.findByRole('button', { name: '开启' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '已开启' })).toBeInTheDocument())
  expect(patched).toEqual([{ ai_reply_enabled: true }])
})

test('已开启时再点一下是关掉', async () => {
  mountable(true)
  const patched: unknown[] = []
  server.use(
    http.patch('/api/auth/me', async ({ request }) => {
      patched.push(await request.json())
      return HttpResponse.json(me(false))
    }),
  )
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  await userEvent.click(await screen.findByRole('button', { name: '已开启' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '开启' })).toBeInTheDocument())
  expect(patched).toEqual([{ ai_reply_enabled: false }])
})

test('PATCH 失败时给一句人话，开关不假装成功', async () => {
  mountable(false)
  server.use(http.patch('/api/auth/me', () => new HttpResponse(null, { status: 500 })))
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  await userEvent.click(await screen.findByRole('button', { name: '开启' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('没改成功')
  expect(screen.getByRole('button', { name: '开启' })).toBeInTheDocument()
})
