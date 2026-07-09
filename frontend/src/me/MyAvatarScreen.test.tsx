import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { MyAvatarScreen } from './MyAvatarScreen'

const MINE = {
  id: 1, couple_id: 1, subject_user_id: 1, keeper_user_id: 2,
  name: '小恶魔', appearance: { emoji: '😈' }, persona: {},
}

function me(ai_reply_enabled: boolean) {
  return { id: 1, nickname: 'alice', gender: 'female', ai_reply_enabled }
}

function mountable(ai_reply_enabled = false) {
  server.use(
    http.get('/api/avatars/mine', () => HttpResponse.json(MINE)),
    http.get('/api/auth/me', () => HttpResponse.json(me(ai_reply_enabled))),
  )
}

test('分身回复默认关闭，按钮邀请你「开启」', async () => {
  mountable(false)
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  expect(await screen.findByText('分身回复')).toBeInTheDocument()
  await waitFor(() => expect(screen.getByRole('button', { name: '开启' })).toBeInTheDocument())
})

test('点开关会 PATCH /auth/me，文案翻成「已开启」', async () => {
  mountable(false)
  const patched: unknown[] = []
  server.use(
    http.patch('/api/auth/me', async ({ request }) => {
      patched.push(await request.json())
      return HttpResponse.json(me(true))
    }),
  )
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  await userEvent.click(await screen.findByRole('button', { name: '开启' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '已开启' })).toBeInTheDocument())
  expect(patched).toEqual([{ ai_reply_enabled: true }])
})

test('已开启时再点一下是关掉', async () => {
  mountable(true)
  const patched: unknown[] = []
  server.use(
    http.patch('/api/auth/me', async ({ request }) => {
      patched.push(await request.json())
      return HttpResponse.json(me(false))
    }),
  )
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  await userEvent.click(await screen.findByRole('button', { name: '已开启' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '开启' })).toBeInTheDocument())
  expect(patched).toEqual([{ ai_reply_enabled: false }])
})

test('PATCH 失败时给一句人话，开关不假装成功', async () => {
  mountable(false)
  server.use(http.patch('/api/auth/me', () => new HttpResponse(null, { status: 500 })))
  renderWithProviders(<MyAvatarScreen onLogout={() => {}} />)
  await userEvent.click(await screen.findByRole('button', { name: '开启' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('没改成功')
  expect(screen.getByRole('button', { name: '开启' })).toBeInTheDocument()
})
