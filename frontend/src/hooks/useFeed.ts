import { useCallback, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getEvents } from '../api/events'
import { GameEvent, Stats } from '../api/types'

export const FEED_PAGE = 25 // 首屏 / 每次上翻加载的条数

export interface FeedData {
  events: GameEvent[]
  cursor: number // 最新 id，向前轮询用
  oldestLoaded: number // 已加载最旧 id，向上翻页用
  hasMore: boolean // 更早还有没有历史
}

export function mergeEvents(prev: GameEvent[], incoming: GameEvent[]): GameEvent[] {
  const byId = new Map<number, GameEvent>()
  for (const e of prev) byId.set(e.id, e)
  for (const e of incoming) byId.set(e.id, e)
  return [...byId.values()].sort((a, b) => a.id - b.id)
}

// 追加新事件（来自动作/回应/nudge）——保留翻页游标，只在末尾长
export function appendToFeed(old: FeedData | undefined, incoming: GameEvent[]): FeedData {
  const events = mergeEvents(old?.events ?? [], incoming)
  return {
    events,
    cursor: events.length ? events[events.length - 1].id : old?.cursor ?? 0,
    oldestLoaded: old?.oldestLoaded ?? (events.length ? events[0].id : 0),
    hasMore: old?.hasMore ?? false,
  }
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
      if (coupleId == null) return { events: [], cursor: 0, oldestLoaded: 0, hasMore: false }
      const prev = qc.getQueryData<FeedData>(feedKey(coupleId))
      if (prev && prev.events.length) {
        // 已有窗口 → 只向前拉新消息，末尾累加
        const res = await getEvents({ since: prev.cursor })
        qc.setQueryData<Stats>(statsKey(coupleId), res.stats)
        const events = mergeEvents(prev.events, res.events)
        return {
          events,
          cursor: events.length ? events[events.length - 1].id : prev.cursor,
          oldestLoaded: prev.oldestLoaded || (events.length ? events[0].id : 0),
          hasMore: prev.hasMore,
        }
      }
      // 首屏 → 只拿最新一页
      const res = await getEvents({ limit: FEED_PAGE })
      qc.setQueryData<Stats>(statsKey(coupleId), res.stats)
      const events = res.events
      return {
        events,
        cursor: events.length ? events[events.length - 1].id : 0,
        oldestLoaded: events.length ? events[0].id : 0,
        hasMore: res.has_more ?? false,
      }
    },
  })
}

/** 向上翻页：拉一页更早的历史，前插到缓存。返回是否真的加载到了内容。 */
export function useLoadOlder(coupleId: number) {
  const qc = useQueryClient()
  const [loadingOlder, setLoading] = useState(false)
  const inflight = useRef(false)

  const loadOlder = useCallback(async (): Promise<boolean> => {
    const prev = qc.getQueryData<FeedData>(feedKey(coupleId))
    if (inflight.current || !prev || !prev.hasMore || prev.events.length === 0) return false
    inflight.current = true
    setLoading(true)
    try {
      const res = await getEvents({ before: prev.oldestLoaded, limit: FEED_PAGE })
      const cur = qc.getQueryData<FeedData>(feedKey(coupleId)) ?? prev
      const events = mergeEvents(res.events, cur.events)
      qc.setQueryData<FeedData>(feedKey(coupleId), {
        events,
        cursor: cur.cursor,
        oldestLoaded: events.length ? events[0].id : cur.oldestLoaded,
        hasMore: res.has_more ?? false,
      })
      return res.events.length > 0
    } finally {
      inflight.current = false
      setLoading(false)
    }
  }, [coupleId, qc])

  return { loadOlder, loadingOlder }
}
