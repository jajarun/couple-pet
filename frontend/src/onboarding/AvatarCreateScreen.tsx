import { FormEvent, CSSProperties, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { updateMyAvatar } from '../api/avatars'

const TONES = ['毒舌', '憨憨', '舔狗', '高冷', '中二']
const EMOJIS = ['🐷', '🐶', '🐱', '🐹', '👾', '🦖']

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
  const [tone, setTone] = useState(TONES[0])
  const [name, setName] = useState('')
  const [emoji, setEmoji] = useState(EMOJIS[0])
  const [seed, setSeed] = useState('')

  const save = useMutation({
    mutationFn: () =>
      updateMyAvatar({ name: name.trim(), appearance: { emoji, tone }, persona: { tone, seed } }),
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
        <span className="tiny muted">基调</span>
        <div role="radiogroup" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {TONES.map((t) => (
            <button
              type="button" key={t} role="radio" aria-checked={t === tone} onClick={() => setTone(t)}
              style={chip(t === tone)}
            >
              {t}
            </button>
          ))}
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
