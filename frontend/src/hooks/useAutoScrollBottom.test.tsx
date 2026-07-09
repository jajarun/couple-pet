import { render } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { useAutoScrollBottom } from './useAutoScrollBottom'

// jsdom 没有 scrollIntoView，hook 会直接 return——补上桩才测得到
let scrollIntoView: ReturnType<typeof vi.fn>
beforeEach(() => {
  scrollIntoView = vi.fn()
  Element.prototype.scrollIntoView = scrollIntoView as unknown as Element['scrollIntoView']
})
afterEach(() => vi.restoreAllMocks())

/** 把哨兵 ref 挂到真 DOM 节点上，跟 ChatScreen 里的用法一致 */
function Harness({ c, p }: { c: number; p: boolean }) {
  const endRef = useAutoScrollBottom(c, p)
  return <div ref={endRef} />
}

test('首次有内容时落到底部', () => {
  render(<Harness c={1} p={false} />)
  expect(scrollIntoView).toHaveBeenCalledTimes(1)
})

test('发送完最后一条也要滚——即使 count 只涨 1 且 pending 同时落下', () => {
  // 这正是「分身回复」关掉后的时序：bundle 只回一条 action 事件。
  // 旧写法把两个信号加成一个数(count + pending)，N+1 → N+1 撞值，effect 不重跑。
  const { rerender } = render(<Harness c={3} p={false} />)
  expect(scrollIntoView).toHaveBeenCalledTimes(1) // 首次落地

  rerender(<Harness c={3} p={true} />) // 点了发送，底部挂出「加载中」
  expect(scrollIntoView).toHaveBeenCalledTimes(2)

  rerender(<Harness c={4} p={false} />) // 回来了：多 1 条事件，加载中收起
  expect(scrollIntoView).toHaveBeenCalledTimes(3) // ← 回归点：以前这里不滚
})

test('分身接话时多 2 条事件，同样只滚该滚的次数', () => {
  const { rerender } = render(<Harness c={3} p={false} />)
  rerender(<Harness c={3} p={true} />)
  rerender(<Harness c={5} p={false} />) // action + ai_reaction
  expect(scrollIntoView).toHaveBeenCalledTimes(3)
})
