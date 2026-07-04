import { useQuery } from '@tanstack/react-query'
import { statsKey } from '../hooks/useFeed'
import { Stats } from '../api/types'
import { StatGauge } from '../components/StatGauge'

const GRIEVANCE_ALARM = 80

const DEFAULT_STATS: Stats = { grievance: 0, dogfood: 0, miss: 0, intimacy: 0 }

export function StatDashboard({ coupleId }: { coupleId: number }) {
  // enabled:false → queryFn never runs; this observer only reads what
  // useFeed / useAction write via setQueryData(statsKey(...)).
  const { data } = useQuery<Stats>({
    queryKey: statsKey(coupleId),
    queryFn: () => DEFAULT_STATS,
    enabled: false,
  })
  const s = data ?? DEFAULT_STATS
  return (
    <div style={{ display: 'flex', gap: 8 }}>
      <StatGauge label="委屈" value={s.grievance} alarm={s.grievance >= GRIEVANCE_ALARM} />
      <StatGauge label="狗粮" value={s.dogfood} />
      <StatGauge label="想你" value={s.miss} />
      <StatGauge label="亲密" value={s.intimacy} />
    </div>
  )
}
