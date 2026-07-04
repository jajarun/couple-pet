import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { ReactNode } from 'react'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { useCouple } from './useCouple'

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

test('useCouple fetches the active couple state', async () => {
  server.use(
    http.get('/api/couples/me', () =>
      HttpResponse.json({ couple_id: 7, status: 'active', partner_id: 2 }),
    ),
  )
  const { result } = renderHook(() => useCouple(true), { wrapper })
  await waitFor(() => expect(result.current.data).toBeDefined())
  expect(result.current.data).toMatchObject({ status: 'active', partner_id: 2 })
})
