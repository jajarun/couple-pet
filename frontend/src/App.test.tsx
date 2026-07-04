import { screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import { renderWithProviders } from './test/utils'
import App from './App'

test('renders the app root', () => {
  renderWithProviders(<App />)
  expect(screen.getByText(/分身宠物孵化中/)).toBeInTheDocument()
})
