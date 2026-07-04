import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getEvents } from '../api/events'
import { GameEvent, Stats } from '../api/types'

export interface FeedData {
  events: GameEvent[]
  cursor: number
}

export function mergeEvents(prev: GameEvent[], incoming: GameEvent[]): GameEvent[] {
  const byId = new Map<number, GameEvent>()
  for (const e of prev) byId.set(e.id, e)
  for (const e of incoming) byId.set(e.id, e)
  return [...byId.values()].sort((a, b) => a.id - b.id)
}

export function feedKey(coupleId: number) {
  return ['feed', coupleId] as const
}
export function statsKey(coupleId: number) {
  return ['stats', coupleId] as const
}

export function useFeed(coupleId: number | null) {
  const qc = useQueryClient()
  return useQuery({
    queryKey: coupleId == null ? (['feed', 'none'] as const) : feedKey(coupleId),
    enabled: coupleId != null,
    refetchInterval: 3000,
    queryFn: async (): Promise<FeedData> => {
      const prev = qc.getQueryData<FeedData>(feedKey(coupleId!))
      const cursor = prev?.cursor ?? 0
      const res = await getEvents(cursor)
      const events = mergeEvents(prev?.events ?? [], res.events)
      const nextCursor = events.length ? events[events.length - 1].id : cursor
      qc.setQueryData<Stats>(statsKey(coupleId!), res.stats)
      return { events, cursor: nextCursor }
    },
  })
}
