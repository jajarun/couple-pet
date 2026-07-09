import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { StatDashboard } from './StatDashboard'
import { ActionBar } from './ActionBar'
import { DailyCard } from './DailyCard'
import { PetSprite } from '../components/PetSprite'
import { SpeechBubble } from '../components/SpeechBubble'
import { LoadingBanter } from '../components/LoadingBanter'
import { useAction } from '../hooks/useAction'
import { useIdempotencyKey } from '../hooks/useIdempotencyKey'
import { usePetAvatar } from '../hooks/useAvatar'
import { statsKey, useFeed } from '../hooks/useFeed'
import { GameEvent, Stats } from '../api/types'

const GRIEVANCE_ALARM = 80
const DEFAULT_STATS: Stats = { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 }

function reactionText(events: GameEvent[]): string {
  return events.find((e) => e.kind === 'ai_reaction')?.content ?? '（分身没接话，装死中…）'
}
function comfortText(events: GameEvent[]): string | null {
  return events.find((e) => e.kind === 'system')?.content ?? null
}

export function HomeScreen({ coupleId, partnerId }: { coupleId: number; partnerId?: number }) {
  const pet = usePetAvatar(true)
  const action = useAction(coupleId)
  const feed = useFeed(coupleId)
  const key = useIdempotencyKey()
  const [reaction, setReaction] = useState<string | null>(null)
  const [bubble, setBubble] = useState<{ text: string; typing: boolean } | null>(null)
  const [comfort, setComfort] = useState<string | null>(null)

  // When TA's avatar nudges us (a new nudge event lands in the feed), pop it into
  // the pet's speech bubble. Baseline the existing nudges on first load so only
  // ones that arrive during this session pop.
  const events = feed.data?.events ?? []
  const latestNudgeId = events.reduce(
    (m, e) =>
      e.kind === 'ai_reaction' && e.action_type === 'nudge' && e.actor_user_id === partnerId && e.id > m
        ? e.id
        : m,
    0,
  )
  const nudgeBaseline = useRef<number | null>(null)
  useEffect(() => {
    if (!feed.data) return
    if (nudgeBaseline.current === null) {
      nudgeBaseline.current = latestNudgeId
      return
    }
    if (latestNudgeId > nudgeBaseline.current && !action.isPending) {
      nudgeBaseline.current = latestNudgeId
      const ev = events.find((e) => e.id === latestNudgeId)
      if (ev) {
        setComfort(null)
        setReaction('nudge')
        setBubble({ text: ev.content, typing: true })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feed.data, latestNudgeId, action.isPending])

  // Read-only mirror of the stats useFeed/useAction write; drives the aura's mood.
  const { data: stats } = useQuery<Stats>({
    queryKey: statsKey(coupleId),
    queryFn: () => DEFAULT_STATS,
    enabled: false,
  })
  const grievanceAlarm = (stats?.grievance ?? DEFAULT_STATS.grievance) >= GRIEVANCE_ALARM

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
      <div className="pad">
        <LoadingBanter />
      </div>
    )
  if (!petCaptured)
    return (
      <div className="pad center stack" style={{ gap: 10, marginTop: 'auto', marginBottom: 'auto' }}>
        <div style={{ fontSize: 56 }}>🥚</div>
        <p>对方分身孵化中…</p>
        <p className="muted tiny">催 TA 一下：「快去捏你自己啊！」</p>
        <LoadingBanter />
      </div>
    )

  return (
    <div className="screenview">
      <div className="screenview-body pad stack" style={{ gap: 14 }}>
        <DailyCard coupleId={coupleId} />
        <StatDashboard coupleId={coupleId} />

        <div className="pet-stage">
          <div className={`aura${grievanceAlarm ? ' alarm' : ''}`} />
          <button
            type="button"
            className="pet-tap"
            onClick={() => fire('poke')}
            disabled={action.isPending}
            aria-label={`戳一戳 ${pet.data?.name || 'TA 的分身'}`}
          >
            <PetSprite face={face} reaction={action.isPending ? null : reaction} />
          </button>
          <div className="pet-name">{pet.data?.name || 'TA 的分身'}</div>
        </div>

        <div className="center" style={{ minHeight: 46, display: 'grid', placeItems: 'center' }}>
          {action.isPending ? (
            <LoadingBanter />
          ) : bubble ? (
            <SpeechBubble text={bubble.text} typing={bubble.typing} fromPet />
          ) : null}
        </div>

        {comfort && (
          <div role="status" className="center" style={{ color: 'var(--warn)' }}>
            {comfort}
          </div>
        )}
      </div>

      <div className="screenview-dock">
        <ActionBar onAction={fire} disabled={action.isPending} />
      </div>
    </div>
  )
}
