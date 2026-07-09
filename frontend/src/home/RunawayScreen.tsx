import { ReactNode } from 'react'
import { motion } from 'framer-motion'

/**
 * 分身被你气跑了（1 小时里骂满 5 次）。首页整个换成空窝——它不在，你什么都做不了，只能去哄。
 * 这是全局唯一能发 coax 的地方（正常态的 ActionBar 里没有这个键）。
 *
 * 哄完不等于回家：pending 时按钮变成「等 TA 点头」，钥匙在它代表的那个人手里。
 * children 用来塞对侧的 ForgiveCard——两只分身可能同时跑掉，那时点头的按钮也得在这儿。
 */
export function RunawayScreen({
  name,
  note,
  pending,
  onCoax,
  busy,
  children,
}: {
  name: string
  note?: string | null
  pending: boolean
  onCoax: () => void
  busy: boolean
  children?: ReactNode
}) {
  return (
    <div className="screenview" data-testid="runaway">
      <div className="screenview-body pad stack center" style={{ gap: 16, placeContent: 'center' }}>
        <motion.div
          className="nest"
          animate={{ y: [0, -3, 0] }}
          transition={{ duration: 3.4, repeat: Infinity, ease: 'easeInOut' }}
        >
          🪹
        </motion.div>
        <div>
          <strong>{name || 'TA 的分身'}走了</strong>
          <p className="muted tiny" style={{ marginTop: 4 }}>
            {pending
              ? '你哄了。它站在门口没动——回不回去，得 TA 说了算。'
              : '你一小时里骂了它五次，一句好话都没有。'}
          </p>
        </div>

        {note && (
          <div className="runaway-note">
            <span className="tiny muted">它留了张纸条</span>
            <p className="runaway-note-text">{note}</p>
          </div>
        )}

        {children}
      </div>

      <div className="screenview-dock">
        {pending ? (
          <button className="btn-primary btn-block" disabled data-testid="awaiting-forgiveness">
            🙏 已经哄过了，等 TA 点头…
          </button>
        ) : (
          <button className="btn-primary btn-block" onClick={onCoax} disabled={busy}>
            {busy ? '正在把它哄回来…' : '🥺 去哄它回来'}
          </button>
        )}
      </div>
    </div>
  )
}
