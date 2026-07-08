import { apiRequest } from './client'
import { DailyResponse } from './types'

export function getDaily() {
  return apiRequest<DailyResponse>('GET', '/daily')
}
export function postDailyAnswer(content: string, client_key: string) {
  return apiRequest<DailyResponse>('POST', '/daily/answer', { content, client_key })
}
