import { apiRequest } from './client'
import { StoryResponse } from './types'

export function getStory() {
  return apiRequest<StoryResponse>('GET', '/story')
}
export function postStoryChoice(round_no: number, option_index: number, client_key: string) {
  return apiRequest<StoryResponse>('POST', '/story/choose', {
    round_no,
    option_index,
    client_key,
  })
}
