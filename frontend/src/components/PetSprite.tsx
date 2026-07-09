import { motion } from 'framer-motion'

export function PetSprite({
  face = '◕‿◕',
  reaction,
  evolving = false,
}: {
  face?: string
  reaction?: string | null
  evolving?: boolean
}) {
  // 进化压过普通反应：这一下是主角，别让「戳一戳」的小抖动抢戏
  const mode = evolving ? 'evolving' : (reaction ?? 'idle')
  return (
    <motion.div
      key={mode}
      data-testid="pet"
      data-reaction={reaction ?? ''}
      data-evolving={evolving ? '1' : ''}
      className="pet-face"
      animate={
        evolving
          ? { scale: [1, 1.5, 0.9, 1.15, 1], rotate: [0, -14, 14, -5, 0] }
          : reaction
            ? { rotate: [0, -9, 9, -4, 0], scale: [1, 1.08, 1] }
            : { y: [0, -4, 0] }
      }
      transition={
        evolving
          ? { duration: 1.1, ease: 'easeInOut' }
          : reaction
            ? { duration: 0.45 }
            : { duration: 2.6, repeat: Infinity, ease: 'easeInOut' }
      }
    >
      {face}
    </motion.div>
  )
}
