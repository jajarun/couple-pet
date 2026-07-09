import { useQuery } from '@tanstack/react-query'
import { pingPresence } from '../api/presence'

export const presenceKey = ['presence'] as const

/**
 * 在线心跳。**故意用 useQuery 而不是手写 setInterval**：
 * TanStack 的 refetchInterval 在页面切后台时自动暂停 → 心跳停 → 我对 TA 自动显示为离线，
 * 而 refetchOnWindowFocus（全局开着）让我回前台的一瞬间就重新亮起。
 * 「切后台就下线」正是「TA 正在看这只分身」想要的语义。
 */
export function usePresence() {
  return useQuery({ queryKey: presenceKey, queryFn: pingPresence, refetchInterval: 10_000 })
}
