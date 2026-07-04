import { useState } from 'react'
import { StatDashboard } from './StatDashboard'
import { ActionBar } from './ActionBar'
import { PetSprite } from '../components/PetSprite'
import { SpeechBubble } from '../components/SpeechBubble'
import { LoadingBanter } from '../components/LoadingBanter'
import { useAction } from '../hooks/useAction'
import { useIdempotencyKey } from '../hooks/useIdempotencyKey'
import { usePetAvatar } from '../hooks/useAvatar'
import { GameEvent } from '../api/types'

function reactionText(events: GameEvent[]): string {
  return events.find((e) => e.kind === 'ai_reaction')?.content ?? '（分身没接话，装死中…）'
}
function comfortText(events: GameEvent[]): string | null {
  return events.find((e) => e.kind === 'system')?.content ?? null
}

export function HomeScreen({ coupleId }: { coupleId: number }) {
  const pet = usePetAvatar(true)
  const action = useAction(coupleId)
  const key = useIdempotencyKey()
  const [reaction, setReaction] = useState<string | null>(null)
  const [bubble, setBubble] = useState<{ text: string; typing: boolean } | null>(null)
  const [comfort, setComfort] = useState<string | null>(null)

  const petCaptured = pet.data && pet.data.name !== ''
  const face = (pet.data?.appearance?.emoji as string) ?? '👾'

  const fire = (type: string) => {
    setComfort(null)
    setReaction(type)
    setBubble(null)
    action.mutate(
      { action_type: type, content: '', client_key: key.next() },
      {
        onSuccess: (bundle) => {
          setBubble({ text: reactionText(bundle.events), typing: true })
          setComfort(comfortText(bundle.events))
          key.clear()
        },
        onError: () => setBubble({ text: '（分身卡壳了，喝口水再战~）', typing: false }),
      },
    )
  }

  if (pet.isLoading)
    return (
      <div style={{ padding: 16 }}>
        <LoadingBanter />
      </div>
    )
  if (!petCaptured)
    return (
      <div style={{ padding: 16, textAlign: 'center' }}>
        <div style={{ fontSize: 48 }}>🥚</div>
        <p>对方分身孵化中…</p>
        <p>催 TA 一下：「快去捏你自己啊！」</p>
        <LoadingBanter />
      </div>
    )

  return (
    <div style={{ padding: 8, display: 'grid', gap: 12 }}>
      <StatDashboard coupleId={coupleId} />
      <div style={{ minHeight: 40, textAlign: 'center' }}>
        {action.isPending ? <LoadingBanter /> : bubble ? <SpeechBubble text={bubble.text} typing={bubble.typing} /> : null}
      </div>
      <div className="screen" style={{ padding: 8 }}>
        <div style={{ textAlign: 'center' }}>{pet.data?.name || 'TA 的分身'}</div>
        <PetSprite face={face} reaction={action.isPending ? null : reaction} />
      </div>
      {comfort && (
        <div role="status" style={{ color: 'var(--warn)', textAlign: 'center' }}>
          {comfort}
        </div>
      )}
      <ActionBar onAction={fire} disabled={action.isPending} />
    </div>
  )
}
