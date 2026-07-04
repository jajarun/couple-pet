import { apiRequest } from './client'
import { ActionBundle } from './types'

export function postAction(action_type: string, content: string, client_key: string) {
  return apiRequest<ActionBundle>('POST', '/actions', { action_type, content, client_key })
}
