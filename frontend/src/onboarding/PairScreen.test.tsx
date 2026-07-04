import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { PairScreen } from './PairScreen'

test('pending state shows the pair code and nudges the partner', () => {
  renderWithProviders(<PairScreen couple={{ couple_id: 1, status: 'pending', pair_code: 'A1B2C3' }} />)
  expect(screen.getByTestId('pair-code')).toHaveTextContent('A1B2C3')
  expect(screen.getByText(/催 TA/)).toBeInTheDocument()
})

test('invalid pair code shows a friendly message', async () => {
  server.use(
    http.post('/api/couples/join', () => HttpResponse.json({ detail: 'invalid pair code' }, { status: 404 })),
  )
  renderWithProviders(<PairScreen couple={{ couple_id: null, status: 'none' }} />)
  await userEvent.type(screen.getByLabelText('邀请码'), 'zzzzzz')
  await userEvent.click(screen.getByRole('button', { name: '加入' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('邀请码不对或失效啦')
})
