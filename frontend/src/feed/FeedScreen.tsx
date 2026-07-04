import { useState } from 'react'
import { useFeed } from '../hooks/useFeed'
import { useRespond } from '../hooks/useRespond'
import { useIdempotencyKey } from '../hooks/useIdempotencyKey'
import { EventItem } from './EventItem'
import { LoadingBanter } from '../components/LoadingBanter'
import { GameEvent } from '../api/types'

export function FeedScreen({ coupleId, myUserId, partnerId }: { coupleId: number; myUserId: number; partnerId: number }) {
  const feed = useFeed(coupleId)
  const respond = useRespond(coupleId)
  const key = useIdempotencyKey()
  const [openFor, setOpenFor] = useState<number | null>(null)
  const [text, setText] = useState('')

  const events = feed.data?.events ?? []
  const hasResponse = (actionId: number) =>
    events.some((e) => e.kind === 'real_response' && e.parent_event_id === actionId)

  if (feed.isLoading)
    return (
      <div style={{ padding: 16 }}>
        <LoadingBanter />
      </div>
    )
  if (events.length === 0)
    return <div style={{ padding: 16, textAlign: 'center' }}>还没有故事，去戳戳 TA 吧~</div>

  const submit = (actionId: number) => {
    respond.mutate(
      { eventId: actionId, content: text, client_key: key.next() },
      { onSuccess: () => { setOpenFor(null); setText(''); key.clear() } },
    )
  }

  return (
    <div style={{ padding: 8, display: 'grid', gap: 8 }}>
      {events.map((ev: GameEvent) => {
        const canRespond = ev.kind === 'action' && ev.actor_user_id === partnerId && !hasResponse(ev.id)
        return (
          <div key={ev.id} className="screen" style={{ padding: 8 }}>
            <EventItem ev={ev} mine={ev.actor_user_id === myUserId} />
            {canRespond && openFor !== ev.id && (
              <button onClick={() => setOpenFor(ev.id)} style={{ marginTop: 6 }}>👤 本尊附身回应</button>
            )}
            {canRespond && openFor === ev.id && (
              <div style={{ display: 'grid', gap: 6, marginTop: 6 }}>
                <input aria-label="回应内容" value={text} onChange={(e) => setText(e.target.value)} placeholder="亲自回怼/服软…" />
                <button onClick={() => submit(ev.id)} disabled={respond.isPending}>发送</button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
