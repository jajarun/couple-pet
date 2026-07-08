import { useCallback, useEffect, useState } from 'react'
import {
  deletePushSubscription,
  getVapidPublicKey,
  registerPushSubscription,
} from '../api/push'

// 浏览器是否支持 Web Push（jsdom / 老浏览器会缺这些全局，此时开关显示"不支持"）
export function isPushSupported(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    'serviceWorker' in navigator &&
    typeof window !== 'undefined' &&
    'PushManager' in window &&
    'Notification' in window
  )
}

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4)
  const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(b64)
  // 用显式 ArrayBuffer 回填，类型才是 Uint8Array<ArrayBuffer>（满足 applicationServerKey 的 BufferSource）
  const out = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
  return out
}

// 取浏览器订阅并登记到后端。假定通知权限已授予；无公钥（服务端没配）或失败抛错。
async function subscribeToPush(): Promise<void> {
  const { key } = await getVapidPublicKey()
  if (!key) throw new Error('push not enabled on server')
  const reg = await navigator.serviceWorker.ready
  let sub = await reg.pushManager.getSubscription()
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(key),
    })
  }
  const j = sub.toJSON()
  await registerPushSubscription({
    endpoint: sub.endpoint,
    keys: { p256dh: j.keys?.p256dh ?? '', auth: j.keys?.auth ?? '' },
  })
}

async function unsubscribeFromPush(): Promise<void> {
  const reg = await navigator.serviceWorker.ready
  const sub = await reg.pushManager.getSubscription()
  if (!sub) return
  const endpoint = sub.endpoint
  await sub.unsubscribe()
  await deletePushSubscription(endpoint)
}

/** 已授权则静默补订阅（MainShell 挂载时调，不弹权限框）。best-effort，吞错。 */
export async function ensurePushSubscribed(): Promise<void> {
  if (!isPushSupported() || Notification.permission !== 'granted') return
  try {
    await subscribeToPush()
  } catch {
    /* 静默：补订阅是尽力而为 */
  }
}

/** 「⚙️我」页签的推送开关用。turnOn 必须由用户手势触发（浏览器要求）。 */
export function usePush() {
  const supported = isPushSupported()
  const [enabled, setEnabled] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  // 初次挂载：若已授权，看是否已有订阅，同步开关初始态
  useEffect(() => {
    if (!supported || Notification.permission !== 'granted') return
    let cancelled = false
    navigator.serviceWorker.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) => {
        if (!cancelled) setEnabled(!!sub)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [supported])

  const turnOn = useCallback(async () => {
    setError('')
    setBusy(true)
    try {
      const perm = await Notification.requestPermission()
      if (perm !== 'granted') {
        setError('（你把通知拒了，想收推送得去浏览器/系统设置里开一下~）')
        return
      }
      await subscribeToPush()
      setEnabled(true)
    } catch {
      setError('（没订上，稍后再试试~）')
    } finally {
      setBusy(false)
    }
  }, [])

  const turnOff = useCallback(async () => {
    setError('')
    setBusy(true)
    try {
      await unsubscribeFromPush()
      setEnabled(false)
    } catch {
      setError('（关闭失败，稍后再试~）')
    } finally {
      setBusy(false)
    }
  }, [])

  return { supported, enabled, busy, error, turnOn, turnOff }
}
