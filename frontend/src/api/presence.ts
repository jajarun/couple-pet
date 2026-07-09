import { apiRequest } from './client'
import { PresenceView } from './types'

/** 在线心跳。前端每 10 秒打一次，顺带拿回「TA 此刻在不在」。 */
export function pingPresence() {
  return apiRequest<PresenceView>('POST', '/presence')
}
