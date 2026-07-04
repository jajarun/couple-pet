import { FormEvent, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createCouple, joinCouple } from '../api/couples'
import { CoupleState } from '../api/types'
import { ApiError } from '../api/client'
import { LoadingBanter } from '../components/LoadingBanter'

export function PairScreen({ couple }: { couple: CoupleState }) {
  const qc = useQueryClient()
  const [code, setCode] = useState('')
  const [err, setErr] = useState('')

  const create = useMutation({
    mutationFn: createCouple,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['couple'] }),
  })
  const join = useMutation({
    mutationFn: (c: string) => joinCouple(c),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['couple'] }),
    onError: (e) => {
      if (e instanceof ApiError && e.status === 404) setErr('邀请码不对或失效啦')
      else if (e instanceof ApiError && e.status === 400) setErr('不能跟自己配对呀')
      else if (e instanceof ApiError && e.status === 409) setErr('这对已经凑齐啦')
      else setErr('配对出了点岔子，再试一次~')
    },
  })

  if (couple.status === 'pending') {
    return (
      <div className="pad stack center" style={{ gap: 14, marginTop: 'auto', marginBottom: 'auto' }}>
        <div className="brand-mark">📮</div>
        <h2>等对方进门…</h2>
        <p className="muted tiny">把邀请码发给 TA</p>
        <div className="card center" style={{ padding: '18px 12px' }}>
          <div
            data-testid="pair-code"
            style={{ fontSize: 34, fontWeight: 800, letterSpacing: 6, color: 'var(--primary-strong)' }}
          >
            {couple.pair_code}
          </div>
        </div>
        <p className="tiny">催 TA 一下 👉「就等你了，快输码！」</p>
        <LoadingBanter />
      </div>
    )
  }

  const submitJoin = (e: FormEvent) => {
    e.preventDefault()
    setErr('')
    join.mutate(code.trim().toUpperCase())
  }

  return (
    <div className="pad stack" style={{ gap: 16, marginTop: 'auto', marginBottom: 'auto' }}>
      <div className="center stack" style={{ gap: 8 }}>
        <div className="brand-mark">💑</div>
        <h2>开一段关系</h2>
        <p className="muted tiny">和 TA 凑成一对，才能养起分身</p>
      </div>

      <div className="card stack">
        <button
          className="btn-primary btn-lg btn-block"
          onClick={() => create.mutate()}
          disabled={create.isPending}
        >
          创建情侣，拿邀请码
        </button>
      </div>

      <div className="center muted tiny">— 或者 —</div>

      <form onSubmit={submitJoin} className="card stack">
        <input aria-label="邀请码" value={code} onChange={(e) => setCode(e.target.value)} placeholder="输入对方邀请码" />
        {err && <div role="alert" style={{ color: 'var(--warn)' }}>{err}</div>}
        <button type="submit" className="btn-block" disabled={join.isPending}>加入</button>
      </form>
    </div>
  )
}
