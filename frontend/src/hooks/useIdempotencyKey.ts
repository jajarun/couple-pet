import { useRef } from 'react'
import { randomId } from '../uuid'

export function useIdempotencyKey() {
  const ref = useRef<string | null>(null)
  return {
    next() {
      ref.current = randomId()
      return ref.current
    },
    current() {
      if (!ref.current) ref.current = randomId()
      return ref.current
    },
    clear() {
      ref.current = null
    },
  }
}
