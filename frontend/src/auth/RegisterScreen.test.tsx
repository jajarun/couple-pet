import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect, beforeEach } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { AuthProvider } from './AuthContext'
import { RegisterScreen } from './RegisterScreen'

beforeEach(() => localStorage.clear())

test('duplicate nickname shows a friendly message', async () => {
  server.use(
    http.post('/api/auth/register', () =>
      HttpResponse.json({ detail: 'nickname already taken' }, { status: 409 }),
    ),
  )
  renderWithProviders(
    <AuthProvider>
      <RegisterScreen />
    </AuthProvider>,
  )
  await userEvent.click(screen.getByRole('radio', { name: '女生' }))
  await userEvent.type(screen.getByLabelText('昵称'), 'mimi')
  await userEvent.type(screen.getByLabelText('密码'), 'secret1')
  await userEvent.click(screen.getByRole('button', { name: '开始' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('这名字被抢啦，换一个')
})
