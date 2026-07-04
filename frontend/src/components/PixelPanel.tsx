import { ReactNode } from 'react'

export function PixelPanel({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        maxWidth: 440,
        margin: '0 auto',
        minHeight: '100dvh',
        background: 'var(--machine)',
        border: '6px solid #101010',
        borderRadius: 'var(--radius)',
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {children}
    </div>
  )
}
