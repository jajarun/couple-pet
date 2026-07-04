import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { test, expect, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { TabBar } from './TabBar'

const tabs = [
  { key: 'home', label: '🏠 TA' },
  { key: 'feed', label: '🔔 事件流' },
]

test('marks the active tab and reports clicks', async () => {
  const onChange = vi.fn()
  renderWithProviders(<TabBar tabs={tabs} active="home" onChange={onChange} />)
  expect(screen.getByRole('tab', { name: '🏠 TA' })).toHaveAttribute('aria-selected', 'true')
  await userEvent.click(screen.getByRole('tab', { name: '🔔 事件流' }))
  expect(onChange).toHaveBeenCalledWith('feed')
})
