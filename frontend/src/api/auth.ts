import { apiRequest } from './client'
import { AuthResponse, Me } from './types'
import { Gender } from '../theme'

export function registerUser(nickname: string, password: string, gender: Gender) {
  return apiRequest<AuthResponse>('POST', '/auth/register', { nickname, password, gender })
}
export function loginUser(nickname: string, password: string) {
  return apiRequest<AuthResponse>('POST', '/auth/login', { nickname, password })
}
export function getMe() {
  return apiRequest<Me>('GET', '/auth/me')
}
export function updateMe(patch: { ai_reply_enabled?: boolean }) {
  return apiRequest<Me>('PATCH', '/auth/me', patch)
}
