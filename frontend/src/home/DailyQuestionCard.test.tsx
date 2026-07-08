import { describe, it, expect } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { DailyQuestionCard } from './DailyQuestionCard'

const q = { question: { text: '今晚想干嘛?', flavor: 'ambiguous' }, streak: { count: 1, i_did_today: false, partner_did_today: false, at_risk: false, lagging_user_id: null } }

describe('DailyQuestionCard', () => {
  it('未答:显示题目和输入框', async () => {
    server.use(http.get('/api/daily', () => HttpResponse.json({ ...q, my_answer: null, partner_answer: null, both_answered: false })))
    renderWithProviders(<DailyQuestionCard coupleId={1} />)
    await waitFor(() => expect(screen.getByText('今晚想干嘛?')).toBeTruthy())
    expect(screen.getByRole('textbox')).toBeTruthy()
  })

  it('已答未解锁:显示等 TA', async () => {
    server.use(http.get('/api/daily', () => HttpResponse.json({ ...q, my_answer: '睡觉', partner_answer: null, both_answered: false })))
    renderWithProviders(<DailyQuestionCard coupleId={1} />)
    await waitFor(() => expect(screen.getByText(/就等 TA/)).toBeTruthy())
  })

  it('双方解锁:并排显示两人答案', async () => {
    server.use(http.get('/api/daily', () => HttpResponse.json({ ...q, my_answer: '睡觉', partner_answer: '想你', both_answered: true })))
    renderWithProviders(<DailyQuestionCard coupleId={1} />)
    await waitFor(() => expect(screen.getByText('想你')).toBeTruthy())
    expect(screen.getByText('睡觉')).toBeTruthy()
  })
})
