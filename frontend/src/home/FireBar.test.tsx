import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { FireBar } from './FireBar'

const daily = (streak: Record<string, unknown>) => ({
  question: { text: 'q', flavor: 'deep' },
  my_answer: null,
  partner_answer: null,
  both_answered: false,
  streak,
})

const rescuable = {
  count: 0,
  i_did_today: false,
  partner_did_today: false,
  at_risk: false,
  rescuable: true,
  lagging_user_id: null,
}

describe('FireBar', () => {
  it('可救时露出续火按钮 + 提示', async () => {
    server.use(http.get('/api/daily', () => HttpResponse.json(daily(rescuable))))
    renderWithProviders(<FireBar coupleId={1} />)
    await screen.findByRole('button', { name: /花亲密续火/ })
    expect(screen.getByText(/还能救回来/)).toBeTruthy()
  })

  it('不可救时不显示按钮', async () => {
    server.use(http.get('/api/daily', () => HttpResponse.json(daily({ ...rescuable, rescuable: false, count: 3 }))))
    renderWithProviders(<FireBar coupleId={1} />)
    await screen.findByText('3 天')
    expect(screen.queryByRole('button', { name: /续火/ })).toBeNull()
  })

  it('点续火 → 调 POST /streak/rescue,天数恢复、按钮消失', async () => {
    server.use(http.get('/api/daily', () => HttpResponse.json(daily(rescuable))))
    server.use(
      http.post('/api/streak/rescue', () =>
        HttpResponse.json({ ...rescuable, count: 4, rescuable: false, at_risk: true }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<FireBar coupleId={1} />)
    await user.click(await screen.findByRole('button', { name: /花亲密续火/ }))
    await screen.findByText('4 天')                                    // 续火后天数回来
    expect(screen.queryByRole('button', { name: /续火/ })).toBeNull()  // 救过就不再露按钮
  })

  it('续火失败 → 卖萌提示', async () => {
    server.use(http.get('/api/daily', () => HttpResponse.json(daily(rescuable))))
    server.use(http.post('/api/streak/rescue', () => new HttpResponse(null, { status: 409 })))
    const user = userEvent.setup()
    renderWithProviders(<FireBar coupleId={1} />)
    await user.click(await screen.findByRole('button', { name: /花亲密续火/ }))
    expect(await screen.findByRole('alert')).toBeTruthy()
    await screen.findByText(/喝口水再试/)
  })
})
