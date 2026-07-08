import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getDaily, postDailyAnswer, postRescueStreak } from '../api/daily'
import { ApiError } from '../api/client'
import { DailyResponse, StreakView } from '../api/types'
import { feedKey } from './useFeed'
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
  const rescueMut = useMutation({
    mutationFn: postRescueStreak,
    retry: (n, e) => n < 2 && !(e instanceof ApiError), // 409「cannot rescue」不重试
    retryDelay: 200,
    onSuccess: (streak: StreakView) => {
      // 续火端点只回 streak view → 合并进 daily 缓存，不整体替换
      qc.setQueryData<DailyResponse>(dailyKey(coupleId), (old) => (old ? { ...old, streak } : old))
      // 亲密被扣了 → 让 useFeed 重拉，刷新亲密 gauge
      qc.invalidateQueries({ queryKey: feedKey(coupleId) })
    },
  })
  return {
    data: query.data,
    isLoading: query.isLoading,
    answer: (content: string) => mutation.mutateAsync({ content, key: randomId() }),
    isAnswering: mutation.isPending,
    rescue: () => rescueMut.mutateAsync(),
    isRescuing: rescueMut.isPending,
  }
}
