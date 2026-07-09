import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { petAvatarKey } from '../hooks/useAvatar'
import { FeedData, appendToFeed, feedKey } from '../hooks/useFeed'
import { presenceKey } from '../hooks/usePresence'
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
      HttpResponse.json({ ...pet('臭宝'), is_away: true, runaway_state: 'away', runaway_note: '走了。别找。' }),
    ),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  expect(await screen.findByTestId('runaway')).toBeInTheDocument()
  expect(screen.getByText(/别找/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '骂一顿' })).not.toBeInTheDocument()
})

test('哄完只到门口：按钮变成「等 TA 点头」，首页还是空窝', async () => {
  let state = 'away'
  server.use(
    http.get('/api/avatars/pet', () =>
      HttpResponse.json({ ...pet('臭宝'), is_away: true, runaway_state: state, runaway_note: '哼。' }),
    ),
    http.post('/api/actions', async ({ request }) => {
      const body = (await request.json()) as { action_type: string }
      if (body.action_type === 'coax') state = 'pending'
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

  expect(await screen.findByTestId('awaiting-forgiveness')).toBeDisabled()
  expect(screen.getByTestId('runaway')).toBeInTheDocument() // 没点头就还没回家
  expect(screen.queryByRole('button', { name: '骂一顿' })).not.toBeInTheDocument()
})

test('对方点了头，它才真的回家', async () => {
  let state = 'pending'
  server.use(
    http.get('/api/avatars/pet', () =>
      HttpResponse.json({
        ...pet('臭宝'),
        is_away: state !== 'home',
        runaway_state: state,
        runaway_note: state === 'home' ? null : '哼。',
      }),
    ),
  )
  const { queryClient: qc } = renderWithProviders(<HomeScreen coupleId={1} />)
  expect(await screen.findByTestId('awaiting-forgiveness')).toBeInTheDocument()

  // 对方在那头点了头 → forgive 事件进时间线 → 3 秒轮询把它捞回来 → 重取分身状态
  state = 'home'
  act(() => {
    qc.setQueryData(feedKey(1), (old: FeedData | undefined) => appendToFeed(old, [FORGIVE_EVENT]))
  })
  expect(await screen.findByRole('button', { name: '骂一顿' })).toBeInTheDocument()
  expect(screen.queryByTestId('runaway')).not.toBeInTheDocument()
})

test('别处把它气跑了：动作被 409 挡回来，首页自己切成空窝', async () => {
  let away = false
  server.use(
    http.get('/api/avatars/pet', () =>
      HttpResponse.json({
        ...pet('臭宝'),
        is_away: away,
        runaway_state: away ? 'away' : 'home',
        runaway_note: away ? '哼。' : null,
      }),
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

test('哄完还在等点头时，连「哄」都被 409 挡回来', async () => {
  server.use(
    http.get('/api/avatars/pet', () =>
      HttpResponse.json({ ...pet('臭宝'), is_away: true, runaway_state: 'away', runaway_note: '哼。' }),
    ),
    http.post('/api/actions', () =>
      HttpResponse.json({ detail: 'awaiting_forgiveness' }, { status: 409 }),
    ),
  )
  const { queryClient: qc } = renderWithProviders(<HomeScreen coupleId={1} />)
  await userEvent.click(await screen.findByRole('button', { name: '🥺 去哄它回来' }))
  // 409 触发重取 /avatars/pet——真实服务端此时会返回 pending
  await waitFor(() => expect(qc.getQueryState(petAvatarKey)?.isInvalidated).toBe(false))
  expect(screen.getByTestId('runaway')).toBeInTheDocument()
})

function mine(name = '小恶魔', extra: Record<string, unknown> = {}) {
  return {
    id: 1, couple_id: 1, subject_user_id: 1, keeper_user_id: 2, name,
    appearance: { emoji: '🐶' }, persona: {}, evolution: EGG_EVOLUTION, ...extra,
  }
}

const FORGIVE_EVENT = {
  id: 9, couple_id: 1, actor_user_id: 2, kind: 'system' as const, action_type: 'forgive',
  content: '💌 alice 点了头，臭宝回家了。', parent_event_id: null, created_at: 't',
}

test('TA 把「我」气跑了：点头的卡片长在我的首页上', async () => {
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.get('/api/avatars/mine', () =>
      HttpResponse.json(mine('小恶魔', { is_away: true, runaway_state: 'pending', runaway_note: '再也不回来了。' })),
    ),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  const card = await screen.findByTestId('forgive-card')
  expect(card).toHaveTextContent('再也不回来了')
  expect(screen.getByRole('button', { name: '💌 原谅 TA' })).toBeInTheDocument()
  // 我养的那只好端端在家，首页照常
  expect(screen.getByRole('button', { name: '骂一顿' })).toBeInTheDocument()
})

test('TA 还没来哄，就没有原谅按钮可点', async () => {
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.get('/api/avatars/mine', () =>
      HttpResponse.json(mine('小恶魔', { is_away: true, runaway_state: 'away', runaway_note: '哼。' })),
    ),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  expect(await screen.findByTestId('forgive-card')).toHaveTextContent('还没来哄')
  expect(screen.queryByRole('button', { name: '💌 原谅 TA' })).not.toBeInTheDocument()
})

test('两只分身同时在外面：空窝里也得能点头，否则谁都回不了家', async () => {
  server.use(
    http.get('/api/avatars/pet', () =>
      HttpResponse.json({ ...pet('臭宝'), is_away: true, runaway_state: 'away', runaway_note: '哼。' }),
    ),
    http.get('/api/avatars/mine', () =>
      HttpResponse.json(mine('小恶魔', { is_away: true, runaway_state: 'pending', runaway_note: '走了。' })),
    ),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  expect(await screen.findByTestId('runaway')).toBeInTheDocument()
  expect(await screen.findByTestId('forgive-card')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '💌 原谅 TA' })).toBeInTheDocument()
})

test('点头之后卡片消失', async () => {
  let state = 'pending'
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.get('/api/avatars/mine', () =>
      HttpResponse.json(
        mine('小恶魔', { is_away: state !== 'home', runaway_state: state, runaway_note: '哼。' }),
      ),
    ),
    http.post('/api/runaway/forgive', () => {
      state = 'home'
      return HttpResponse.json({ state: 'home' })
    }),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  await userEvent.click(await screen.findByRole('button', { name: '💌 原谅 TA' }))
  await waitFor(() => expect(screen.queryByTestId('forgive-card')).not.toBeInTheDocument())
})

test('平时（都在家）首页没有原谅卡', async () => {
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.get('/api/avatars/mine', () => HttpResponse.json(mine())),
  )
  renderWithProviders(<HomeScreen coupleId={1} />)
  await screen.findByText('臭宝')
  expect(screen.queryByTestId('forgive-card')).not.toBeInTheDocument()
})

test('TA 也在线：banner 亮起、两只分身贴贴、多出摸摸头', async () => {
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.get('/api/avatars/mine', () => HttpResponse.json(mine())),
  )
  renderWithProviders(<HomeScreen coupleId={1} together />)
  expect(await screen.findByTestId('together-banner')).toHaveTextContent('TA 正在看这只分身')
  expect(await screen.findByTestId('snuggle-pair')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '摸摸头' })).toBeInTheDocument()
})

test('TA 不在时，同框的三件套一件都不出现', async () => {
  server.use(http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))))
  renderWithProviders(<HomeScreen coupleId={1} />)
  await screen.findByText('臭宝')
  expect(screen.queryByTestId('together-banner')).not.toBeInTheDocument()
  expect(screen.queryByTestId('snuggle-pair')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '摸摸头' })).not.toBeInTheDocument()
})

const PARTNER_POKE = {
  id: 7, couple_id: 1, actor_user_id: 2, kind: 'action' as const, action_type: 'poke',
  content: '', parent_event_id: null, created_at: 't',
}

test('同框时实时看到对方在戳你', async () => {
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.get('/api/avatars/mine', () => HttpResponse.json(mine())),
  )
  const { queryClient: qc } = renderWithProviders(
    <HomeScreen coupleId={1} partnerId={2} together />,
  )
  await screen.findByTestId('snuggle-pair')
  // 先等首屏 feed 落地——已在时间线上的旧动作会被 baseline 吃掉，不该抖
  await waitFor(() => expect(qc.getQueryData(feedKey(1))).toBeDefined())
  expect(screen.queryByTestId('poke-tip')).not.toBeInTheDocument()

  // TA 在那头戳了一下，3 秒轮询把它捞了回来
  act(() => {
    qc.setQueryData(feedKey(1), (old: FeedData | undefined) => appendToFeed(old, [PARTNER_POKE]))
  })
  expect(await screen.findByTestId('poke-tip')).toHaveTextContent('TA 刚戳了你')
})

test('已经躺在时间线上的旧动作不会一进页面就抖', async () => {
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.get('/api/avatars/mine', () => HttpResponse.json(mine())),
    http.get('/api/events', () =>
      HttpResponse.json({
        events: [PARTNER_POKE],
        stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 },
      }),
    ),
  )
  const { queryClient: qc } = renderWithProviders(
    <HomeScreen coupleId={1} partnerId={2} together />,
  )
  await screen.findByTestId('snuggle-pair')
  await waitFor(() => expect(qc.getQueryData(feedKey(1))).toBeDefined())
  expect(screen.queryByTestId('poke-tip')).not.toBeInTheDocument()
})

test('自己发的动作不会触发「TA 刚…」的提示', async () => {
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.get('/api/avatars/mine', () => HttpResponse.json(mine())),
  )
  const { queryClient: qc } = renderWithProviders(
    <HomeScreen coupleId={1} partnerId={2} together />,
  )
  await screen.findByTestId('snuggle-pair')
  await waitFor(() => expect(qc.getQueryData(feedKey(1))).toBeDefined())
  act(() => {
    qc.setQueryData(feedKey(1), (old: FeedData | undefined) =>
      appendToFeed(old, [{ ...PARTNER_POKE, actor_user_id: 1 }]),
    )
  })
  await waitFor(() => expect(screen.queryByTestId('poke-tip')).not.toBeInTheDocument())
})

test('摸到一半 TA 走了：409 not_together 把同框态就地关掉', async () => {
  server.use(
    http.get('/api/avatars/pet', () => HttpResponse.json(pet('臭宝'))),
    http.get('/api/avatars/mine', () => HttpResponse.json(mine())),
    http.post('/api/actions', () => HttpResponse.json({ detail: 'not_together' }, { status: 409 })),
  )
  const { queryClient: qc } = renderWithProviders(<HomeScreen coupleId={1} together />)
  await screen.findByTestId('snuggle-pair')
  await userEvent.click(screen.getByRole('button', { name: '摸摸头' }))
  await waitFor(() => expect(qc.getQueryData(presenceKey)).toEqual({ partner_online: false }))
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
