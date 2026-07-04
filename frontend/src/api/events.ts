import { apiRequest } from './client'
import { FeedResponse, GameEvent } from './types'

export function getEvents(params: { since?: number; before?: number; limit?: number } = {}) {
  const q = new URLSearchParams()
  if (params.since != null) q.set('since', String(params.since))
  if (params.before != null) q.set('before', String(params.before))
  if (params.limit != null) q.set('limit', String(params.limit))
  const qs = q.toString()
  return apiRequest<FeedResponse>('GET', `/events${qs ? `?${qs}` : ''}`)
}
export function respondToEvent(eventId: number, content: string, client_key: string) {
  return apiRequest<GameEvent>('POST', `/events/${eventId}/respond`, { content, client_key })
}
