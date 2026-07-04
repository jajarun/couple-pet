import { motion } from 'framer-motion'

export function PetSprite({ face = '◕‿◕', reaction }: { face?: string; reaction?: string | null }) {
  return (
    <motion.div
      data-testid="pet"
      data-reaction={reaction ?? ''}
      animate={reaction ? { rotate: [0, -8, 8, -4, 0], scale: [1, 1.05, 1] } : { y: [0, -2, 0] }}
      transition={reaction ? { duration: 0.4 } : { duration: 2, repeat: Infinity }}
      style={{ fontSize: 56, textAlign: 'center', padding: 16 }}
    >
      {face}
    </motion.div>
  )
}
