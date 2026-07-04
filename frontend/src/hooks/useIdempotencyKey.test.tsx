import { renderHook } from '@testing-library/react'
import { test, expect } from 'vitest'
import { useIdempotencyKey } from './useIdempotencyKey'

test('current is stable until cleared; next rotates', () => {
  const { result } = renderHook(() => useIdempotencyKey())
  const a = result.current.current()
  expect(result.current.current()).toBe(a)
  const b = result.current.next()
  expect(b).not.toBe(a)
  result.current.clear()
  expect(result.current.current()).not.toBe(b)
})
