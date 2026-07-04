import { ReactNode, useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

export function PressButton({
  children,
  onPress,
  disabled,
  cooldownMs = 800,
}: {
  children: ReactNode
  onPress: () => void
  disabled?: boolean
  cooldownMs?: number
}) {
  const [cooling, setCooling] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current)
  }, [])

  const handle = () => {
    if (disabled || cooling) return
    onPress()
    setCooling(true)
    timer.current = setTimeout(() => setCooling(false), cooldownMs)
  }

  return (
    <motion.button
      whileTap={{ scale: 0.9 }}
      onClick={handle}
      disabled={disabled || cooling}
      style={{
        padding: '12px 8px',
        border: '3px solid #101010',
        borderRadius: 8,
        background: disabled || cooling ? '#8a8aa0' : 'var(--panel)',
        color: 'var(--ink)',
        boxShadow: cooling ? 'var(--shadow-press)' : 'none',
      }}
    >
      {children}
    </motion.button>
  )
}
