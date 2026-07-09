import { motion } from 'framer-motion'

/**
 * 「代表我」的那只分身（养在 TA 那儿）被 TA 骂跑了。
 * TA 只能哄——回不回去是我说了算，所以点头的按钮长在我的首页上。
 *
 * pending=false 时 TA 还没来哄：只挂个牌子，不给按钮。
 */
export function ForgiveCard({
  name,
  note,
  pending,
  onForgive,
  busy,
}: {
  name: string
  note?: string | null
  pending: boolean
  onForgive: () => void
  busy: boolean
}) {
  return (
    <motion.div
      className="forgive-card"
      data-testid="forgive-card"
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="forgive-title">🪹 TA 把「{name || '你'}」气跑了</div>
      <p className="tiny muted">TA 一小时里骂了五次，那只代表你的分身留下纸条就走了。</p>
      {note && <p className="runaway-note-text">{note}</p>}
      {pending ? (
        <>
          <p className="tiny">TA 正在门口哄。回不回去，你说了算。</p>
          <button className="btn-primary btn-block" onClick={onForgive} disabled={busy}>
            {busy ? '正在回家…' : '💌 原谅 TA'}
          </button>
        </>
      ) : (
        <p className="tiny muted">TA 还没来哄呢。晾着。</p>
      )}
    </motion.div>
  )
}
