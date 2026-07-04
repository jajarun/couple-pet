import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { postNudge } from '../api/actions'
import { GameEvent } from '../api/types'
import { FeedData, appendToFeed, feedKey } from './useFeed'

/**
 * While the app is open and visible, ask the backend every `intervalMs` whether
 * TA's avatar wants to nudge you. The backend only actually nudges after enough
 * idle time, so most polls are no-ops. Any returned event is merged into the feed
 * cache → shows up in chat, lights the badge, and pops the pet's bubble on Home.
 */
export function useNudge(coupleId: number, intervalMs = 60000) {
  const qc = useQueryClient()
  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      if (document.visibilityState !== 'visible') return
      try {
        const res = await postNudge()
        const ev = res?.event
        if (cancelled || !ev) return
        qc.setQueryData<FeedData>(feedKey(coupleId), (old) => appendToFeed(old, [ev as GameEvent]))
      } catch {
        /* nudges are best-effort; ignore errors */
      }
    }
    const id = setInterval(tick, intervalMs)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [coupleId, intervalMs, qc])
}
