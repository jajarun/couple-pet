import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getDaily, postDailyAnswer } from '../api/daily'
import { ApiError } from '../api/client'
import { DailyResponse } from '../api/types'
import { randomId } from '../uuid'

export function dailyKey(coupleId: number) {
  return ['daily', coupleId] as const
}

export function useDaily(coupleId: number) {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: dailyKey(coupleId),
    queryFn: getDaily,
    refetchInterval: 20000, // 对方答完时自动解锁
  })
  const mutation = useMutation({
    // client_key 放进 variables，重试时复用同一个 key → 幂等（别在 mutationFn 里现生成）
    mutationFn: (v: { content: string; key: string }) => postDailyAnswer(v.content, v.key),
    retry: (n, e) => n < 2 && !(e instanceof ApiError),
    retryDelay: 200,
    onSuccess: (resp: DailyResponse) => qc.setQueryData(dailyKey(coupleId), resp),
  })
  return {
    data: query.data,
    isLoading: query.isLoading,
    answer: (content: string) => mutation.mutateAsync({ content, key: randomId() }),
    isAnswering: mutation.isPending,
  }
}
