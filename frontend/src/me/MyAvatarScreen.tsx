import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { myAvatarKey as avatarKey, useMyAvatar } from '../hooks/useAvatar'
import { updateMyAvatar } from '../api/avatars'
import { updateMe } from '../api/auth'
import { AVATAR_EMOJIS, FALLBACK_AVATAR_EMOJI } from '../avatarOptions'
import { EvolutionBar } from '../components/EvolutionBar'
import { evolutionOf, faceOf } from '../evolution'
import { Avatar } from '../api/types'
import { meKey, useMe } from '../hooks/useMe'
import { usePush } from '../hooks/usePush'

export function MyAvatarScreen({ onLogout }: { onLogout: () => void }) {
  const mine = useMyAvatar(true)
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [emoji, setEmoji] = useState(FALLBACK_AVATAR_EMOJI)

  const savedName = mine.data?.name ?? ''
  const savedEmoji = (mine.data?.appearance?.emoji as string) ?? FALLBACK_AVATAR_EMOJI
  useEffect(() => {
    if (!mine.data) return
    setName(savedName)
    setEmoji(savedEmoji)
  }, [mine.data, savedName, savedEmoji])

  const save = useMutation({
    mutationFn: () =>
      updateMyAvatar({
        name: name.trim(),
        // appearance 是整列覆盖的：只塞 emoji 会把捏分身时存进去的 tone 一起冲掉
        appearance: { ...(mine.data?.appearance ?? {}), emoji },
      }),
    // 服务端返回直接回写；invalidate 会重拉一次，中间那一帧还是旧造型
    onSuccess: (av) => qc.setQueryData(avatarKey, av),
  })

  const dirty = name.trim() !== savedName || emoji !== savedEmoji

  return (
    <div className="pad stack" style={{ gap: 16 }}>
      <h2>我的分身</h2>
      <p className="muted tiny">对方眼里的你，长这样</p>

      <div className="card stack center" style={{ gap: 12 }}>
        <div className="pet-stage" style={{ padding: 0 }}>
          <div className="aura" />
          <div className="pet-face" style={{ fontSize: 60 }}>{emoji}</div>
        </div>
        <input aria-label="分身名字" value={name} onChange={(e) => setName(e.target.value)} />

        <div className="stack" style={{ gap: 8 }}>
          <span className="tiny muted">造型</span>
          <div className="emoji-chips">
            {AVATAR_EMOJIS.map((em) => (
              <button
                type="button" key={em} className="emoji-chip"
                aria-label={`emoji-${em}`} aria-pressed={em === emoji} onClick={() => setEmoji(em)}
              >
                {em}
              </button>
            ))}
          </div>
        </div>

        <button
          className="btn-primary btn-block"
          onClick={() => save.mutate()}
          disabled={save.isPending || !name.trim() || !dirty}
        >
          {save.isPending ? '保存中…' : !mine.data || dirty ? '保存' : '已保存'}
        </button>
        {save.isError && (
          <span role="alert" className="tiny" style={{ color: 'var(--primary-strong)' }}>
            没存上，再试一次~
          </span>
        )}
      </div>

      <RaisedByPartner mine={mine.data} />
      <AiReplyToggle />
      <PushToggle />

      <button className="btn-ghost" onClick={onLogout} style={{ marginTop: 8 }}>退出登录</button>
    </div>
  )
}

// 上面那张卡是「你把自己设定成什么样」，这张是「TA 把你养成了什么样」——
// 这只分身归 TA 养，形态完全由 TA 对它做过的动作决定。看着办吧。
function RaisedByPartner({ mine }: { mine?: Avatar }) {
  if (!mine) return null
  const evo = evolutionOf(mine)
  const grown = evo.stage >= 2
  return (
    <div className="card stack" style={{ gap: 10 }}>
      <div className="setting-text">
        <strong>TA 把你养成了什么样</strong>
        <span className="muted tiny">
          {grown ? '性格已经定型了，这是 TA 一次次互动养出来的' : '还在长——TA 还没把你养出个性'}
        </span>
      </div>
      <div className="center" style={{ fontSize: 52, lineHeight: 1.1 }} aria-label={`形态 ${evo.title}`}>
        {faceOf(mine)}
      </div>
      <EvolutionBar evo={evo} />
    </div>
  )
}

// 分身回复开关：关掉后分身不自动接话，把话头留给「本尊回应」。默认关。
function AiReplyToggle() {
  const me = useMe()
  const qc = useQueryClient()
  const toggle = useMutation({
    mutationFn: (next: boolean) => updateMe({ ai_reply_enabled: next }),
    onSuccess: (u) => qc.setQueryData(meKey, u),
  })
  const enabled = me.data?.ai_reply_enabled ?? false
  const busy = me.isLoading || toggle.isPending
  return (
    <div className="card stack" style={{ gap: 8 }}>
      <div className="setting-row">
        <div className="setting-text">
          <strong>分身回复</strong>
          <span className="muted tiny">关掉后分身不接话，等 TA 本尊亲自回你</span>
        </div>
        <button
          className={`setting-toggle ${enabled ? 'btn-ghost' : 'btn-primary'}`}
          onClick={() => toggle.mutate(!enabled)}
          disabled={busy}
        >
          {busy ? '…' : enabled ? '已开启' : '开启'}
        </button>
      </div>
      {toggle.isError && (
        <span role="alert" className="tiny" style={{ color: 'var(--primary-strong)' }}>
          没改成功，再试一次~
        </span>
      )}
    </div>
  )
}

// 消息推送开关：TA 撩你 / 火苗快灭时，关着页面也能收到系统通知
function PushToggle() {
  const push = usePush()
  if (!push.supported) return null
  return (
    <div className="card stack" style={{ gap: 8 }}>
      <div className="setting-row">
        <div className="setting-text">
          <strong>消息推送</strong>
          <span className="muted tiny">TA 撩你 / 火苗快灭时，关着页面也能收到</span>
        </div>
        <button
          className={`setting-toggle ${push.enabled ? 'btn-ghost' : 'btn-primary'}`}
          onClick={() => (push.enabled ? push.turnOff() : push.turnOn())}
          disabled={push.busy}
        >
          {push.busy ? '…' : push.enabled ? '已开启' : '开启'}
        </button>
      </div>
      {push.error && (
        <span role="alert" className="tiny" style={{ color: 'var(--primary-strong)' }}>
          {push.error}
        </span>
      )}
      <span className="muted tiny">iPhone 需先「添加到主屏幕」再开，才能收到推送</span>
    </div>
  )
}
