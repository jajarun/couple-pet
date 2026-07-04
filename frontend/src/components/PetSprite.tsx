import { motion } from 'framer-motion'

export function PetSprite({ face = '◕‿◕', reaction }: { face?: string; reaction?: string | null }) {
  return (
    <motion.div
      key={reaction ?? 'idle'}
      data-testid="pet"
      data-reaction={reaction ?? ''}
      className="pet-face"
      animate={reaction ? { rotate: [0, -9, 9, -4, 0], scale: [1, 1.08, 1] } : { y: [0, -4, 0] }}
      transition={reaction ? { duration: 0.45 } : { duration: 2.6, repeat: Infinity, ease: 'easeInOut' }}
    >
      {face}
    </motion.div>
  )
}
