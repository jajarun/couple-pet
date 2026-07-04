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
    <div role="tablist" style={{ display: 'flex', gap: 6, marginTop: 8 }}>
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={t.key === active}
          onClick={() => onChange(t.key)}
          style={{
            flex: 1,
            padding: '10px 4px',
            border: '3px solid #101010',
            borderRadius: 6,
            background: t.key === active ? 'var(--accent)' : 'var(--panel)',
            color: 'var(--ink)',
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
