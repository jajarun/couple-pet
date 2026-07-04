import { GameEvent } from '../api/types'

const ACTION_LABEL: Record<string, string> = {
  scold: '骂了你', poke: '戳了你', feed_dogfood: '喂了狗粮', hug: '抱了你',
  miss_you: '说想你', apologize: '道了歉', chat: '找你唠',
}

export function EventItem({ ev, mine }: { ev: GameEvent; mine: boolean }) {
  if (ev.kind === 'ai_reaction') return <div style={{ opacity: 0.9 }}>🤖 {ev.content}</div>
  if (ev.kind === 'system')
    return (
      <div role="note" style={{ color: 'var(--warn)' }}>
        {ev.content}
      </div>
    )
  if (ev.kind === 'real_response')
    return (
      <div style={{ border: '2px solid var(--accent)', borderRadius: 8, padding: 6, background: '#ffffff22', fontWeight: 'bold' }}>
        <span aria-label="本尊回应">👤 本尊回应</span>：<span>{ev.content}</span>
      </div>
    )
  const who = mine ? '你' : 'TA'
  const label = ev.action_type ? ACTION_LABEL[ev.action_type] ?? '做了个动作' : '做了个动作'
  return (
    <div>
      {who}
      {label}
      {ev.content ? `：「${ev.content}」` : ''}
    </div>
  )
}
