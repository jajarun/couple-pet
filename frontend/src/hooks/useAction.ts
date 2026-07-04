import { useMutation, useQueryClient } from '@tanstack/react-query'
import { postAction } from '../api/actions'
import { ApiError } from '../api/client'
import { ActionBundle, Stats } from '../api/types'
import { FeedData, appendToFeed, feedKey, statsKey } from './useFeed'

export function useAction(coupleId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { action_type: string; content: string; client_key: string }) =>
      postAction(v.action_type, v.content, v.client_key),
    retry: (failureCount, error) => failureCount < 2 && !(error instanceof ApiError),
    retryDelay: 200,
    onSuccess: (bundle: ActionBundle) => {
      qc.setQueryData<FeedData>(feedKey(coupleId), (old) => appendToFeed(old, bundle.events))
      qc.setQueryData<Stats>(statsKey(coupleId), bundle.stats)
    },
  })
}
