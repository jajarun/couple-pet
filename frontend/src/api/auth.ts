import { apiRequest } from './client'
import { AuthResponse } from './types'

export function registerUser(nickname: string, password: string) {
  return apiRequest<AuthResponse>('POST', '/auth/register', { nickname, password })
}
export function loginUser(nickname: string, password: string) {
  return apiRequest<AuthResponse>('POST', '/auth/login', { nickname, password })
}
