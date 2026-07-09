import { render, screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import { EvolutionView } from '../api/types'
import { EvolutionBar } from './EvolutionBar'

function evo(patch: Partial<EvolutionView> = {}): EvolutionView {
  return {
    stage: 2, branch: 'dark', exp: 60, next_exp: 120, progress: 0.25,
    emoji: '😼', title: '腹黑体', use_form_emoji: true, ...patch,
  }
}

test('显示形态称号、阶段和还差多少经验', () => {
  render(<EvolutionBar evo={evo()} />)
  expect(screen.getByText('腹黑体')).toBeInTheDocument()
  expect(screen.getByText('· 成体')).toBeInTheDocument()
  expect(screen.getByText('60/120')).toBeInTheDocument()
  expect(screen.getByText('再攒 60 点就长大了')).toBeInTheDocument()
})

test('完全体不显示进度数字，改说养到头了', () => {
  render(
    <EvolutionBar
      evo={evo({ stage: 3, exp: 130, next_exp: null, progress: 1, emoji: '😈', title: '黑化完全体' })}
    />,
  )
  expect(screen.getByText('MAX')).toBeInTheDocument()
  expect(screen.getByText(/养到头了/)).toBeInTheDocument()
  expect(screen.queryByText(/再攒/)).not.toBeInTheDocument()
})

test('把阶段挂到 data 属性上，方便样式和断言', () => {
  render(<EvolutionBar evo={evo({ stage: 0, title: '一颗蛋' })} />)
  expect(screen.getByTestId('evo-bar')).toHaveAttribute('data-stage', '0')
})
