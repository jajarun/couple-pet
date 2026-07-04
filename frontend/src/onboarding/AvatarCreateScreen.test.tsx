import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { test, expect } from 'vitest'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { AvatarCreateScreen } from './AvatarCreateScreen'

test('submitting captures name/appearance/persona via PUT', async () => {
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
  await userEvent.click(screen.getByRole('radio', { name: '毒舌' }))
  await userEvent.type(screen.getByLabelText('名字'), '臭宝')
  await userEvent.click(screen.getByRole('button', { name: '就它了' }))
  await waitFor(() => expect(body).not.toBeNull())
  expect(body).toMatchObject({ name: '臭宝', appearance: { tone: '毒舌' }, persona: { tone: '毒舌' } })
})
