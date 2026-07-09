import { afterEach, expect, test, vi } from 'vitest'
import { clearAppBadge } from './appBadge'

function stubNavigator(parts: Record<string, unknown>) {
  for (const [k, v] of Object.entries(parts)) {
    Object.defineProperty(navigator, k, { value: v, configurable: true, writable: true })
  }
}
afterEach(() => vi.restoreAllMocks())

test('清图标 + 通知 SW 把持久计数也归零', () => {
  const clear = vi.fn().mockResolvedValue(undefined)
  const postMessage = vi.fn()
  stubNavigator({ clearAppBadge: clear, serviceWorker: { controller: { postMessage } } })

  clearAppBadge()

  expect(clear).toHaveBeenCalledTimes(1)
  expect(postMessage).toHaveBeenCalledWith({ type: 'clear-badge' })
})

test('浏览器不支持角标时静默跳过，仍然通知 SW', () => {
  const postMessage = vi.fn()
  stubNavigator({ clearAppBadge: undefined, serviceWorker: { controller: { postMessage } } })

  expect(() => clearAppBadge()).not.toThrow()
  expect(postMessage).toHaveBeenCalledWith({ type: 'clear-badge' })
})

test('SW 还没接管（controller 为 null）时不炸', () => {
  stubNavigator({ clearAppBadge: undefined, serviceWorker: { controller: null } })
  expect(() => clearAppBadge()).not.toThrow()
})

test('clearAppBadge 的 rejection 被吞掉，不冒泡到 UI', async () => {
  const clear = vi.fn().mockRejectedValue(new Error('nope'))
  stubNavigator({ clearAppBadge: clear, serviceWorker: { controller: null } })

  expect(() => clearAppBadge()).not.toThrow()
  await Promise.resolve() // 让被 catch 的 rejection 落地，不留 unhandled
})
