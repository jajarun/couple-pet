import { apiRequest } from './client'
import { Avatar } from './types'

export function getMyAvatar() {
  return apiRequest<Avatar>('GET', '/avatars/mine')
}
export function getPetAvatar() {
  return apiRequest<Avatar>('GET', '/avatars/pet')
}
export function updateMyAvatar(patch: {
  name?: string
  appearance?: Record<string, unknown>
  persona?: Record<string, unknown>
}) {
  return apiRequest<Avatar>('PUT', '/avatars/mine', patch)
}
