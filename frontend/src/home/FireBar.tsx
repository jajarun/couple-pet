import { useState } from 'react'
import { useDaily } from '../hooks/useDaily'

export function FireBar({ coupleId }: { coupleId: number }) {
  const { data, rescue, isRescuing } = useDaily(coupleId)
  const [err, setErr] = useState('')
  if (!data) return null

  const { count, at_risk, i_did_today, partner_did_today, rescuable } = data.streak
  let hint = ''
  if (rescuable) hint = '断了 1 天 · 还能救回来!'
  else if (at_risk && !i_did_today) hint = '快断了!今天还没露面'
  else if (at_risk && i_did_today && !partner_did_today) hint = '今天你搞定了,就等 TA'

  return (
    <div className={`fire-bar${at_risk ? ' at-risk' : ''}`} role="status">
      <span className="fire-emoji" aria-hidden>🔥</span>
      <b>{count} 天</b>
      {hint && <span className="fire-hint">· {hint}</span>}
      {rescuable && (
        <button
          type="button"
          className="fire-rescue"
          disabled={isRescuing}
          onClick={() => {
            setErr('')
            rescue().catch(() => setErr('（没续上,喝口水再试~）'))
          }}
        >
          {isRescuing ? '续火中…' : '🔥 花亲密续火'}
        </button>
      )}
      {err && <span className="fire-hint" role="alert">{err}</span>}
    </div>
  )
}
