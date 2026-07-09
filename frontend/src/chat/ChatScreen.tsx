import { type KeyboardEvent, useLayoutEffect, useRef, useState } from 'react'
import { useFeed, useLoadOlder } from '../hooks/useFeed'
import { useAction } from '../hooks/useAction'
import { useIdempotencyKey } from '../hooks/useIdempotencyKey'
import { LoadingBanter } from '../components/LoadingBanter'
import { useAutoScrollBottom } from '../hooks/useAutoScrollBottom'
import { PaperPlaneIcon } from '../components/icons'
import { EmojiPicker } from './EmojiPicker'
import { GameEvent } from '../api/types'
import { Gender } from '../theme'

// Verb templates: {o} = the person on the receiving end (the non-actor).
const ACTION_VERB: Record<string, (o: string) => string> = {
  scold: (o) => `骂了${o}`,
  poke: (o) => `戳了${o}`,
  feed_dogfood: () => '喂了狗粮',
  hug: (o) => `抱了${o}`,
  miss_you: (o) => `说想${o}`,
  apologize: () => '道了歉',
  chat: (o) => `找${o}唠`,
}

function genderClass(g?: Gender | null): string {
  return g === 'male' ? 'g-male' : g === 'female' ? 'g-female' : 'g-neutral'
}

export function ChatScreen({
  coupleId,
  myUserId,
  partnerId,
  myGender,
  partnerGender,
}: {
  coupleId: number
  myUserId: number
  partnerId?: number
  myGender?: Gender | null
  partnerGender?: Gender | null
}) {
  const feed = useFeed(coupleId)
  const action = useAction(coupleId)
  const key = useIdempotencyKey()
  const [text, setText] = useState('')
  const [sendErr, setSendErr] = useState('')

  const events = feed.data?.events ?? []
  const endRef = useAutoScrollBottom(events.length, action.isPending)
  const byId = new Map(events.map((e) => [e.id, e]))

  // daily_qa：答案子事件按父题 id 归组，父题出卡时并入渲染
  const qaChildren = new Map<number, GameEvent[]>()
  for (const e of events) {
    if (e.kind === 'daily_qa' && e.parent_event_id != null) {
      const arr = qaChildren.get(e.parent_event_id) ?? []
      arr.push(e)
      qaChildren.set(e.parent_event_id, arr)
    }
  }

  // 向上滑动懒加载更早的消息
  const { loadOlder, loadingOlder } = useLoadOlder(coupleId)
  const hasMore = feed.data?.hasMore ?? false
  const oldestLoaded = feed.data?.oldestLoaded ?? 0
  const bodyRef = useRef<HTMLDivElement>(null)
  const pendingPrepend = useRef<{ prevHeight: number; prevTop: number } | null>(null)

  const onScroll = () => {
    const el = bodyRef.current
    if (!el || loadingOlder || !hasMore) return
    if (el.scrollTop < 80) {
      pendingPrepend.current = { prevHeight: el.scrollHeight, prevTop: el.scrollTop }
      loadOlder()
    }
  }

  // 前插历史后，把视口锚回原来的位置，避免内容"跳走"
  useLayoutEffect(() => {
    const el = bodyRef.current
    if (el && pendingPrepend.current) {
      el.scrollTop = pendingPrepend.current.prevTop + (el.scrollHeight - pendingPrepend.current.prevHeight)
      pendingPrepend.current = null
    }
  }, [oldestLoaded])

  const send = () => {
    if (action.isPending || !text.trim()) return
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

  // 回车发送。中文输入法敲回车是「确认候选词」，那一下绝不能当发送——
  // 靠原生事件的 isComposing 判定（React 合成事件上没有这个字段），
  // 老安卓输入法不给 isComposing、只给 keyCode 229，一并挡掉。
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter') return
    if (e.nativeEvent.isComposing || e.keyCode === 229) return
    e.preventDefault()
    send()
  }

  const inputRef = useRef<HTMLInputElement>(null)

  // 表情插在光标处（不是傻追加到末尾），插完把光标落到表情后面，接着打字不跳走
  const insertEmoji = (emoji: string) => {
    const el = inputRef.current
    if (!el) {
      setText((t) => t + emoji)
      return
    }
    const start = el.selectionStart ?? text.length
    const end = el.selectionEnd ?? text.length
    setText(text.slice(0, start) + emoji + text.slice(end))
    requestAnimationFrame(() => {
      el.focus()
      const caret = start + emoji.length
      el.setSelectionRange(caret, caret)
    })
  }

  const bubble = (side: 'left' | 'right', variant: 'real' | 'ai', g: string, content: string, label?: string) => (
    <div className={`msg-row ${side}`}>
      <div className={`bubble ${variant} ${g}`}>
        {label && <span className="who">{label}</span>}
        {content}
      </div>
    </div>
  )

  const renderEvent = (ev: GameEvent) => {
    if (ev.kind === 'daily_qa') {
      if (ev.parent_event_id != null) return null // 子答案并入父卡渲染
      const answers = qaChildren.get(ev.id) ?? []
      return (
        <div key={ev.id} className="qa-card">
          <div className="qa-title">📮 今日一问</div>
          <div className="qa-q">{ev.content}</div>
          {answers.map((a) => (
            <div key={a.id} className={`qa-a ${a.actor_user_id === myUserId ? 'mine' : 'partner'}`}>
              {a.content}
            </div>
          ))}
        </div>
      )
    }

    if (ev.kind === 'system')
      return (
        <div key={ev.id} className="tip warn" role="note">
          <span>{ev.content}</span>
        </div>
      )

    // 分身主动撩你（nudge）：只显示冲着「我」来的那条（actor = 说话分身的 subject = TA）
    if (ev.kind === 'ai_reaction' && ev.action_type === 'nudge') {
      if (partnerId != null && ev.actor_user_id !== partnerId) return null
      return <div key={ev.id}>{bubble('left', 'ai', genderClass(partnerGender), ev.content, '🤖 分身')}</div>
    }

    if (ev.kind === 'ai_reaction') {
      const parent = ev.parent_event_id != null ? byId.get(ev.parent_event_id) : undefined
      const parentMine = parent?.actor_user_id === myUserId
      return (
        <div key={ev.id}>
          {bubble(parentMine ? 'left' : 'right', 'ai', genderClass(parentMine ? partnerGender : myGender), ev.content, '🤖 分身')}
        </div>
      )
    }

    if (ev.kind === 'real_response') {
      const mine = ev.actor_user_id === myUserId
      return (
        <div key={ev.id}>
          {bubble(mine ? 'right' : 'left', 'real', genderClass(mine ? myGender : partnerGender), ev.content, mine ? '💗 本尊（你）' : '💗 本尊')}
        </div>
      )
    }

    // kind === 'action'
    const mine = ev.actor_user_id === myUserId
    if (ev.action_type === 'chat')
      return (
        <div key={ev.id}>
          {bubble(mine ? 'right' : 'left', 'real', genderClass(mine ? myGender : partnerGender), ev.content)}
        </div>
      )

    // non-chat action → inline tip
    const who = mine ? '你' : 'TA'
    const other = mine ? 'TA' : '你'
    const make = ev.action_type ? ACTION_VERB[ev.action_type] : undefined
    const verb = make ? make(other) : '做了个动作'
    return (
      <div key={ev.id} className="tip">
        <span>
          {who}
          {verb}
          {ev.content ? `：「${ev.content}」` : ''}
        </span>
      </div>
    )
  }

  return (
    <div className="screenview">
      <div className="screenview-body pad" ref={bodyRef} onScroll={onScroll}>
        <div className="chat-log">
          {loadingOlder && (
            <div className="tip">
              <span>加载更早的消息…</span>
            </div>
          )}
          {events.length === 0 && (
            <div className="tip">
              <span>还没有故事～去「TA」那边戳戳，或在下面唠两句</span>
            </div>
          )}
          {events.map(renderEvent)}
          {action.isPending && <LoadingBanter />}
          <div ref={endRef} />
        </div>
      </div>
      <div className="screenview-dock stack" style={{ gap: 8 }}>
        {sendErr && <div role="alert" style={{ color: 'var(--warn)' }}>{sendErr}</div>}
        <div className="chat-bar">
          <div className="chat-field">
            <input
              ref={inputRef}
              aria-label="聊天输入"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={onKeyDown}
              enterKeyHint="send"
              placeholder="随便唠两句…"
            />
            <EmojiPicker onPick={insertEmoji} disabled={action.isPending} />
          </div>
          <button
            className="btn-primary chat-send"
            onClick={send}
            disabled={action.isPending || !text.trim()}
            aria-label="发送"
          >
            <PaperPlaneIcon />
          </button>
        </div>
      </div>
    </div>
  )
}
