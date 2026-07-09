import { useState } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { test, expect, vi } from 'vitest'
import { EmojiPicker } from './EmojiPicker'

/** 受控组件，用一个小壳子把 value 接起来 */
function Harness({ initial = '🐷', onChange }: { initial?: string; onChange?: (em: string) => void }) {
  const [emoji, setEmoji] = useState(initial)
  return (
    <EmojiPicker
      value={emoji}
      onChange={(em) => {
        setEmoji(em)
        onChange?.(em)
      }}
    />
  )
}

test('平时只有一个分身，28 个 emoji 不占页面', () => {
  render(<Harness />)
  expect(screen.getByLabelText('换造型，当前 🐷')).toHaveTextContent('🐷')
  expect(screen.queryByTestId('emoji-sheet')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('emoji-🦊')).not.toBeInTheDocument()
})

test('点分身弹出抽屉，当前造型高亮', async () => {
  render(<Harness />)
  await userEvent.click(screen.getByLabelText('换造型，当前 🐷'))

  expect(await screen.findByTestId('emoji-sheet')).toBeInTheDocument()
  expect(screen.getByLabelText('emoji-🐷')).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByLabelText('emoji-🦊')).toHaveAttribute('aria-pressed', 'false')
})

test('分组排版：四段标题都在', async () => {
  render(<Harness />)
  await userEvent.click(screen.getByLabelText('换造型，当前 🐷'))
  for (const label of ['动物', '人物', '角色', '其它']) {
    expect(await screen.findByText(label)).toBeInTheDocument()
  }
})

test('挑一个就关闭，一次点击搞定', async () => {
  const onChange = vi.fn()
  render(<Harness onChange={onChange} />)
  await userEvent.click(screen.getByLabelText('换造型，当前 🐷'))
  await userEvent.click(await screen.findByLabelText('emoji-🦊'))

  expect(onChange.mock.calls).toEqual([['🦊']])
  await waitFor(() => expect(screen.queryByTestId('emoji-sheet')).not.toBeInTheDocument())
  expect(screen.getByLabelText('换造型，当前 🦊')).toHaveTextContent('🦊')
})

test('点遮罩关掉，不改造型', async () => {
  const onChange = vi.fn()
  render(<Harness onChange={onChange} />)
  await userEvent.click(screen.getByLabelText('换造型，当前 🐷'))
  await screen.findByTestId('emoji-sheet')

  await userEvent.click(document.querySelector('.sheet-backdrop') as HTMLElement)
  await waitFor(() => expect(screen.queryByTestId('emoji-sheet')).not.toBeInTheDocument())
  expect(onChange).not.toHaveBeenCalled()
})

// 长在触发它的子树里，就会继承页面的 text-align，且 position:fixed 会被带 transform
// 的祖先劫持成相对定位。挂 body 上这两件事都不会发生。
test('抽屉挂在 body 上，不长在触发它的那棵子树里', async () => {
  const { container } = render(<Harness />)
  await userEvent.click(screen.getByLabelText('换造型，当前 🐷'))
  await screen.findByTestId('emoji-sheet')

  expect(container.querySelector('.sheet-backdrop')).toBeNull()
  expect(document.body.querySelector('.sheet-backdrop')).not.toBeNull()
})

test('点面板本身不会误关', async () => {
  render(<Harness />)
  await userEvent.click(screen.getByLabelText('换造型，当前 🐷'))
  await userEvent.click(await screen.findByText('挑个造型'))
  expect(screen.getByTestId('emoji-sheet')).toBeInTheDocument()
})

test('Esc 关掉', async () => {
  render(<Harness />)
  await userEvent.click(screen.getByLabelText('换造型，当前 🐷'))
  await screen.findByTestId('emoji-sheet')

  await userEvent.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByTestId('emoji-sheet')).not.toBeInTheDocument())
})

test('关掉之后焦点回到分身上，键盘用户不会掉进虚空', async () => {
  render(<Harness />)
  const trigger = screen.getByLabelText('换造型，当前 🐷')
  await userEvent.click(trigger)
  await userEvent.click(await screen.findByRole('button', { name: '关闭' }))
  await waitFor(() => expect(trigger).toHaveFocus())
})

test('抽屉是个 modal dialog，读屏能认出来', async () => {
  render(<Harness />)
  await userEvent.click(screen.getByLabelText('换造型，当前 🐷'))
  const sheet = await screen.findByRole('dialog', { name: '挑个造型' })
  expect(sheet).toHaveAttribute('aria-modal', 'true')
})
