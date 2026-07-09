import { describe, it, expect } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { DailyCard } from './DailyCard'

const healthy = {
  count: 1,
  i_did_today: false,
  partner_did_today: false,
  at_risk: false,
  rescuable: false,
  lagging_user_id: null,
}
const rescuable = { ...healthy, count: 0, rescuable: true }

/** 桩一份 GET /api/daily；streak 不传就是「火苗健康」，不会渲染告急行 */
function stubDaily(over: Record<string, unknown> = {}, streak: Record<string, unknown> = healthy) {
  const body = {
    question: { text: '今晚想干嘛?', flavor: 'ambiguous' },
    my_answer: null,
    partner_answer: null,
    both_answered: false,
    ...over,
    streak,
  }
  server.use(http.get('/api/daily', () => HttpResponse.json(body)))
}

const answered = { my_answer: '睡觉', partner_answer: '想你', both_answered: true }

describe('DailyCard · 每日一问', () => {
  it('未答:显示题目和输入框', async () => {
    stubDaily()
    renderWithProviders(<DailyCard coupleId={1} />)
    await waitFor(() => expect(screen.getByText('今晚想干嘛?')).toBeTruthy())
    expect(screen.getByRole('textbox')).toBeTruthy()
  })

  it('已答未解锁:显示等 TA', async () => {
    stubDaily({ my_answer: '睡觉' })
    renderWithProviders(<DailyCard coupleId={1} />)
    await waitFor(() => expect(screen.getByText(/就等 TA/)).toBeTruthy())
  })

  it('双方解锁:展开后并排显示两人答案', async () => {
    stubDaily(answered)
    const user = userEvent.setup()
    renderWithProviders(<DailyCard coupleId={1} />)
    await user.click(await screen.findByRole('button', { name: /看答案/ }))
    expect(screen.getByText('想你')).toBeTruthy()
    expect(screen.getByText('睡觉')).toBeTruthy()
  })

  it('提交失败:显示卖萌错误提示', async () => {
    stubDaily()
    server.use(http.post('/api/daily/answer', () => new HttpResponse(null, { status: 500 })))
    const user = userEvent.setup()
    renderWithProviders(<DailyCard coupleId={1} />)
    await waitFor(() => expect(screen.getByText('今晚想干嘛?')).toBeTruthy())
    await user.type(screen.getByRole('textbox'), '睡觉')
    await user.click(screen.getByRole('button', { name: '答一个' }))
    await screen.findByText(/喝口水再答/)
    expect(await screen.findByRole('alert')).toBeTruthy()
  })
})

describe('DailyCard · 答案折叠', () => {
  it('默认收起:只看得到题目,答案不在 DOM 里', async () => {
    stubDaily(answered)
    renderWithProviders(<DailyCard coupleId={1} />)
    const peek = await screen.findByRole('button', { name: /看答案/ })

    expect(screen.getByText('今晚想干嘛?')).toBeTruthy()
    expect(peek).toHaveAttribute('aria-expanded', 'false')
    // 必须是「不在 DOM 里」，不是 CSS 藏起来——藏在 DOM 里等于没藏
    expect(screen.queryByText('睡觉')).toBeNull()
    expect(screen.queryByText('想你')).toBeNull()
  })

  it('点一下展开,答案露出来,按钮改口叫「收起」', async () => {
    stubDaily(answered)
    const user = userEvent.setup()
    renderWithProviders(<DailyCard coupleId={1} />)
    await user.click(await screen.findByRole('button', { name: /看答案/ }))

    expect(screen.getByText('睡觉')).toBeTruthy()
    expect(screen.getByText('想你')).toBeTruthy()
    const peek = screen.getByRole('button', { name: /收起/ })
    expect(peek).toHaveAttribute('aria-expanded', 'true')
    // aria-controls 得真的指向那块答案，屏幕阅读器才跟得上
    expect(document.getElementById(peek.getAttribute('aria-controls')!)).toBeTruthy()
  })

  it('再点一下又收回去', async () => {
    stubDaily(answered)
    const user = userEvent.setup()
    renderWithProviders(<DailyCard coupleId={1} />)
    await user.click(await screen.findByRole('button', { name: /看答案/ }))
    await user.click(screen.getByRole('button', { name: /收起/ }))

    expect(screen.queryByText('睡觉')).toBeNull()
    expect(screen.getByRole('button', { name: /看答案/ })).toHaveAttribute('aria-expanded', 'false')
  })

  it('没答完时没有折叠键:压根没有答案可藏', async () => {
    stubDaily()
    renderWithProviders(<DailyCard coupleId={1} />)
    await screen.findByRole('textbox') // 输入框照常在，藏了就没法答题
    expect(screen.queryByRole('button', { name: /看答案|收起/ })).toBeNull()
  })

  it('答完等 TA 时也没有折叠键', async () => {
    stubDaily({ my_answer: '睡觉' })
    renderWithProviders(<DailyCard coupleId={1} />)
    await screen.findByText(/就等 TA/)
    expect(screen.queryByRole('button', { name: /看答案|收起/ })).toBeNull()
  })
})

describe('DailyCard · 火苗', () => {
  it('可救时露出续火按钮 + 提示', async () => {
    stubDaily({}, rescuable)
    renderWithProviders(<DailyCard coupleId={1} />)
    await screen.findByRole('button', { name: /花亲密续火/ })
    expect(screen.getByText(/还能救回来/)).toBeTruthy()
  })

  it('不可救时不显示按钮', async () => {
    stubDaily({}, { ...healthy, count: 3 })
    renderWithProviders(<DailyCard coupleId={1} />)
    await screen.findByText('3 天')
    expect(screen.queryByRole('button', { name: /续火/ })).toBeNull()
  })

  it('点续火 → 调 POST /streak/rescue,天数恢复、按钮消失', async () => {
    stubDaily({}, rescuable)
    server.use(
      http.post('/api/streak/rescue', () =>
        HttpResponse.json({ ...rescuable, count: 4, rescuable: false, at_risk: true }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<DailyCard coupleId={1} />)
    await user.click(await screen.findByRole('button', { name: /花亲密续火/ }))
    await screen.findByText('4 天') // 续火后天数回来
    expect(screen.queryByRole('button', { name: /续火/ })).toBeNull() // 救过就不再露按钮
  })

  it('续火失败 → 卖萌提示', async () => {
    stubDaily({}, rescuable)
    server.use(http.post('/api/streak/rescue', () => new HttpResponse(null, { status: 409 })))
    const user = userEvent.setup()
    renderWithProviders(<DailyCard coupleId={1} />)
    await user.click(await screen.findByRole('button', { name: /花亲密续火/ }))
    expect(await screen.findByRole('alert')).toBeTruthy()
    await screen.findByText(/喝口水再试/)
  })

  it('火苗健康:chip 不变红,告急那一行压根不存在', async () => {
    stubDaily({}, { ...healthy, count: 5 })
    const { container, unmount } = renderWithProviders(<DailyCard coupleId={1} />)
    await screen.findByText('5 天')

    expect(screen.getByRole('status')).not.toHaveClass('at-risk')
    // 空的 .daily-fire 也不许留——它会白白吃掉卡片 10px 的 gap
    expect(container.querySelector('.daily-fire')).toBeNull()
    unmount()
  })

  it('火苗告急:chip 变红,多出一行提示', async () => {
    stubDaily({}, { ...healthy, count: 5, at_risk: true })
    const { container } = renderWithProviders(<DailyCard coupleId={1} />)
    await screen.findByText(/快断了!今天还没露面/)

    expect(screen.getByRole('status')).toHaveClass('at-risk')
    expect(container.querySelector('.daily-fire')).toBeTruthy()
  })
})
