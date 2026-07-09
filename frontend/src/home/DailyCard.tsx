import { useId, useState } from 'react'
import { useDaily } from '../hooks/useDaily'

// 火苗 + 每日一问合成一张卡：火苗从独占一行的药丸缩成标题行右边的 chip。
// 两块本来就共用 useDaily 的同一个缓存，合起来只是少发一次订阅、少占半屏。
export function DailyCard({ coupleId }: { coupleId: number }) {
  const { data, answer, isAnswering, rescue, isRescuing } = useDaily(coupleId)
  const [draft, setDraft] = useState('')
  const [err, setErr] = useState('')
  const [fireErr, setFireErr] = useState('')
  // 答案默认收起，只露题目。不持久化——切走再回来又是收起的，
  // 「默认隐藏」要的就是这个：随手把手机递出去也不会被瞟到答案。
  const [open, setOpen] = useState(false)
  const answersId = useId()
  if (!data) return null

  const { count, at_risk, i_did_today, partner_did_today, rescuable } = data.streak
  let hint = ''
  if (rescuable) hint = '断了 1 天 · 还能救回来!'
  else if (at_risk && !i_did_today) hint = '快断了!今天还没露面'
  else if (at_risk && i_did_today && !partner_did_today) hint = '今天你搞定了,就等 TA'

  return (
    <div className="daily-card">
      <div className="daily-head">
        <div className="daily-title">📮 今日一问</div>
        <span className={`fire-chip${at_risk ? ' at-risk' : ''}`} role="status">
          <span className="fire-emoji" aria-hidden>
            🔥
          </span>
          <b>{count} 天</b>
        </span>
        {/* 没答完就没有答案可藏，折叠键也就不该出现 */}
        {data.both_answered && (
          <button
            type="button"
            className="daily-peek"
            aria-expanded={open}
            aria-controls={answersId}
            onClick={() => setOpen((o) => !o)}
          >
            {open ? '🙈 收起' : '👀 看答案'}
          </button>
        )}
      </div>

      {/* 火苗告急才占这一行，平时它压根不存在 */}
      {hint && (
        <div className="daily-fire">
          <span className="fire-hint">{hint}</span>
          {rescuable && (
            <button
              type="button"
              className="fire-rescue"
              disabled={isRescuing}
              onClick={() => {
                setFireErr('')
                rescue().catch(() => setFireErr('（没续上,喝口水再试~）'))
              }}
            >
              {isRescuing ? '续火中…' : '🔥 花亲密续火'}
            </button>
          )}
        </div>
      )}
      {fireErr && (
        <div className="daily-err" role="alert">
          {fireErr}
        </div>
      )}

      <div className="daily-q">{data.question.text}</div>
      {err && (
        <div className="daily-err" role="alert">
          {err}
        </div>
      )}

      {data.both_answered ? (
        // 条件渲染，不是 CSS 藏起来——藏在 DOM 里等于没藏
        open && (
          <div id={answersId} className="daily-reveal stack" style={{ gap: 6 }}>
            <div className="daily-ans mine">
              <b>你:</b> {data.my_answer}
            </div>
            <div className="daily-ans partner">
              <b>TA:</b> {data.partner_answer}
            </div>
          </div>
        )
      ) : data.my_answer != null ? (
        <div className="daily-waiting">✅ 你答完啦,就等 TA 了…</div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            const t = draft.trim()
            setErr('')
            if (t)
              answer(t)
                .then(() => setDraft(''))
                .catch(() => setErr('（没送出去，喝口水再答一次~）'))
          }}
        >
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="写下你的答案，答完才能看 TA 的~"
            rows={2}
          />
          <button type="submit" disabled={isAnswering || !draft.trim()}>
            {isAnswering ? '发送中…' : '答一个'}
          </button>
        </form>
      )}
    </div>
  )
}
