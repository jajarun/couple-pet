import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import { usePush } from './usePush'

// 把 jsdom 缺失的 Web Push 能力桩起来（serviceWorker / PushManager / Notification）
function stubPushEnv(opts: { permission?: NotificationPermission; existing?: unknown } = {}) {
  const fakeSub = {
    endpoint: 'https://push.example/ep1',
    toJSON: () => ({
      endpoint: 'https://push.example/ep1',
      keys: { p256dh: 'PKEY', auth: 'AKEY' },
    }),
    unsubscribe: vi.fn(async () => true),
  }
  const pushManager = {
    getSubscription: vi.fn(async () => opts.existing ?? null),
    subscribe: vi.fn(async () => fakeSub),
  }
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: { ready: Promise.resolve({ pushManager }) },
  })
  vi.stubGlobal('PushManager', function () {})
  const requestPermission = vi.fn(async () => 'granted' as NotificationPermission)
  vi.stubGlobal(
    'Notification',
    Object.assign(function () {}, { permission: opts.permission ?? 'default', requestPermission }),
  )
  return { fakeSub, pushManager, requestPermission }
}

afterEach(() => {
  vi.unstubAllGlobals()
  // @ts-expect-error 删掉测试注入的属性，别污染其它用例
  delete navigator.serviceWorker
})

describe('usePush', () => {
  it('缺能力（jsdom 无 SW/Push）时 supported=false', () => {
    const { result } = renderHook(() => usePush())
    expect(result.current.supported).toBe(false)
  })

  it('开启：申请权限 → 订阅 → 登记后端，enabled 变真', async () => {
    const { requestPermission } = stubPushEnv({ permission: 'default' })
    let posted: unknown = null
    server.use(
      http.get('/api/push/public-key', () => HttpResponse.json({ key: 'aGVsbG8' })),
      http.post('/api/push/subscribe', async ({ request }) => {
        posted = await request.json()
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { result } = renderHook(() => usePush())
    expect(result.current.supported).toBe(true)
    await act(async () => {
      await result.current.turnOn()
    })
    expect(requestPermission).toHaveBeenCalled()
    expect(result.current.enabled).toBe(true)
    expect(posted).toEqual({
      endpoint: 'https://push.example/ep1',
      keys: { p256dh: 'PKEY', auth: 'AKEY' },
    })
  })

  it('权限被拒：给提示、不 enabled、不发订阅请求', async () => {
    stubPushEnv({ permission: 'default' })
    ;(Notification as unknown as { requestPermission: () => Promise<string> }).requestPermission =
      vi.fn(async () => 'denied')
    const { result } = renderHook(() => usePush())
    await act(async () => {
      await result.current.turnOn()
    })
    expect(result.current.enabled).toBe(false)
    expect(result.current.error).toMatch(/拒/)
  })

  it('关闭：退订并通知后端删除', async () => {
    const existing = {
      endpoint: 'https://push.example/ep1',
      unsubscribe: vi.fn(async () => true),
    }
    stubPushEnv({ permission: 'granted', existing })
    let deleted: unknown = null
    server.use(
      http.delete('/api/push/subscribe', async ({ request }) => {
        deleted = await request.json()
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { result } = renderHook(() => usePush())
    await waitFor(() => expect(result.current.enabled).toBe(true)) // 已授权+已有订阅 → 初始为开
    await act(async () => {
      await result.current.turnOff()
    })
    expect(existing.unsubscribe).toHaveBeenCalled()
    expect(deleted).toEqual({ endpoint: 'https://push.example/ep1' })
    expect(result.current.enabled).toBe(false)
  })
})
