import { useState } from 'react'
import { useDaily } from '../hooks/useDaily'

export function DailyQuestionCard({ coupleId }: { coupleId: number }) {
  const { data, answer, isAnswering } = useDaily(coupleId)
  const [draft, setDraft] = useState('')
  const [err, setErr] = useState('')
  if (!data) return null

  return (
    <div className="daily-card">
      <div className="daily-title">📮 今日一问</div>
      <div className="daily-q">{data.question.text}</div>
      {err && <div className="daily-err" role="alert">{err}</div>}

      {data.both_answered ? (
        <div className="daily-reveal stack" style={{ gap: 6 }}>
          <div className="daily-ans mine"><b>你:</b> {data.my_answer}</div>
          <div className="daily-ans partner"><b>TA:</b> {data.partner_answer}</div>
        </div>
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
