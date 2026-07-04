import { useMutation, useQueryClient } from '@tanstack/react-query'
import { respondToEvent } from '../api/events'
import { GameEvent } from '../api/types'
import { FeedData, feedKey, mergeEvents } from './useFeed'

export function useRespond(coupleId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { eventId: number; content: string; client_key: string }) =>
      respondToEvent(v.eventId, v.content, v.client_key),
    onSuccess: (ev: GameEvent) => {
      qc.setQueryData<FeedData>(feedKey(coupleId), (old) => {
        const merged = mergeEvents(old?.events ?? [], [ev])
        const cursor = merged.length ? merged[merged.length - 1].id : old?.cursor ?? 0
        return { events: merged, cursor }
      })
    },
  })
}
