import { Avatar, EvolutionView } from './api/types'
import { FALLBACK_AVATAR_EMOJI } from './avatarOptions'

// 老分身（早期建的）/ 老缓存里可能没有 evolution：当一颗蛋看
export const EGG: EvolutionView = {
  stage: 0,
  branch: '',
  exp: 0,
  next_exp: 10,
  progress: 0,
  emoji: '🥚',
  title: '一颗蛋',
  use_form_emoji: false,
}

export function evolutionOf(avatar?: Avatar): EvolutionView {
  return avatar?.evolution ?? EGG
}

/**
 * 蛋/幼体阶段用用户捏分身时选的 emoji（那是他的所有权表达），
 * 成体起才让进化形态抢过来——这时形态才有辨识度。绝不物理覆盖 appearance.emoji。
 */
export function faceOf(avatar?: Avatar): string {
  const evo = evolutionOf(avatar)
  if (evo.use_form_emoji) return evo.emoji
  return (avatar?.appearance?.emoji as string) ?? FALLBACK_AVATAR_EMOJI
}
