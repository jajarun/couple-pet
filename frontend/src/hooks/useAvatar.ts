import { useQuery } from '@tanstack/react-query'
import { getMyAvatar, getPetAvatar } from '../api/avatars'

export const myAvatarKey = ['avatar', 'mine'] as const
export const petAvatarKey = ['avatar', 'pet'] as const

/** TA 养的那只（代表我）——「我在 TA 眼里被养成了什么样」 */
export function useMyAvatar(enabled: boolean) {
  return useQuery({ queryKey: myAvatarKey, queryFn: getMyAvatar, enabled })
}
/** 我养的那只（代表 TA）——「我把 TA 养成了什么样」 */
export function usePetAvatar(enabled: boolean) {
  return useQuery({ queryKey: petAvatarKey, queryFn: getPetAvatar, enabled })
}
