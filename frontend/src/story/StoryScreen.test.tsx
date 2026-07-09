import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { STORY_ROUND_ONE } from '../test/handlers'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { StoryScreen } from './StoryScreen'

const OPTS = ['疯狂按按钮', '按紧急呼叫铃', '讲个冷笑话']

function round(over: Record<string, unknown> = {}) {
  return { ...STORY_ROUND_ONE.rounds[0], ...over }
}
function story(rounds: unknown[], over: Record<string, unknown> = {}) {
  return { story: { ...STORY_ROUND_ONE.story, ...over }, rounds, my_turn: false }
}

test('轮到你：场景 + 三个选项', async () => {
  renderWithProviders(<StoryScreen coupleId={1} />)
  expect(await screen.findByText('🎭 困在电梯里')).toBeInTheDocument()
  expect(screen.getByText('第 1 幕 / 共 4 幕')).toBeInTheDocument()
  expect(screen.getByText(/电梯卡在 7 楼和 8 楼之间/)).toBeInTheDocument()
  for (const o of OPTS) expect(screen.getByRole('button', { name: new RegExp(o) })).toBeInTheDocument()
})

test('你选完了但 TA 还没：显示你的选择 + 等 TA，且不泄露对方选了啥', async () => {
  server.use(
    http.get('/api/story', () =>
      HttpResponse.json(story([round({ my_choice: 1, partner_choice: null, both_chose: false })])),
    ),
  )
  renderWithProviders(<StoryScreen coupleId={1} />)
  const waiting = await screen.findByTestId('story-waiting')
  expect(waiting).toHaveTextContent('你选好了「按紧急呼叫铃」')
  expect(waiting).toHaveTextContent('等 TA 也做出选择')
  expect(screen.queryByRole('button', { name: /疯狂按按钮/ })).not.toBeInTheDocument()
})

test('两人都选完：互看彼此的选择，新一幕接上', async () => {
  server.use(
    http.get('/api/story', () =>
      HttpResponse.json(
        story([
          round({ my_choice: 0, partner_choice: 2, both_chose: true }),
          round({ round_no: 2, scene: '对讲机里传来一句「等着」。', my_choice: null, partner_choice: null, both_chose: false }),
        ]),
      ),
    ),
  )
  renderWithProviders(<StoryScreen coupleId={1} />)
  const picks = await screen.findByTestId('picks-1')
  expect(picks).toHaveTextContent('你选了「疯狂按按钮」')
  expect(picks).toHaveTextContent('TA 选了「讲个冷笑话」')
  expect(screen.getByTestId('story-current')).toHaveTextContent('对讲机里传来一句')
  expect(screen.getByText('第 2 幕 / 共 4 幕')).toBeInTheDocument()
})

test('选了同一个：合并成一句「你们俩都选了」', async () => {
  server.use(
    http.get('/api/story', () =>
      HttpResponse.json(story([round({ my_choice: 2, partner_choice: 2, both_chose: true })])),
    ),
  )
  renderWithProviders(<StoryScreen coupleId={1} />)
  expect(await screen.findByTestId('picks-1')).toHaveTextContent('你们俩都选了「讲个冷笑话」')
})

test('结局：完结卡 + 明天还有新的一章，且没有任何可选项', async () => {
  server.use(
    http.get('/api/story', () =>
      HttpResponse.json(
        story(
          [
            round({ my_choice: 0, partner_choice: 1, both_chose: true }),
            { round_no: 5, scene: '门开了。检修师傅探头进来。', options: [], my_choice: null, partner_choice: null, both_chose: false },
          ],
          { status: 'ended' },
        ),
      ),
    ),
  )
  renderWithProviders(<StoryScreen coupleId={1} />)
  expect(await screen.findByTestId('story-ending')).toHaveTextContent('明天还有新的一章')
  expect(screen.getByText('已完结')).toBeInTheDocument()
  expect(screen.getByText(/检修师傅探头进来/)).toBeInTheDocument()
  expect(screen.queryByTestId('story-current')).not.toBeInTheDocument()
})

test('点一个选项 → 服务端返回的新剧情直接回写，不用等轮询', async () => {
  let picked: unknown = null
  server.use(
    http.post('/api/story/choose', async ({ request }) => {
      picked = await request.json()
      return HttpResponse.json(story([round({ my_choice: 1, both_chose: false })]))
    }),
  )
  renderWithProviders(<StoryScreen coupleId={1} />)
  await userEvent.click(await screen.findByRole('button', { name: /按紧急呼叫铃/ }))
  await waitFor(() => expect(screen.getByTestId('story-waiting')).toBeInTheDocument())
  expect(picked).toMatchObject({ round_no: 1, option_index: 1 })
})

test('别处已经翻篇了：409 stale_round 不会把页面搞崩', async () => {
  server.use(
    http.post('/api/story/choose', () =>
      HttpResponse.json({ detail: 'stale_round' }, { status: 409 }),
    ),
  )
  renderWithProviders(<StoryScreen coupleId={1} />)
  await userEvent.click(await screen.findByRole('button', { name: /疯狂按按钮/ }))
  // 页面还在，选项还在（下一次 20s 轮询会把最新的幕带回来）
  expect(await screen.findByText('🎭 困在电梯里')).toBeInTheDocument()
})
