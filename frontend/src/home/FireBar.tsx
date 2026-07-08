import { StreakView } from '../api/types'

export function FireBar({ streak }: { streak: StreakView }) {
  const { count, at_risk, i_did_today, partner_did_today } = streak
  let hint = ''
  if (at_risk && !i_did_today) hint = '快断了!今天还没露面'
  else if (at_risk && i_did_today && !partner_did_today) hint = '今天你搞定了,就等 TA'
  return (
    <div className={`fire-bar${at_risk ? ' at-risk' : ''}`} role="status">
      <span className="fire-emoji" aria-hidden>🔥</span>
      <b>{count} 天</b>
      {hint && <span className="fire-hint">· {hint}</span>}
    </div>
  )
}
