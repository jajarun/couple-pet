import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useMyAvatar } from '../hooks/useAvatar'
import { updateMyAvatar } from '../api/avatars'
import { updateMe } from '../api/auth'
import { meKey, useMe } from '../hooks/useMe'
import { usePush } from '../hooks/usePush'

export function MyAvatarScreen({ onLogout }: { onLogout: () => void }) {
  const mine = useMyAvatar(true)
  const qc = useQueryClient()
  const [name, setName] = useState('')
  useEffect(() => {
    if (mine.data) setName(mine.data.name)
  }, [mine.data])
  const save = useMutation({
    mutationFn: () => updateMyAvatar({ name: name.trim() }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['avatar', 'mine'] }),
  })
  const emoji = (mine.data?.appearance?.emoji as string) ?? '👾'
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
        <button className="btn-primary btn-block" onClick={() => save.mutate()} disabled={save.isPending || !name.trim()}>保存</button>
      </div>

      <AiReplyToggle />
      <PushToggle />

      <button className="btn-ghost" onClick={onLogout} style={{ marginTop: 8 }}>退出登录</button>
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <div className="stack" style={{ gap: 2 }}>
          <strong>分身回复</strong>
          <span className="muted tiny">开着时 TA 的分身自动接你的话；关掉就安静等 TA 本尊回你</span>
        </div>
        <button
          className={enabled ? 'btn-ghost' : 'btn-primary'}
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <div className="stack" style={{ gap: 2 }}>
          <strong>消息推送</strong>
          <span className="muted tiny">TA 撩你 / 火苗快灭时，关着页面也能收到</span>
        </div>
        <button
          className={push.enabled ? 'btn-ghost' : 'btn-primary'}
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
