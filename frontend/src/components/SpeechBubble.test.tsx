import { screen, act } from '@testing-library/react'
import { test, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { SpeechBubble } from './SpeechBubble'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

test('typing mode eventually reveals the full text', () => {
  renderWithProviders(<SpeechBubble text="大猪蹄子" typing />)
  act(() => { vi.advanceTimersByTime(2000) }) // act-wrapped: flush the typewriter interval's state updates
  expect(screen.getByText('大猪蹄子')).toBeInTheDocument()
})

test('non-typing mode shows text immediately', () => {
  renderWithProviders(<SpeechBubble text="哼" />)
  expect(screen.getByText('哼')).toBeInTheDocument()
})
