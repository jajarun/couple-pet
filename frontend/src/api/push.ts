import { apiRequest } from './client'
import { PushSubscribePayload } from './types'

// VAPID 公钥；空串表示服务端未启用推送（前端据此隐藏开关）
export function getVapidPublicKey() {
  return apiRequest<{ key: string }>('GET', '/push/public-key')
}

export function registerPushSubscription(sub: PushSubscribePayload) {
  return apiRequest<void>('POST', '/push/subscribe', sub)
}

export function deletePushSubscription(endpoint: string) {
  return apiRequest<void>('DELETE', '/push/subscribe', { endpoint })
}
