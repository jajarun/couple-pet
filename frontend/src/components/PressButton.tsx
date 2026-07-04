import { ReactNode, useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

export function PressButton({
  children,
  onPress,
  disabled,
  className = 'action-btn',
  cooldownMs = 800,
}: {
  children: ReactNode
  onPress: () => void
  disabled?: boolean
  className?: string
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
      whileTap={{ scale: 0.94 }}
      onClick={handle}
      disabled={disabled || cooling}
      className={className}
    >
      {children}
    </motion.button>
  )
}
