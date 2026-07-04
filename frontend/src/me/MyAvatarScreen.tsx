import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useMyAvatar } from '../hooks/useAvatar'
import { updateMyAvatar } from '../api/avatars'

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

      <button className="btn-ghost" onClick={onLogout} style={{ marginTop: 8 }}>退出登录</button>
    </div>
  )
}
