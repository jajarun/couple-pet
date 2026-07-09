import { motion } from 'framer-motion'

/**
 * 分身被你气跑了。首页整个换成空窝——它不在，你什么都做不了，只能去哄。
 * 这是全局唯一能发 coax 的地方（正常态的 ActionBar 里没有这个键）。
 */
export function RunawayScreen({
  name,
  note,
  onCoax,
  busy,
}: {
  name: string
  note?: string | null
  onCoax: () => void
  busy: boolean
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
            你骂了它一次又一次，一句好话都没有。
          </p>
        </div>

        {note && (
          <div className="runaway-note">
            <span className="tiny muted">它留了张纸条</span>
            <p className="runaway-note-text">{note}</p>
          </div>
        )}
      </div>

      <div className="screenview-dock">
        <button className="btn-primary btn-block" onClick={onCoax} disabled={busy}>
          {busy ? '正在把它哄回来…' : '🥺 去哄它回来'}
        </button>
      </div>
    </div>
  )
}
