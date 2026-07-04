import { useQuery } from '@tanstack/react-query'
import { getMyCouple } from '../api/couples'

export function useCouple(enabled: boolean) {
  return useQuery({
    queryKey: ['couple'],
    queryFn: getMyCouple,
    enabled,
    refetchInterval: (q) => (q.state.data?.status === 'pending' ? 2500 : false),
  })
}
