import { motion } from 'framer-motion'

export function StatGauge({
  label,
  value,
  alarm,
}: {
  label: string
  value: number
  alarm?: boolean
}) {
  const rounded = Math.round(value)
  const clamped = Math.max(0, Math.min(100, value))
  return (
    <div data-testid={`gauge-${label}`} data-alarm={alarm ? 'true' : 'false'} style={{ flex: 1 }}>
      <div style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between' }}>
        <span>{label}</span>
        {/* Plain text keeps the value deterministic for tests; key remount gives a pop on change. */}
        <motion.span
          key={rounded}
          initial={{ y: -6, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.25 }}
        >
          {rounded}
        </motion.span>
      </div>
      <div style={{ height: 8, border: '2px solid #101010', background: '#0003' }}>
        <motion.div
          animate={{ width: `${clamped}%` }}
          transition={{ duration: 0.4 }}
          style={{ height: '100%', background: alarm ? 'var(--warn)' : 'var(--good)' }}
        />
      </div>
    </div>
  )
}
