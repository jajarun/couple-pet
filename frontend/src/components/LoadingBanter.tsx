import { useEffect, useState } from 'react'
import { BANTER_LINES } from '../banter'

export function LoadingBanter({ intervalMs = 1200 }: { intervalMs?: number }) {
  const [i, setI] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setI((n) => (n + 1) % BANTER_LINES.length), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs])
  return (
    <div data-testid="banter" style={{ opacity: 0.85, fontSize: 13 }}>
      {BANTER_LINES[i]}
    </div>
  )
}
