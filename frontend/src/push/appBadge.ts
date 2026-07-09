// 主屏图标右上角的未读角标。iOS 16.4+ / 装成主屏 App / 已授通知权限才有；
// 其余环境（Safari 标签页、Firefox…）静默降级——跟「没配 VAPID 私钥就整套关掉」同一个契约。
//
// 数字由 sw.js 在收推送时 +1 并落进 IndexedDB。这里只负责「清零」：
// 页面自己清一次图标（App 开着时 SW 未必醒着），再让 SW 把它那份持久计数也归零。

// lib.dom 还没收录 Badging API，这里自己声明
type BadgeNavigator = Navigator & {
  clearAppBadge?: () => Promise<void>
}

export function clearAppBadge(): void {
  const nav = navigator as BadgeNavigator
  if (typeof nav.clearAppBadge === 'function') {
    nav.clearAppBadge().catch(() => {
      /* 静默：角标清不掉不该冒泡到 UI */
    })
  }
  navigator.serviceWorker?.controller?.postMessage({ type: 'clear-badge' })
}
