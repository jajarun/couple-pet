import { apiRequest } from './client'
import { ActionBundle, GameEvent } from './types'

export function postAction(action_type: string, content: string, client_key: string) {
  return apiRequest<ActionBundle>('POST', '/actions', { action_type, content, client_key })
}

// 分身主动撩你：闲够了后端返回一条 nudge 事件，否则 event 为 null
export function postNudge() {
  return apiRequest<{ event: GameEvent | null }>('POST', '/nudge')
}
