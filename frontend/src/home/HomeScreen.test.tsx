import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { EGG_EVOLUTION } from '../test/handlers'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { HomeScreen } from './HomeScreen'

function pet(name: string, evolution: Record<string, unknown> = EGG_EVOLUTION, dream: unknown = null) {
  return {
    id: 2, couple_id: 1, subject_user_id: 2, keeper_user_id: 1, name,
    appearance: { emoji: '🐷' }, persona: {}, evolution, dream,
  }
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

test('a failed action shows a cute fallback and leaves stats unchanged', async () => {
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.post('/api/actions', () => HttpResponse.json({ detail: 'boom' }, { status: 500 })),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  await screen.findByText('臭宝')
  await userEvent.click(screen.getByRole('button', { name: '骂一顿' }))
  expect(await screen.findByText(/喝口水再战/)).toBeInTheDocument()
  // stats never updated → 委屈 stays 0
  expect(screen.getByTestId('gauge-委屈')).toHaveTextContent('0')
})

const ADULT = { stage: 2, branch: 'dark', exp: 60, next_exp: 120, progress: 0.25, emoji: '😼', title: '腹黑体', use_form_emoji: true }

test('成体起，进化形态抢过用户捏的造型', async () => {
  server.use(http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝', ADULT))))
  renderWithProviders(<HomeScreen coupleId={1} />)
  await screen.findByText('臭宝')
  expect(screen.getByTestId('pet')).toHaveTextContent('😼') // 不是 appearance 里的 🐷
  expect(screen.getByText('腹黑体')).toBeInTheDocument()
})

test('今早的梦话冒在首页上，没做梦就不占地方', async () => {
  server.use(
    http.get('/api/avatars/pet', () =>
      HttpResponse.json(pet('臭宝', EGG_EVOLUTION, { content: '（翻身）别走…', at: 't' })),
    ),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  expect(await screen.findByTestId('dream-card')).toHaveTextContent('别走')
})

test('没做梦时首页不出现梦话卡', async () => {
  server.use(http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))))
  renderWithProviders(<HomeScreen coupleId={1} />)
  await screen.findByText('臭宝')
  expect(screen.queryByTestId('dream-card')).not.toBeInTheDocument()
})

test('进化那一下放全屏动画，之后自己消失', async () => {
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.post('/api/actions', () =>
      HttpResponse.json({
        events: [{ id: 10, couple_id: 1, actor_user_id: 1, kind: 'action', action_type: 'hug', content: '', parent_event_id: null, created_at: 't' }],
        stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 10 },
        evolution: { stage: 1, branch: '', exp: 12, next_exp: 40, progress: 0.071, emoji: '🐣', title: '幼体', use_form_emoji: false },
        evolved: true,
      }),
    ),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  await screen.findByText('臭宝')
  await userEvent.click(screen.getByRole('button', { name: '抱抱' }))

  const overlay = await screen.findByTestId('evo-overlay')
  expect(overlay).toHaveTextContent('破壳了')
  await userEvent.click(overlay) // 点一下就收（不用等 2.2s）
  await waitFor(() => expect(screen.queryByTestId('evo-overlay')).not.toBeInTheDocument())
})

test('没跨阶段就不放动画，但进度条照样跟着涨', async () => {
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.post('/api/actions', () =>
      HttpResponse.json({
        events: [{ id: 10, couple_id: 1, actor_user_id: 1, kind: 'action', action_type: 'hug', content: '', parent_event_id: null, created_at: 't' }],
        stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 10 },
        evolution: { stage: 0, branch: '', exp: 3, next_exp: 10, progress: 0.3, emoji: '🥚', title: '一颗蛋', use_form_emoji: false },
        evolved: false,
      }),
    ),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  await screen.findByText('臭宝')
  expect(screen.getByText('再攒 10 点就长大了')).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: '抱抱' }))
  // 服务端返回的进化态直接回写缓存，不用等重新 GET /avatars/pet
  expect(await screen.findByText('再攒 7 点就长大了')).toBeInTheDocument()
  expect(screen.queryByTestId('evo-overlay')).not.toBeInTheDocument()
})

test('它跑了：首页换成空窝，一个动作都点不到', async () => {
  server.use(
    http.get('/api/avatars/pet', () =>
      HttpResponse.json({ ...pet('臭宝'), is_away: true, runaway_note: '走了。别找。' }),
    ),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  expect(await screen.findByTestId('runaway')).toBeInTheDocument()
  expect(screen.getByText(/别找/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '骂一顿' })).not.toBeInTheDocument()
})

test('哄回来以后首页恢复正常', async () => {
  let away = true
  server.use(
    http.get('/api/avatars/pet', () =>
      HttpResponse.json({ ...pet('臭宝'), is_away: away, runaway_note: away ? '哼。' : null }),
    ),
    http.post('/api/actions', async ({ request }) => {
      const body = (await request.json()) as { action_type: string }
      if (body.action_type === 'coax') away = false
      return HttpResponse.json({
        events: [{ id: 20, couple_id: 1, actor_user_id: 1, kind: 'action', action_type: body.action_type, content: '', parent_event_id: null, created_at: 't' }],
        stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 5 },
        evolution: EGG_EVOLUTION,
        evolved: false,
      })
    }),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  await userEvent.click(await screen.findByRole('button', { name: '🥺 去哄它回来' }))

  await waitFor(() => expect(screen.queryByTestId('runaway')).not.toBeInTheDocument())
  expect(await screen.findByRole('button', { name: '骂一顿' })).toBeInTheDocument()
})

test('别处把它气跑了：动作被 409 挡回来，首页自己切成空窝', async () => {
  let away = false
  server.use(
    http.get('/api/avatars/pet', () =>
      HttpResponse.json({ ...pet('臭宝'), is_away: away, runaway_note: away ? '哼。' : null }),
    ),
    http.post('/api/actions', () => {
      away = true // 服务端早就知道它跑了
      return HttpResponse.json({ detail: 'pet_away' }, { status: 409 })
    }),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  await screen.findByText('臭宝')
  await userEvent.click(screen.getByRole('button', { name: '骂一顿' }))
  expect(await screen.findByTestId('runaway')).toBeInTheDocument()
})

test('a lost-response retry reuses the same client_key (idempotency)', async () => {
  const keys: string[] = []
  let calls = 0
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.post('/api/actions', async ({ request }) => {
      const body = (await request.json()) as { client_key: string }
      keys.push(body.client_key)
      calls += 1
      if (calls === 1) return HttpResponse.error() // simulate a lost response
      return HttpResponse.json({
        events: [
          { id: 10, couple_id: 1, actor_user_id: 1, kind: 'action', action_type: 'scold', content: '', parent_event_id: null, created_at: 't' },
          { id: 11, couple_id: 1, actor_user_id: null, kind: 'ai_reaction', action_type: 'scold', content: '重新组织语言。', parent_event_id: 10, created_at: 't' },
        ],
        stats: { grievance: 15, dogfood: 0, miss: 0, intimacy: 0 },
      })
    }),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  await screen.findByText('臭宝')
  await userEvent.click(screen.getByRole('button', { name: '骂一顿' }))
  expect(await screen.findByText('重新组织语言。')).toBeInTheDocument()
  expect(keys.length).toBe(2)
  expect(keys[0]).toBe(keys[1]) // retry reused the same key → backend can dedup
})
