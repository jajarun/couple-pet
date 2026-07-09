import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence } from 'framer-motion'
import { StatDashboard } from './StatDashboard'
import { ActionBar } from './ActionBar'
import { DailyCard } from './DailyCard'
import { DreamCard } from './DreamCard'
import { EvolutionOverlay } from './EvolutionOverlay'
import { ForgiveCard } from './ForgiveCard'
import { RunawayScreen } from './RunawayScreen'
import { SnugglePair } from './SnugglePair'
import { TogetherBanner } from './TogetherBanner'
import { EvolutionBar } from '../components/EvolutionBar'
import { PetSprite } from '../components/PetSprite'
import { SpeechBubble } from '../components/SpeechBubble'
import { LoadingBanter } from '../components/LoadingBanter'
import { useAction } from '../hooks/useAction'
import { useForgive } from '../hooks/useForgive'
import { useIdempotencyKey } from '../hooks/useIdempotencyKey'
import { myAvatarKey, petAvatarKey, useMyAvatar, usePetAvatar } from '../hooks/useAvatar'
import { statsKey, useFeed } from '../hooks/useFeed'
import { evolutionOf, faceOf } from '../evolution'
import { verbOf } from '../actions'
import { EvolutionView, GameEvent, Stats } from '../api/types'

const GRIEVANCE_ALARM = 80
const DEFAULT_STATS: Stats = { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 }
const POKE_TIP_MS = 3000

// 出走三态的三个标记。它们都可能是**对面**落下的（TA 骂跑了我、TA 来哄了、TA 点了头），
// 所以只能靠时间线轮询发现——见下面那个 effect。
const RUNAWAY_MARKERS = new Set(['runaway', 'coax', 'forgive'])

function reactionText(events: GameEvent[]): string {
  return events.find((e) => e.kind === 'ai_reaction')?.content ?? '（分身没接话，装死中…）'
}
function comfortText(events: GameEvent[]): string | null {
  return events.find((e) => e.kind === 'system')?.content ?? null
}

export function HomeScreen({
  coupleId,
  partnerId,
  together = false,
}: {
  coupleId: number
  partnerId?: number
  together?: boolean
}) {
  const qc = useQueryClient()
  const pet = usePetAvatar(true)
  const mine = useMyAvatar(true) // 「TA 养的那只」：同框时贴贴，被气跑时也得在这儿点头
  const action = useAction(coupleId)
  const forgive = useForgive()
  const feed = useFeed(coupleId)
  const key = useIdempotencyKey()
  const [reaction, setReaction] = useState<string | null>(null)
  const [bubble, setBubble] = useState<{ text: string; typing: boolean } | null>(null)
  const [comfort, setComfort] = useState<string | null>(null)
  const [justEvolved, setJustEvolved] = useState<EvolutionView | null>(null)
  const [pokeTip, setPokeTip] = useState<string | null>(null)
  const clearEvolved = useCallback(() => setJustEvolved(null), [])

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

  // 同框时实时看到对方在戳你：同 nudge 那套 baseline，只是盯的是 TA 发出的 action 事件。
  // 先 baseline 掉已经在时间线上的旧动作，只有本次会话里新到的才抖。
  const latestPartnerActionId = events.reduce(
    (m, e) => (e.kind === 'action' && e.actor_user_id === partnerId && e.id > m ? e.id : m),
    0,
  )
  const partnerActionBaseline = useRef<number | null>(null)
  useEffect(() => {
    if (!feed.data) return
    if (partnerActionBaseline.current === null) {
      partnerActionBaseline.current = latestPartnerActionId
      return
    }
    if (latestPartnerActionId <= partnerActionBaseline.current) return
    partnerActionBaseline.current = latestPartnerActionId
    const ev = events.find((e) => e.id === latestPartnerActionId)
    if (!ev) return
    setPokeTip(`TA 刚${verbOf(ev.action_type, '你')}`)
    const t = setTimeout(() => setPokeTip(null), POKE_TIP_MS)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feed.data, latestPartnerActionId])

  // 出走三态只有服务端知道，而改变它的动作一半来自对面。时间线 3 秒一轮，见到新标记
  // 就把两只分身的状态重取一次——「TA 点头了」于是最多 3 秒就落到我屏幕上。
  const latestMarkerId = events.reduce(
    (m, e) => (RUNAWAY_MARKERS.has(e.action_type ?? '') && e.id > m ? e.id : m),
    0,
  )
  const markerBaseline = useRef<number | null>(null)
  useEffect(() => {
    if (!feed.data) return
    if (markerBaseline.current === null) {
      markerBaseline.current = latestMarkerId // 首屏的状态已经是新取的，别白刷一次
      return
    }
    if (latestMarkerId <= markerBaseline.current) return
    markerBaseline.current = latestMarkerId
    qc.invalidateQueries({ queryKey: petAvatarKey })
    qc.invalidateQueries({ queryKey: myAvatarKey })
  }, [feed.data, latestMarkerId, qc])

  // Read-only mirror of the stats useFeed/useAction write; drives the aura's mood.
  const { data: stats } = useQuery<Stats>({
    queryKey: statsKey(coupleId),
    queryFn: () => DEFAULT_STATS,
    enabled: false,
  })
  const grievanceAlarm = (stats?.grievance ?? DEFAULT_STATS.grievance) >= GRIEVANCE_ALARM

  const petCaptured = pet.data && pet.data.name !== ''
  const evo = evolutionOf(pet.data)
  const face = faceOf(pet.data)

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
          if (bundle.evolved && bundle.evolution) setJustEvolved(bundle.evolution)
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

  // 「代表我」的那只被 TA 骂跑了：点头的按钮只能长在我这边（后端也只认我，见 /runaway/forgive）
  const mineState = mine.data?.runaway_state ?? 'home'
  const forgiveCard =
    mineState === 'home' ? null : (
      <ForgiveCard
        name={mine.data?.name ?? ''}
        note={mine.data?.runaway_note}
        pending={mineState === 'pending'}
        onForgive={() => forgive.mutate()}
        busy={forgive.isPending}
      />
    )

  // 它跑了：整个首页交给空窝，别的动作一个都点不到（后端也拦，见 /actions 的 pet_away）。
  // 两只分身可能同时在外面——所以点头的卡片也得跟着塞进空窝里，否则谁都回不了家。
  if (pet.data?.is_away)
    return (
      <RunawayScreen
        name={pet.data.name}
        note={pet.data.runaway_note}
        pending={pet.data.runaway_state === 'pending'}
        onCoax={() => fire('coax')}
        busy={action.isPending}
      >
        {forgiveCard}
      </RunawayScreen>
    )

  return (
    <div className="screenview">
      <div className="screenview-body pad stack" style={{ gap: 14 }}>
        <AnimatePresence>{together && <TogetherBanner />}</AnimatePresence>
        {forgiveCard}

        <DailyCard coupleId={coupleId} />
        <DreamCard dream={pet.data?.dream} />
        <StatDashboard coupleId={coupleId} />

        <div className="pet-stage">
          <div className={`aura${grievanceAlarm ? ' alarm' : ''}`} />
          {together ? (
            <SnugglePair
              pet={pet.data}
              mine={mine.data}
              reaction={action.isPending ? null : reaction}
              evolving={justEvolved !== null}
              poked={pokeTip !== null}
              onPoke={() => fire('poke')}
              disabled={action.isPending}
            />
          ) : (
            <>
              <button
                type="button"
                className="pet-tap"
                onClick={() => fire('poke')}
                disabled={action.isPending}
                aria-label={`戳一戳 ${pet.data?.name || 'TA 的分身'}`}
              >
                <PetSprite
                  face={face}
                  reaction={action.isPending ? null : reaction}
                  evolving={justEvolved !== null}
                />
              </button>
              <div className="pet-name">{pet.data?.name || 'TA 的分身'}</div>
            </>
          )}
        </div>

        <EvolutionBar evo={evo} />

        <div className="center" style={{ minHeight: 46, display: 'grid', placeItems: 'center' }}>
          {action.isPending ? (
            <LoadingBanter />
          ) : bubble ? (
            <SpeechBubble text={bubble.text} typing={bubble.typing} fromPet />
          ) : null}
        </div>

        {pokeTip && (
          <div role="status" data-testid="poke-tip" className="center poke-tip">
            {pokeTip}
          </div>
        )}

        {comfort && (
          <div role="status" className="center" style={{ color: 'var(--warn)' }}>
            {comfort}
          </div>
        )}
      </div>

      <div className="screenview-dock">
        <ActionBar onAction={fire} disabled={action.isPending} together={together} />
      </div>

      <AnimatePresence>
        {justEvolved && <EvolutionOverlay evo={justEvolved} onDone={clearEvolved} />}
      </AnimatePresence>
    </div>
  )
}
