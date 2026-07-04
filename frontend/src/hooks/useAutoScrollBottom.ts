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
 * `count` is the number of items; pass a value that changes whenever the list grows.
 * Returns a ref to drop on a zero-height sentinel at the end of the list.
 */
export function useAutoScrollBottom(count: number) {
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
  }, [count])

  return endRef
}
