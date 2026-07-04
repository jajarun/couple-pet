import { screen, act } from '@testing-library/react'
import { test, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { LoadingBanter } from './LoadingBanter'
import { BANTER_LINES } from '../banter'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

test('cycles to a different banter line over time', () => {
  renderWithProviders(<LoadingBanter intervalMs={1200} />)
  const first = screen.getByTestId('banter').textContent
  act(() => { vi.advanceTimersByTime(1200) }) // act-wrapped: flush the interval's state update
  const second = screen.getByTestId('banter').textContent
  expect(BANTER_LINES).toContain(second)
  expect(second).not.toBe(first)
})
