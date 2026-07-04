import { apiRequest } from './client'
import { AuthResponse } from './types'
import { Gender } from '../theme'

export function registerUser(nickname: string, password: string, gender: Gender) {
  return apiRequest<AuthResponse>('POST', '/auth/register', { nickname, password, gender })
}
export function loginUser(nickname: string, password: string) {
  return apiRequest<AuthResponse>('POST', '/auth/login', { nickname, password })
}
