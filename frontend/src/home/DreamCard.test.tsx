import { render, screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import { DreamCard } from './DreamCard'

test('有梦话就显示出来', () => {
  render(<DreamCard dream={{ content: '（睡梦中嘟囔）不许…不许再喂了…好撑…', at: '2026-07-09T00:00:00Z' }} />)
  expect(screen.getByText('🌙 昨夜梦话')).toBeInTheDocument()
  expect(screen.getByText(/不许再喂了/)).toBeInTheDocument()
})

test('今天还没做梦就不占地方', () => {
  const { container } = render(<DreamCard dream={null} />)
  expect(container).toBeEmptyDOMElement()
})

test('老接口没这个字段也不炸', () => {
  const { container } = render(<DreamCard />)
  expect(container).toBeEmptyDOMElement()
})
