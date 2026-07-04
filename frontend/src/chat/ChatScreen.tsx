import { useState } from 'react'
import { useFeed } from '../hooks/useFeed'
import { useAction } from '../hooks/useAction'
import { useIdempotencyKey } from '../hooks/useIdempotencyKey'
import { SpeechBubble } from '../components/SpeechBubble'
import { LoadingBanter } from '../components/LoadingBanter'
import { GameEvent } from '../api/types'

export function ChatScreen({ coupleId, myUserId }: { coupleId: number; myUserId: number }) {
  const feed = useFeed(coupleId)
  const action = useAction(coupleId)
  const key = useIdempotencyKey()
  const [text, setText] = useState('')
  const [sendErr, setSendErr] = useState('')

  const events = feed.data?.events ?? []
  const chatActionIds = new Set(
    events
      .filter((e) => e.kind === 'action' && e.action_type === 'chat' && e.actor_user_id === myUserId)
      .map((e) => e.id),
  )
  const thread = events.filter(
    (e) =>
      (e.kind === 'action' && e.action_type === 'chat' && e.actor_user_id === myUserId) ||
      (e.kind === 'ai_reaction' && e.parent_event_id != null && chatActionIds.has(e.parent_event_id)),
  )

  const send = () => {
    if (!text.trim()) return
    setSendErr('')
    action.mutate(
      { action_type: 'chat', content: text.trim(), client_key: key.next() },
      {
        onSuccess: () => {
          setText('')
          setSendErr('')
          key.clear()
        },
        onError: () => setSendErr('（消息卡在半路了，分身正在找信号…）'),
      },
    )
  }

  return (
    <div style={{ padding: 8, display: 'grid', gap: 8 }}>
      <div style={{ display: 'grid', gap: 6 }}>
        {thread.map((e: GameEvent) =>
          e.kind === 'action' ? (
            <div key={e.id} style={{ textAlign: 'right' }}>🧑 {e.content}</div>
          ) : (
            <div key={e.id} style={{ textAlign: 'left' }}>
              <SpeechBubble text={e.content} />
            </div>
          ),
        )}
        {action.isPending && <LoadingBanter />}
      </div>
      {sendErr && <div role="alert" style={{ color: 'var(--warn)' }}>{sendErr}</div>}
      <div style={{ display: 'flex', gap: 6 }}>
        <input aria-label="聊天输入" style={{ flex: 1 }} value={text} onChange={(e) => setText(e.target.value)} placeholder="随便唠两句…" />
        <button onClick={send} disabled={action.isPending}>发</button>
      </div>
    </div>
  )
}
