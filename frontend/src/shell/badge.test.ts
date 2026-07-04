import { test, expect } from 'vitest'
import { hasUnseen } from './badge'

test('flags unseen only when a newer event exists and chat is not the active tab', () => {
  expect(hasUnseen(10, 8, 'home')).toBe(true)
  expect(hasUnseen(10, 10, 'home')).toBe(false)
  expect(hasUnseen(10, 8, 'chat')).toBe(false)
})
