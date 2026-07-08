import { describe, it, expect } from 'vitest'
import { ReactNode } from 'react'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import { useDaily } from './useDaily'

// renderHook 需要一个包裹组件；utils.tsx 的 renderWithProviders 是给 render() 用的，
// 这里自带一个只含 QueryClient 的 wrapper。
function wrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

const base = {
  question: { text: '今天想我了吗?', flavor: 'deep' },
  my_answer: null,
  partner_answer: null,
  both_answered: false,
  streak: { count: 3, i_did_today: false, partner_did_today: false, at_risk: true, lagging_user_id: 7 },
}

describe('useDaily', () => {
  it('拉取今日一问 + 火苗', async () => {
    server.use(http.get('/api/daily', () => HttpResponse.json(base)))
    const { result } = renderHook(() => useDaily(1), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.data?.question.text).toBe('今天想我了吗?'))
    expect(result.current.data?.streak.count).toBe(3)
  })

  it('提交答案后更新缓存', async () => {
    server.use(
      http.get('/api/daily', () => HttpResponse.json(base)),
      http.post('/api/daily/answer', () => HttpResponse.json({ ...base, my_answer: '想了' })),
    )
    const { result } = renderHook(() => useDaily(1), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.data).toBeTruthy())
    await act(async () => {
      await result.current.answer('想了')
    })
    await waitFor(() => expect(result.current.data?.my_answer).toBe('想了'))
  })
})
