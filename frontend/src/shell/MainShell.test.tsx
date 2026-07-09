import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import { STORY_ROUND_ONE } from '../test/handlers'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { MainShell } from './MainShell'

function shell() {
  return renderWithProviders(
    <AuthProvider>
      <MainShell coupleId={1} myUserId={1} partnerId={2} />
    </AuthProvider>,
  )
}

const NOT_MY_TURN = { ...STORY_ROUND_ONE, my_turn: false }

test('四个页签，剧情排在「我」前面', async () => {
  shell()
  // 默认桩的 my_turn 是 true，等 /story 落地、红点点亮之后再比顺序
  await screen.findByRole('tab', { name: '🎭 剧情 🔴' })
  expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual([
    '🏠 TA',
    '💬 聊天',
    '🎭 剧情 🔴',
    '⚙️ 我',
  ])
})

test('轮到你选时 🎭 页签亮红点，不轮到你就不亮', async () => {
  server.use(http.get('/api/story', () => HttpResponse.json(NOT_MY_TURN)))
  shell()
  await waitFor(() =>
    expect(screen.getByRole('tab', { name: '🎭 剧情' })).toBeInTheDocument(),
  )
  expect(screen.queryByRole('tab', { name: '🎭 剧情 🔴' })).not.toBeInTheDocument()
})

test('点 🎭 进得去剧情页', async () => {
  server.use(http.get('/api/story', () => HttpResponse.json(NOT_MY_TURN)))
  shell()
  await userEvent.click(await screen.findByRole('tab', { name: '🎭 剧情' }))
  expect(await screen.findByText('🎭 困在电梯里')).toBeInTheDocument()
})

test('TA 在线时首页亮起同框 banner（心跳来自 POST /presence）', async () => {
  server.use(http.post('/api/presence', () => HttpResponse.json({ partner_online: true })))
  shell()
  expect(await screen.findByTestId('together-banner')).toBeInTheDocument()
})

test('TA 不在线时没有 banner，也没有摸摸头', async () => {
  shell()
  await screen.findByRole('button', { name: '骂一顿' })
  expect(screen.queryByTestId('together-banner')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '摸摸头' })).not.toBeInTheDocument()
})
