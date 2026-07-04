import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect, beforeEach } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { AuthProvider } from './AuthContext'
import { LoginScreen } from './LoginScreen'

beforeEach(() => localStorage.clear())

test('wrong credentials show a friendly message, not a raw error', async () => {
  server.use(
    http.post('/api/auth/login', () =>
      HttpResponse.json({ detail: 'bad credentials' }, { status: 401 }),
    ),
  )
  renderWithProviders(
    <AuthProvider>
      <LoginScreen />
    </AuthProvider>,
  )
  await userEvent.type(screen.getByLabelText('昵称'), 'mimi')
  await userEvent.type(screen.getByLabelText('密码'), 'wrongpw')
  await userEvent.click(screen.getByRole('button', { name: '进去' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('账号或密码不对哦~')
})
