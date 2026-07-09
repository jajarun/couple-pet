import { motion } from 'framer-motion'
import { EvolutionView } from '../api/types'


const STAGE_LABEL = ['蛋', '幼体', '成体', '完全体']

export function EvolutionBar({ evo }: { evo: EvolutionView }) {
  const maxed = evo.next_exp === null
  const left = maxed ? 0 : evo.next_exp! - evo.exp
  return (
    <div className="evo-bar" data-testid="evo-bar" data-stage={evo.stage}>
      <div className="evo-head">
        <span className="evo-title">
          {evo.title}
          <span className="muted tiny"> · {STAGE_LABEL[evo.stage] ?? '?'}</span>
        </span>
        <span className="muted tiny">{maxed ? 'MAX' : `${evo.exp}/${evo.next_exp}`}</span>
      </div>
      <div className="chip-track">
        <motion.div
          className="chip-fill"
          initial={false}
          animate={{ width: `${Math.round(evo.progress * 100)}%` }}
          transition={{ type: 'spring', stiffness: 160, damping: 22 }}
        />
      </div>
      <span className="muted tiny">
        {maxed ? '养到头了，它是你的杰作' : `再攒 ${left} 点就长大了`}
      </span>
    </div>
  )
}
