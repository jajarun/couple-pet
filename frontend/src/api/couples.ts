import { apiRequest } from './client'
import { CoupleState } from './types'

export function getMyCouple() {
  return apiRequest<CoupleState>('GET', '/couples/me')
}
export function createCouple() {
  return apiRequest<{ couple_id: number; pair_code: string; status: string }>('POST', '/couples')
}
export function joinCouple(pair_code: string) {
  return apiRequest<{ couple_id: number; status: string }>('POST', '/couples/join', { pair_code })
}
