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
