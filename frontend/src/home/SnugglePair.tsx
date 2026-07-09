import { motion } from 'framer-motion'
import { PetSprite } from '../components/PetSprite'
import { Avatar } from '../api/types'
import { faceOf } from '../evolution'

/**
 * 同框时两只镜像分身并排贴贴：左边是我养的那只（代表 TA，可点），右边是 TA 养的那只（代表我）。
 * `poked` 为真时右边那只抖一下——TA 此刻正在那头对我做什么。
 */
export function SnugglePair({
  pet,
  mine,
  reaction,
  evolving,
  poked,
  onPoke,
  disabled,
}: {
  pet?: Avatar
  mine?: Avatar
  reaction: string | null
  evolving: boolean
  poked: boolean
  onPoke: () => void
  disabled?: boolean
}) {
  return (
    <div className="snuggle" data-testid="snuggle-pair">
      <div className="snuggle-half">
        <button
          type="button"
          className="pet-tap"
          onClick={onPoke}
          disabled={disabled}
          aria-label={`戳一戳 ${pet?.name || 'TA 的分身'}`}
        >
          <PetSprite face={faceOf(pet)} reaction={reaction} evolving={evolving} />
        </button>
        <div className="pet-name">{pet?.name || 'TA 的分身'}</div>
      </div>

      <motion.div
        className="snuggle-heart"
        aria-hidden="true"
        animate={{ scale: [1, 1.22, 1] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
      >
        💞
      </motion.div>

      <motion.div
        className="snuggle-half"
        data-testid="snuggle-me"
        animate={poked ? { x: [0, -6, 6, -4, 0], rotate: [0, -4, 4, -2, 0] } : { x: 0, rotate: 0 }}
        transition={{ duration: 0.45 }}
      >
        <PetSprite face={faceOf(mine)} reaction={null} />
        <div className="pet-name muted">{mine?.name || '你'}</div>
      </motion.div>
    </div>
  )
}
