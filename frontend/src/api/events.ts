import { apiRequest } from './client'
import { FeedResponse, GameEvent } from './types'

export function getEvents(since: number) {
  return apiRequest<FeedResponse>('GET', `/events?since=${since}`)
}
export function respondToEvent(eventId: number, content: string, client_key: string) {
  return apiRequest<GameEvent>('POST', `/events/${eventId}/respond`, { content, client_key })
}
