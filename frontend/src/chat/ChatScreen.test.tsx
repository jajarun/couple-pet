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
  await userEvent.click(screen.getByRole('button', { name: '发' }))
  expect(await screen.findByText('在的在的，永远在。')).toBeInTheDocument()
  await waitFor(() => expect(screen.getByText('在吗')).toBeInTheDocument())
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
