// 给手写的 public/sw.js 兜底：它不走打包、也没法 import，只能把源码读进来
// 在一个假的 ServiceWorkerGlobalScope 里跑一遍，然后直接调它注册的那几个 handler。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
// 从包根导入才带类型；子路径 fake-indexeddb/lib/FDBFactory 的 .d.ts 被 exports 挡住了
import { IDBFactory } from 'fake-indexeddb'
import { beforeEach, expect, test, vi } from 'vitest'

const SW_SRC = readFileSync(resolve(__dirname, '../../public/sw.js'), 'utf8')

type Handlers = Record<string, (event: unknown) => void>

/** 每个用例一套全新的 SW 作用域 + 全新的空 IndexedDB */
function loadSw(opts: { focused?: boolean; badging?: boolean } = {}) {
  const { focused = false, badging = true } = opts
  const handlers: Handlers = {}
  const setAppBadge = vi.fn().mockResolvedValue(undefined)
  const clearAppBadge = vi.fn().mockResolvedValue(undefined)
  const showNotification = vi.fn().mockResolvedValue(undefined)

  const self = {
    addEventListener: (type: string, fn: (e: unknown) => void) => void (handlers[type] = fn),
    skipWaiting: vi.fn(),
    clients: {
      claim: vi.fn(),
      matchAll: vi.fn().mockResolvedValue(focused ? [{ focused: true }] : []),
      openWindow: vi.fn(),
    },
    registration: { showNotification },
    navigator: badging ? { setAppBadge, clearAppBadge } : {},
  }

  // sw.js 里裸用 self / indexedDB 两个全局
  new Function('self', 'indexedDB', SW_SRC)(self, new IDBFactory())
  return { handlers, setAppBadge, clearAppBadge, showNotification }
}

/** handler 把活儿塞进 event.waitUntil(promise)，测试得把那个 promise 等出来 */
async function fire(handler: (e: unknown) => void, event: Record<string, unknown>) {
  const waits: Promise<unknown>[] = []
  handler({ ...event, waitUntil: (p: Promise<unknown>) => waits.push(p) })
  await Promise.all(waits)
}

const pushEvent = (data: object) => ({ data: { json: () => data } })

let sw: ReturnType<typeof loadSw>
beforeEach(() => {
  sw = loadSw()
})

test('收到推送：弹通知并把角标 +1', async () => {
  await fire(sw.handlers.push, pushEvent({ title: 'TA 找你啦', body: '戳了你一下' }))
  expect(sw.showNotification).toHaveBeenCalledTimes(1)
  expect(sw.setAppBadge).toHaveBeenCalledWith(1)
})

test('连收三条推送，角标累加到 3（计数落盘，跨 SW 唤醒也不丢）', async () => {
  await fire(sw.handlers.push, pushEvent({ title: 'a' }))
  await fire(sw.handlers.push, pushEvent({ title: 'b' }))
  await fire(sw.handlers.push, pushEvent({ title: 'c' }))
  expect(sw.setAppBadge.mock.calls.map((c) => c[0])).toEqual([1, 2, 3])
})

test('页面正开着时：不弹通知，角标也不涨', async () => {
  const fg = loadSw({ focused: true })
  await fire(fg.handlers.push, pushEvent({ title: 'TA 找你啦' }))
  expect(fg.showNotification).not.toHaveBeenCalled()
  expect(fg.setAppBadge).not.toHaveBeenCalled()
})

test('点通知：角标清零', async () => {
  await fire(sw.handlers.push, pushEvent({ title: 'a' }))
  await fire(sw.handlers.notificationclick, {
    notification: { close: vi.fn(), data: { url: '/' } },
  })
  expect(sw.clearAppBadge).toHaveBeenCalledTimes(1)
})

test('页面回前台发来 clear-badge：角标清零，且计数真的归了零', async () => {
  await fire(sw.handlers.push, pushEvent({ title: 'a' }))
  await fire(sw.handlers.push, pushEvent({ title: 'b' }))
  await fire(sw.handlers.message, { data: { type: 'clear-badge' } })
  expect(sw.clearAppBadge).toHaveBeenCalledTimes(1)

  // 归零后再来一条，得从 1 重新数起——而不是接着 3
  await fire(sw.handlers.push, pushEvent({ title: 'c' }))
  expect(sw.setAppBadge).toHaveBeenLastCalledWith(1)
})

test('不认识的 message 不会误清角标', async () => {
  await fire(sw.handlers.message, { data: { type: 'something-else' } })
  await fire(sw.handlers.message, {})
  expect(sw.clearAppBadge).not.toHaveBeenCalled()
})

test('浏览器不支持角标时：推送照常弹，绝不因此报错', async () => {
  const noBadge = loadSw({ badging: false })
  await expect(
    fire(noBadge.handlers.push, pushEvent({ title: 'TA 找你啦' })),
  ).resolves.toBeUndefined()
  expect(noBadge.showNotification).toHaveBeenCalledTimes(1)
})
