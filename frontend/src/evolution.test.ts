import { test, expect } from 'vitest'
import { Avatar, EvolutionView } from './api/types'
import { EGG, evolutionOf, faceOf } from './evolution'

function avatar(emoji: unknown, evolution?: Partial<EvolutionView>): Avatar {
  return {
    id: 1, couple_id: 1, subject_user_id: 1, keeper_user_id: 2, name: '狗蛋',
    appearance: emoji === undefined ? {} : { emoji },
    persona: {},
    evolution: evolution ? { ...EGG, ...evolution } : undefined,
  }
}

test('老分身没有 evolution 时当一颗蛋看', () => {
  expect(evolutionOf(avatar('🐷'))).toEqual(EGG)
  expect(evolutionOf(undefined)).toEqual(EGG)
})

test('蛋/幼体阶段用用户捏分身时选的 emoji', () => {
  expect(faceOf(avatar('🐷'))).toBe('🐷')
  expect(faceOf(avatar('🐷', { stage: 1, emoji: '🐣' }))).toBe('🐷')
})

test('成体起进化形态才抢过来', () => {
  expect(faceOf(avatar('🐷', { stage: 2, emoji: '😼', use_form_emoji: true }))).toBe('😼')
})

test('老数据连 appearance.emoji 都没有时回落到 👾', () => {
  expect(faceOf(avatar(undefined))).toBe('👾')
  expect(faceOf(undefined)).toBe('👾')
})
