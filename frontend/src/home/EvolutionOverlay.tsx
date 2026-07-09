import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { EvolutionView } from '../api/types'

const HOLD_MS = 2200

const HEADLINE = ['', '🐣 破壳了！', '✨ 进化成成体！', '👑 完全体！']
const SUBLINE = [
  '',
  '它开始认得你了',
  '性格就此定型，再也改不回来咯',
  '这只分身被你养到头了',
]

/** 进化瞬间的全屏揭晓。由 /actions 返回的 evolved:true 触发，自动消失。 */
export function EvolutionOverlay({ evo, onDone }: { evo: EvolutionView; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, HOLD_MS)
    return () => clearTimeout(t)
  }, [onDone])

  return (
    <motion.div
      className="evo-overlay"
      data-testid="evo-overlay"
      role="status"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onDone}
    >
      <motion.div
        className="evo-burst"
        initial={{ scale: 0.3, rotate: -20, opacity: 0 }}
        animate={{ scale: [0.3, 1.35, 1], rotate: [-20, 8, 0], opacity: 1 }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      >
        {evo.emoji}
      </motion.div>
      <motion.div
        className="evo-headline"
        initial={{ y: 12, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.35 }}
      >
        {HEADLINE[evo.stage] ?? '✨ 进化了！'}
      </motion.div>
      <motion.div
        className="evo-subline"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.55 }}
      >
        {evo.title} · {SUBLINE[evo.stage] ?? ''}
      </motion.div>
    </motion.div>
  )
}
