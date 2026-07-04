import { screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { StatGauge } from './StatGauge'

test('renders value and alarm flag', () => {
  renderWithProviders(<StatGauge label="委屈" value={85} alarm />)
  expect(screen.getByText('委屈')).toBeInTheDocument()
  expect(screen.getByText('85')).toBeInTheDocument()
  expect(screen.getByTestId('gauge-委屈')).toHaveAttribute('data-alarm', 'true')
})
