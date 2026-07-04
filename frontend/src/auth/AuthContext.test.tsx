import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect, beforeEach } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { AuthProvider, useAuth } from './AuthContext'

function Harness() {
  const { user, login } = useAuth()
  return (
    <div>
      <button onClick={() => login('mimi', 'secret1').catch(() => {})}>login</button>
      <span>user:{user?.nickname ?? 'none'}</span>
    </div>
  )
}

beforeEach(() => localStorage.clear())

test('login stores the user and token', async () => {
  server.use(
    http.post('/api/auth/login', () =>
      HttpResponse.json({
        access_token: 'tok',
        token_type: 'bearer',
        user: { id: 1, nickname: 'mimi' },
      }),
    ),
  )
  renderWithProviders(
    <AuthProvider>
      <Harness />
    </AuthProvider>,
  )
  expect(screen.getByText('user:none')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'login' }))
  expect(await screen.findByText('user:mimi')).toBeInTheDocument()
  expect(localStorage.getItem('couple.token')).toBe('tok')
})
