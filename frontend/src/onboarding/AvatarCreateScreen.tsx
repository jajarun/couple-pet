import { FormEvent, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { updateMyAvatar } from '../api/avatars'

const TONES = ['毒舌', '憨憨', '舔狗', '高冷', '中二']
const EMOJIS = ['🐷', '🐶', '🐱', '🐹', '👾', '🦖']

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
    <form onSubmit={submit} style={{ padding: 16, display: 'grid', gap: 12 }}>
      <h2>捏一个「对方眼里的你」</h2>
      <div>
        基调：
        <div role="radiogroup" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {TONES.map((t) => (
            <button
              type="button" key={t} role="radio" aria-checked={t === tone} onClick={() => setTone(t)}
              style={{ background: t === tone ? 'var(--accent)' : 'var(--panel)', color: 'var(--ink)', border: '2px solid #101010', borderRadius: 6, padding: '6px 10px' }}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      <input aria-label="名字" value={name} onChange={(e) => setName(e.target.value)} placeholder="给它起个名" />
      <div>
        造型：
        <div style={{ display: 'flex', gap: 6 }}>
          {EMOJIS.map((em) => (
            <button
              type="button" key={em} aria-label={`emoji-${em}`} aria-pressed={em === emoji} onClick={() => setEmoji(em)}
              style={{ fontSize: 24, background: em === emoji ? 'var(--accent)' : 'transparent', border: '2px solid #101010', borderRadius: 6 }}
            >
              {em}
            </button>
          ))}
        </div>
      </div>
      <textarea aria-label="种子设定" value={seed} onChange={(e) => setSeed(e.target.value)} placeholder="一句话形容对方眼里的你（AI 之后会扩写）" rows={3} />
      <button type="submit" disabled={save.isPending || !name.trim()}>就它了</button>
    </form>
  )
}
