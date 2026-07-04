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
