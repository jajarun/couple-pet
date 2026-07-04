import { useRef } from 'react'

export function useIdempotencyKey() {
  const ref = useRef<string | null>(null)
  return {
    next() {
      ref.current = crypto.randomUUID()
      return ref.current
    },
    current() {
      if (!ref.current) ref.current = crypto.randomUUID()
      return ref.current
    },
    clear() {
      ref.current = null
    },
  }
}
