import { useQuery } from '@tanstack/react-query'
import { getMe } from '../api/auth'

export const meKey = ['me'] as const

export function useMe() {
  return useQuery({ queryKey: meKey, queryFn: getMe })
}
