import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { apiRequest, ApiError, setAuthToken } from './client'

test('GET returns parsed JSON and sends bearer token when set', async () => {
  let seenAuth: string | null = null
  server.use(
    http.get('/api/ping', ({ request }) => {
      seenAuth = request.headers.get('authorization')
      return HttpResponse.json({ ok: true })
    }),
  )
  setAuthToken('tok123')
  const data = await apiRequest<{ ok: boolean }>('GET', '/ping')
  expect(data.ok).toBe(true)
  expect(seenAuth).toBe('Bearer tok123')
  setAuthToken(null)
})

test('non-2xx throws ApiError carrying status and detail', async () => {
  server.use(
    http.post('/api/auth/login', () =>
      HttpResponse.json({ detail: 'bad credentials' }, { status: 401 }),
    ),
  )
  const err = await apiRequest('POST', '/auth/login', { nickname: 'x' }).catch((e) => e)
  expect(err).toBeInstanceOf(ApiError)
  expect(err).toMatchObject({ status: 401, detail: 'bad credentials' })
})
