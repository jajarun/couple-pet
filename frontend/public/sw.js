// 情侣宠物 · 最小 Service Worker：只处理 Web Push 的收推送与点击，不做离线缓存。
/* eslint-disable no-restricted-globals */

// 改动后的 SW 立刻接管，不用等所有旧标签页关掉（省得测试/发版时更新不生效）
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

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
      // 页面正开着且聚焦时别弹系统通知打扰（前台已有 3s 轮询会拿到消息）
      const wins = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      const focused = wins.some((c) => c.focused || c.visibilityState === 'visible')
      if (focused) return
      await self.registration.showNotification(title, options)
    })(),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    (async () => {
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
