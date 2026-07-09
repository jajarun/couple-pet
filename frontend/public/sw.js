// 情侣宠物 · 最小 Service Worker：只处理 Web Push 的收推送与点击，不做离线缓存。
/* eslint-disable no-restricted-globals */

// 改动后的 SW 立刻接管，不用等所有旧标签页关掉（省得测试/发版时更新不生效）
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

// ============ 主屏图标右上角的未读角标（Badging API）============
// iOS 16.4+ 支持，但仅限「添加到主屏幕」且已授通知权限——跟 Web Push 的前提完全重合。
// 注意：Web Push 不像 APNs 那样能靠 payload 自动 +1，数字得我们自己算、自己调 setAppBadge。
// SW 每次被 push 唤醒都可能是全新的全局作用域，计数只能落盘；SW 里没有 localStorage，
// 所以用 IndexedDB。整套是锦上添花：任何一步失败都必须静默吞掉，绝不能拖垮推送本身。
const BADGE_DB = 'couple-badge'
const BADGE_STORE = 'kv'
const BADGE_KEY = 'unread'

function badgeDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(BADGE_DB, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(BADGE_STORE)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function badgeTx(db, mode, run) {
  return new Promise((resolve, reject) => {
    const t = db.transaction(BADGE_STORE, mode)
    const req = run(t.objectStore(BADGE_STORE))
    t.oncomplete = () => resolve(req ? req.result : undefined)
    t.onerror = () => reject(t.error)
    t.onabort = () => reject(t.error)
  })
}

async function readUnread() {
  const db = await badgeDb()
  const v = await badgeTx(db, 'readonly', (s) => s.get(BADGE_KEY))
  return typeof v === 'number' ? v : 0
}

async function writeUnread(n) {
  const db = await badgeDb()
  await badgeTx(db, 'readwrite', (s) => s.put(n, BADGE_KEY))
}

/** 未读 +1 并刷到图标上。浏览器不支持角标就整段跳过，连数都不用记。 */
async function bumpBadge() {
  if (!self.navigator || typeof self.navigator.setAppBadge !== 'function') return
  try {
    const n = (await readUnread()) + 1
    await writeUnread(n)
    await self.navigator.setAppBadge(n)
  } catch (e) {
    /* 静默：角标失败不该影响推送 */
  }
}

/** 清零：用户开了 App 或点了通知，就当全看过了。 */
async function resetBadge() {
  try {
    await writeUnread(0)
  } catch (e) {
    /* 静默 */
  }
  if (self.navigator && typeof self.navigator.clearAppBadge === 'function') {
    try {
      await self.navigator.clearAppBadge()
    } catch (e) {
      /* 静默 */
    }
  }
}

self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch (e) {
    data = {}
  }
  const title = data.title || '💕 有人在找你'
  const options = {
    body: data.body || '',
    tag: data.tag || 'couple',
    renotify: true, // 同类通知仍合并成一条，但每条都重新提醒（否则后面几条静默替换、感知不到）
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    data: { url: data.url || '/' },
  }
  event.waitUntil(
    (async () => {
      // 页面正开着且聚焦时别弹系统通知打扰（前台已有 3s 轮询会拿到消息）；
      // 人就在看，角标也不该涨。
      const wins = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      const focused = wins.some((c) => c.focused || c.visibilityState === 'visible')
      if (focused) return
      await self.registration.showNotification(title, options)
      await bumpBadge()
    })(),
  )
})

// 页面回到前台时会 postMessage 过来，把持久化的未读数一并归零
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'clear-badge') event.waitUntil(resetBadge())
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    (async () => {
      await resetBadge()
      const wins = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      for (const c of wins) {
        if ('focus' in c) {
          if ('navigate' in c) {
            try {
              await c.navigate(url)
            } catch (e) {
              /* 跨源等情况忽略 */
            }
          }
          return c.focus()
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url)
    })(),
  )
})
