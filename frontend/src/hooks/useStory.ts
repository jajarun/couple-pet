import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getStory, postStoryChoice } from '../api/story'
import { ApiError } from '../api/client'
import { StoryResponse } from '../api/types'
import { feedKey } from './useFeed'
import { dailyKey } from './useDaily'
import { randomId } from '../uuid'

export function storyKey(coupleId: number) {
  return ['story', coupleId] as const
}

export function useStory(coupleId: number) {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: storyKey(coupleId),
    queryFn: getStory,
    refetchInterval: 20000, // 对方选完时自动解锁、下一幕自动冒出来
  })
  const mutation = useMutation({
    // client_key 放进 variables，重试复用同一个 key → 幂等（别在 mutationFn 里现生成）
    mutationFn: (v: { round_no: number; option_index: number; key: string }) =>
      postStoryChoice(v.round_no, v.option_index, v.key),
    retry: (n, e) => n < 2 && !(e instanceof ApiError), // 409 stale_round 不重试
    retryDelay: 200,
    onSuccess: (resp: StoryResponse) => {
      qc.setQueryData(storyKey(coupleId), resp)
      // 做选择算今日露面；打完还会往时间线上落一条纪念
      qc.invalidateQueries({ queryKey: dailyKey(coupleId) })
      if (resp.story.status === 'ended') qc.invalidateQueries({ queryKey: feedKey(coupleId) })
    },
  })
  return {
    data: query.data,
    isLoading: query.isLoading,
    choose: (round_no: number, option_index: number) =>
      mutation.mutateAsync({ round_no, option_index, key: randomId() }),
    isChoosing: mutation.isPending,
    error: mutation.error,
  }
}
