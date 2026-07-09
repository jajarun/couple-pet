import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { test, expect, vi } from 'vitest'
import { RunawayScreen } from './RunawayScreen'

test('空窝 + 纸条 + 一个把它哄回来的按钮', () => {
  render(<RunawayScreen name="臭宝" note="走了。别找。（找的话，往老地方。）" pending={false} onCoax={() => {}} busy={false} />)
  expect(screen.getByText('臭宝走了')).toBeInTheDocument()
  expect(screen.getByText(/往老地方/)).toBeInTheDocument()
  expect(screen.getByText(/骂了它五次/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '🥺 去哄它回来' })).toBeEnabled()
})

test('没纸条也不炸', () => {
  render(<RunawayScreen name="臭宝" note={null} pending={false} onCoax={() => {}} busy={false} />)
  expect(screen.queryByText('它留了张纸条')).not.toBeInTheDocument()
})

test('点按钮去哄', async () => {
  const onCoax = vi.fn()
  render(<RunawayScreen name="臭宝" note="哼。" pending={false} onCoax={onCoax} busy={false} />)
  await userEvent.click(screen.getByRole('button', { name: '🥺 去哄它回来' }))
  expect(onCoax).toHaveBeenCalledOnce()
})

test('哄的过程中按钮禁用，防连点', () => {
  render(<RunawayScreen name="臭宝" note="哼。" pending={false} onCoax={() => {}} busy />)
  expect(screen.getByRole('button', { name: '正在把它哄回来…' })).toBeDisabled()
})

test('哄完了：按钮变成「等 TA 点头」，点不动', () => {
  render(<RunawayScreen name="臭宝" note="哼。" pending onCoax={() => {}} busy={false} />)
  expect(screen.getByTestId('awaiting-forgiveness')).toBeDisabled()
  expect(screen.getByText(/得 TA 说了算/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '🥺 去哄它回来' })).not.toBeInTheDocument()
})

test('两只都在外面时，空窝里塞得下点头的卡片', () => {
  render(
    <RunawayScreen name="臭宝" note="哼。" pending onCoax={() => {}} busy={false}>
      <div data-testid="forgive-card">原谅 TA</div>
    </RunawayScreen>,
  )
  expect(screen.getByTestId('forgive-card')).toBeInTheDocument()
})
