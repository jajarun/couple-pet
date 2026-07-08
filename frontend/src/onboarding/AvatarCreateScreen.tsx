import { FormEvent, CSSProperties, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { updateMyAvatar } from '../api/avatars'

const TONES = [
  '毒舌', '傲娇', '憨憨', '沙雕', '舔狗', '高冷', '中二', '温柔',
  '粘人', '闷骚', '撒娇', '腹黑', '话痨', '佛系', '醋精', '社恐',
]
const EMOJIS = [
  '🐷', '🐶', '🐱', '🐰', '🦊', '🐼', '🐸', '🐲', // 动物
  '👦', '👧', '🧑', '👶', '🤴', '👸', // 人物
  '🧙', '🧚', '🥷', '🦸', '🦹', '🤠', // 角色
  '👾', '🦖', '🤖', '👽', '👻', '🎃', '🤡', '😎', // 其它
]
const MAX_TONES = 3 // 基调多选上限，选太多 AI 人设会变杂

const chip = (active: boolean): CSSProperties => ({
  minHeight: 42,
  padding: '8px 14px',
  borderRadius: 999,
  fontWeight: 700,
  border: active ? '2px solid var(--primary)' : '1px solid var(--line)',
  background: active ? 'var(--primary-soft)' : 'var(--surface)',
  color: active ? 'var(--primary-strong)' : 'var(--ink-2)',
})

const emojiChip = (active: boolean): CSSProperties => ({
  fontSize: 26,
  minHeight: 52,
  minWidth: 52,
  borderRadius: 16,
  border: active ? '2px solid var(--primary)' : '1px solid var(--line)',
  background: active ? 'var(--primary-soft)' : 'var(--surface)',
})

export function AvatarCreateScreen() {
  const qc = useQueryClient()
  const [tones, setTones] = useState<string[]>([TONES[0]])
  const [name, setName] = useState('')
  const [emoji, setEmoji] = useState(EMOJIS[0])
  const [seed, setSeed] = useState('')

  // 点已选的 → 移除（但保留至少 1 个）；点未选的 → 未满 3 个才加
  const toggleTone = (t: string) =>
    setTones((prev) => {
      if (prev.includes(t)) return prev.length > 1 ? prev.filter((x) => x !== t) : prev
      return prev.length < MAX_TONES ? [...prev, t] : prev
    })

  const save = useMutation({
    mutationFn: () =>
      updateMyAvatar({ name: name.trim(), appearance: { emoji, tone: tones }, persona: { tone: tones, seed } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['avatar', 'mine'] }),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    save.mutate()
  }

  return (
    <form onSubmit={submit} className="pad stack" style={{ gap: 16 }}>
      <div className="stack" style={{ gap: 6 }}>
        <h2>捏一个「对方眼里的你」</h2>
        <p className="muted tiny">这就是 TA 每天要面对的分身</p>
      </div>

      <div className="stack" style={{ gap: 8 }}>
        <span className="tiny muted">基调（最多选 {MAX_TONES} 个）</span>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {TONES.map((t) => {
            const active = tones.includes(t)
            const locked = !active && tones.length >= MAX_TONES
            return (
              <button
                type="button" key={t} role="checkbox" aria-checked={active}
                disabled={locked} onClick={() => toggleTone(t)}
                style={{ ...chip(active), ...(locked ? { opacity: 0.4 } : null) }}
              >
                {t}
              </button>
            )
          })}
        </div>
      </div>

      <input aria-label="名字" value={name} onChange={(e) => setName(e.target.value)} placeholder="给它起个名" />

      <div className="stack" style={{ gap: 8 }}>
        <span className="tiny muted">造型</span>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {EMOJIS.map((em) => (
            <button
              type="button" key={em} aria-label={`emoji-${em}`} aria-pressed={em === emoji} onClick={() => setEmoji(em)}
              style={emojiChip(em === emoji)}
            >
              {em}
            </button>
          ))}
        </div>
      </div>

      <textarea aria-label="种子设定" value={seed} onChange={(e) => setSeed(e.target.value)} placeholder="一句话形容对方眼里的你（AI 之后会扩写）" rows={3} />

      <button type="submit" className="btn-primary btn-lg btn-block" disabled={save.isPending || !name.trim()}>就它了</button>
    </form>
  )
}
