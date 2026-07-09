import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { ChatScreen } from './ChatScreen'

test('sending a chat message shows my bubble and the avatar reply', async () => {
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
  renderWithProviders(<ChatScreen coupleId={1} myUserId={1} partnerId={2} />)
  await userEvent.type(screen.getByLabelText('聊天输入'), '在吗')
  await userEvent.click(screen.getByRole('button', { name: '发送' }))
  expect(await screen.findByText('在的在的，永远在。')).toBeInTheDocument()
  await waitFor(() => expect(screen.getByText('在吗')).toBeInTheDocument())
})

test('输入框为空时发送键是禁用的', async () => {
  renderWithProviders(<ChatScreen coupleId={1} myUserId={1} partnerId={2} />)
  const sendBtn = await screen.findByRole('button', { name: '发送' })
  expect(sendBtn).toBeDisabled()
  await userEvent.type(screen.getByLabelText('聊天输入'), '嗨')
  expect(sendBtn).toBeEnabled()
})

test('a partner action renders as an inline tip, not a bubble', async () => {
  server.use(
    http.get('/api/events', () =>
      HttpResponse.json({
        events: [
          { id: 5, couple_id: 1, actor_user_id: 2, kind: 'action', action_type: 'scold', content: '大猪蹄子', parent_event_id: null, created_at: 't' },
        ],
        stats: { grievance: 10, dogfood: 0, miss: 0, intimacy: 0 },
      }),
    ),
  )
  renderWithProviders(<ChatScreen coupleId={1} myUserId={1} partnerId={2} />)
  expect(await screen.findByText(/TA骂了你/)).toBeInTheDocument()
  // the standalone 本尊回应 affordance is gone — you just reply in the chat box
  expect(screen.queryByRole('button', { name: /本尊回应/ })).toBeNull()
})

test('my own non-chat action renders as a tip with the right pronoun', async () => {
  server.use(
    http.get('/api/events', () =>
      HttpResponse.json({
        events: [
          { id: 8, couple_id: 1, actor_user_id: 1, kind: 'action', action_type: 'poke', content: '', parent_event_id: null, created_at: 't' },
        ],
        stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 },
      }),
    ),
  )
  renderWithProviders(<ChatScreen coupleId={1} myUserId={1} partnerId={2} />)
  expect(await screen.findByText(/你戳了 ?TA/)).toBeInTheDocument()
  // my own action offers no 本尊回应
  expect(screen.queryByRole('button', { name: '👤 本尊回应' })).toBeNull()
})

test('表情选择器：默认收起，点开能选，选中的表情插到光标处', async () => {
  renderWithProviders(<ChatScreen coupleId={1} myUserId={1} partnerId={2} />)
  const trigger = await screen.findByRole('button', { name: '选择表情' })
  expect(trigger).toHaveAttribute('aria-expanded', 'false')
  expect(screen.queryByRole('dialog', { name: '选择表情' })).toBeNull()

  const input = screen.getByLabelText('聊天输入') as HTMLInputElement
  await userEvent.type(input, '想你')
  input.setSelectionRange(1, 1) // 把光标塞到「想」和「你」中间

  await userEvent.click(trigger)
  expect(trigger).toHaveAttribute('aria-expanded', 'true')
  await userEvent.click(screen.getByRole('button', { name: '🥰' }))

  expect(input.value).toBe('想🥰你') // 插在光标处，不是追加到末尾
  // 连着挑第二个是常态，面板不该自己收起来
  expect(screen.getByRole('dialog', { name: '选择表情' })).toBeInTheDocument()
})

test('表情面板：点外面 / 按 Esc 都能收起', async () => {
  renderWithProviders(<ChatScreen coupleId={1} myUserId={1} partnerId={2} />)
  const trigger = await screen.findByRole('button', { name: '选择表情' })

  await userEvent.click(trigger)
  await userEvent.click(screen.getByLabelText('聊天输入')) // 点面板外面
  expect(screen.queryByRole('dialog', { name: '选择表情' })).toBeNull()

  await userEvent.click(trigger)
  expect(screen.getByRole('dialog', { name: '选择表情' })).toBeInTheDocument()
  await userEvent.keyboard('{Escape}')
  expect(screen.queryByRole('dialog', { name: '选择表情' })).toBeNull()
  expect(trigger).toHaveFocus() // 收起后焦点还回触发键
})

test('renders a daily_qa card with both answers', async () => {
  server.use(
    http.get('/api/events', () =>
      HttpResponse.json({
        events: [
          { id: 100, couple_id: 1, actor_user_id: null, kind: 'daily_qa', action_type: null, content: '今天想我了吗?', parent_event_id: null, created_at: 't' },
          { id: 101, couple_id: 1, actor_user_id: 1, kind: 'daily_qa', action_type: null, content: '想了', parent_event_id: 100, created_at: 't' },
          { id: 102, couple_id: 1, actor_user_id: 2, kind: 'daily_qa', action_type: null, content: '哼', parent_event_id: 100, created_at: 't' },
        ],
        stats: { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 },
      }),
    ),
  )
  renderWithProviders(<ChatScreen coupleId={1} myUserId={1} partnerId={2} />)
  expect(await screen.findByText('今天想我了吗?')).toBeInTheDocument()
  expect(screen.getByText('想了')).toBeInTheDocument()
  expect(screen.getByText('哼')).toBeInTheDocument()
})
