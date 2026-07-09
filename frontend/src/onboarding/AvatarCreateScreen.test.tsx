import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { AvatarCreateScreen } from './AvatarCreateScreen'

test('submitting captures name/appearance/persona (tone 多选) via PUT', async () => {
  let body: { name: string; appearance: Record<string, unknown>; persona: Record<string, unknown> } | null = null
  server.use(
    http.put('/api/avatars/mine', async ({ request }) => {
      body = (await request.json()) as typeof body
      return HttpResponse.json({
        id: 1, couple_id: 1, subject_user_id: 1, keeper_user_id: 2,
        name: body!.name, appearance: body!.appearance, persona: body!.persona,
      })
    }),
  )
  renderWithProviders(<AvatarCreateScreen />)
  // 默认已选「毒舌」，再加一个「傲娇」验证多选
  await userEvent.click(screen.getByRole('checkbox', { name: '傲娇' }))
  await userEvent.type(screen.getByLabelText('名字'), '臭宝')
  await userEvent.click(screen.getByRole('button', { name: '就它了' }))
  await waitFor(() => expect(body).not.toBeNull())
  expect(body).toMatchObject({
    name: '臭宝',
    appearance: { tone: ['毒舌', '傲娇'] },
    persona: { tone: ['毒舌', '傲娇'] },
  })
})

test('造型收在抽屉里；点分身挑一个，提交时带上它', async () => {
  let body: { appearance: Record<string, unknown> } | null = null
  server.use(
    http.put('/api/avatars/mine', async ({ request }) => {
      body = (await request.json()) as typeof body
      return HttpResponse.json({ id: 1, couple_id: 1, subject_user_id: 1, keeper_user_id: 2 })
    }),
  )
  renderWithProviders(<AvatarCreateScreen />)
  expect(screen.queryByLabelText('emoji-🦊')).not.toBeInTheDocument() // 不占页面

  await userEvent.click(screen.getByLabelText('换造型，当前 🐷')) // 默认是清单第一个
  await userEvent.click(await screen.findByLabelText('emoji-🦊'))
  await userEvent.type(screen.getByLabelText('名字'), '臭宝')
  await userEvent.click(screen.getByRole('button', { name: '就它了' }))

  await waitFor(() => expect(body).not.toBeNull())
  expect(body!.appearance).toMatchObject({ emoji: '🦊' })
})

test('基调最多选 3 个、且至少留 1 个', async () => {
  renderWithProviders(<AvatarCreateScreen />)
  // 默认「毒舌」已选，再点两个凑满 3 个
  await userEvent.click(screen.getByRole('checkbox', { name: '傲娇' }))
  await userEvent.click(screen.getByRole('checkbox', { name: '憨憨' }))
  // 满 3 个后，未选中的被禁用（选不了第 4 个）
  expect(screen.getByRole('checkbox', { name: '沙雕' })).toBeDisabled()
  expect(screen.getByRole('checkbox', { name: '毒舌' })).toHaveAttribute('aria-checked', 'true')

  // 取消到只剩 1 个后，最后一个点不掉（保底 1 个）
  await userEvent.click(screen.getByRole('checkbox', { name: '傲娇' }))
  await userEvent.click(screen.getByRole('checkbox', { name: '憨憨' }))
  await userEvent.click(screen.getByRole('checkbox', { name: '毒舌' }))
  expect(screen.getByRole('checkbox', { name: '毒舌' })).toHaveAttribute('aria-checked', 'true')
})
