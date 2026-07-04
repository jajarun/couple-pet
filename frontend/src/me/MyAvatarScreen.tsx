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
    <div style={{ padding: 16, display: 'grid', gap: 12 }}>
      <h2>我的分身（对方眼里的你）</h2>
      <div style={{ fontSize: 48, textAlign: 'center' }}>{emoji}</div>
      <input aria-label="分身名字" value={name} onChange={(e) => setName(e.target.value)} />
      <button onClick={() => save.mutate()} disabled={save.isPending || !name.trim()}>保存</button>
      <button onClick={onLogout} style={{ marginTop: 24 }}>退出登录</button>
    </div>
  )
}
