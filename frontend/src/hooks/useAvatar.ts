import { useQuery } from '@tanstack/react-query'
import { getMyAvatar, getPetAvatar } from '../api/avatars'

export function useMyAvatar(enabled: boolean) {
  return useQuery({ queryKey: ['avatar', 'mine'], queryFn: getMyAvatar, enabled })
}
export function usePetAvatar(enabled: boolean) {
  return useQuery({ queryKey: ['avatar', 'pet'], queryFn: getPetAvatar, enabled })
}
