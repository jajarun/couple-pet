import { screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { test, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { PressButton } from './PressButton'

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }))
afterEach(() => vi.useRealTimers())

test('fires onPress then disables during cooldown, re-enables after', async () => {
  const onPress = vi.fn()
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
  renderWithProviders(
    <PressButton onPress={onPress} cooldownMs={800}>
      骂
    </PressButton>,
  )
  const btn = screen.getByRole('button', { name: '骂' })
  await user.click(btn)
  expect(onPress).toHaveBeenCalledTimes(1)
  expect(btn).toBeDisabled()
  await user.click(btn)
  expect(onPress).toHaveBeenCalledTimes(1) // still disabled, no second fire
  act(() => {
    vi.advanceTimersByTime(800)
  })
  expect(btn).not.toBeDisabled()
})
