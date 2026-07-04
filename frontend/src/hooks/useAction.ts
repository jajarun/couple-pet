import { useMutation, useQueryClient } from '@tanstack/react-query'
import { postAction } from '../api/actions'
import { ActionBundle, Stats } from '../api/types'
import { FeedData, feedKey, statsKey, mergeEvents } from './useFeed'

export function useAction(coupleId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { action_type: string; content: string; client_key: string }) =>
      postAction(v.action_type, v.content, v.client_key),
    onSuccess: (bundle: ActionBundle) => {
      qc.setQueryData<FeedData>(feedKey(coupleId), (old) => {
        const merged = mergeEvents(old?.events ?? [], bundle.events)
        const cursor = merged.length ? merged[merged.length - 1].id : old?.cursor ?? 0
        return { events: merged, cursor }
      })
      qc.setQueryData<Stats>(statsKey(coupleId), bundle.stats)
    },
  })
}
