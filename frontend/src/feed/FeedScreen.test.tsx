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
