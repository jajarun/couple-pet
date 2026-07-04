import { motion } from 'framer-motion'

const EMOJI: Record<string, string> = {
  委屈: '😤',
  狗粮: '🍬',
  想你: '💭',
  亲密: '💞',
}

export function StatGauge({
  label,
  value,
  alarm,
}: {
  label: string
  value: number
  alarm?: boolean
}) {
  const clamped = Math.max(0, Math.min(100, value))
  const rounded = Math.round(clamped)
  return (
    <div
      data-testid={`gauge-${label}`}
      data-alarm={alarm ? 'true' : 'false'}
      className={`chip${alarm ? ' alarm' : ''}`}
    >
      <span className="chip-label">
        <span aria-hidden="true">{EMOJI[label] ?? ''}</span> <span>{label}</span>
      </span>
      {/* Plain text keeps the value deterministic for tests; key remount pops on change. */}
      <motion.span
        className="chip-val"
        key={rounded}
        initial={{ y: -6, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.25 }}
      >
        {rounded}
      </motion.span>
      <div className="chip-track">
        <motion.div
          className="chip-fill"
          animate={{ width: `${clamped}%` }}
          transition={{ duration: 0.25 }}
        />
      </div>
    </div>
  )
}
