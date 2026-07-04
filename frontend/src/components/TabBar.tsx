export type TabItem = { key: string; label: string }

export function TabBar({
  tabs,
  active,
  onChange,
}: {
  tabs: TabItem[]
  active: string
  onChange: (key: string) => void
}) {
  return (
    <div role="tablist" className="tabbar">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={t.key === active}
          onClick={() => onChange(t.key)}
          className="tab"
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
