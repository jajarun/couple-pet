// 分身造型的 emoji 清单：捏分身时选一个，之后在「⚙️我」里还能换。
// 两处共用 `components/EmojiPicker.tsx`，否则设置页会挑出一个创建页没有的造型。
// 分组只影响选择面板的排版——28 个挤成一坨没法扫，切成四段就好找了。
export const AVATAR_EMOJI_GROUPS = [
  { label: '动物', emojis: ['🐷', '🐶', '🐱', '🐰', '🦊', '🐼', '🐸', '🐲'] },
  { label: '人物', emojis: ['👦', '👧', '🧑', '👶', '🤴', '👸'] },
  { label: '角色', emojis: ['🧙', '🧚', '🥷', '🦸', '🦹', '🤠'] },
  { label: '其它', emojis: ['👾', '🦖', '🤖', '👽', '👻', '🎃', '🤡', '😎'] },
]

/** 拍平的一份，给「取默认值」这类不关心分组的地方用。 */
export const AVATAR_EMOJIS = AVATAR_EMOJI_GROUPS.flatMap((g) => g.emojis)

// 老数据的 appearance 里可能压根没有 emoji（早期建的分身），拿它顶上
export const FALLBACK_AVATAR_EMOJI = '👾'
