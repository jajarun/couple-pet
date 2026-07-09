/** 昨夜梦话：每天早上分身自己冒出来的一句话，这是「点进来看一眼」的钩子。没做梦就不占地方。 */
export function DreamCard({ dream }: { dream?: { content: string; at: string } | null }) {
  if (!dream) return null
  return (
    <div className="card dream-card" data-testid="dream-card">
      <div className="dream-head">🌙 昨夜梦话</div>
      <p className="dream-text">{dream.content}</p>
    </div>
  )
}
