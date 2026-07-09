import { useEffect, useRef } from 'react'

function scrollParent(el: HTMLElement | null): HTMLElement | null {
  let n = el?.parentElement ?? null
  while (n) {
    const oy = getComputedStyle(n).overflowY
    if (oy === 'auto' || oy === 'scroll') return n
    n = n.parentElement
  }
  return null
}

/**
 * Chat-style scrolling: keep the list in natural (oldest→newest) order, but land
 * at the bottom on open and follow new items — only while the user is already
 * parked near the bottom, so scrolling up to read history is never yanked away.
 *
 * `count` 是列表条数；`pending` 是「底部还挂着一个占位（如加载中）」。
 * 两者必须分开传，别自己加成一个数——`count+1 / pending` 和 `count / 无 pending`
 * 会算出同一个值，发送完最后一条时就不滚了（分身不接话时只多 1 条事件，正好撞上）。
 * 返回一个 ref，挂在列表末尾的零高度哨兵上。
 */
export function useAutoScrollBottom(count: number, pending = false) {
  const endRef = useRef<HTMLDivElement>(null)
  const stick = useRef(true)
  const landed = useRef(false)

  useEffect(() => {
    const sc = scrollParent(endRef.current)
    if (!sc) return
    const onScroll = () => {
      stick.current = sc.scrollHeight - sc.scrollTop - sc.clientHeight < 80
    }
    sc.addEventListener('scroll', onScroll, { passive: true })
    return () => sc.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    const end = endRef.current
    if (!end || typeof end.scrollIntoView !== 'function') return // jsdom has no scrollIntoView
    const reduce =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!landed.current && count > 0) {
      end.scrollIntoView({ block: 'end', inline: 'nearest' }) // first landing: instant
      landed.current = true
    } else if (stick.current) {
      end.scrollIntoView({ block: 'end', inline: 'nearest', behavior: reduce ? 'auto' : 'smooth' })
    }
  }, [count, pending])

  return endRef
}
