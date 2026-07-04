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
