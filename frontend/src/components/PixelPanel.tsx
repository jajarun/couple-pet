import { ReactNode } from 'react'

// The app frame: a centered, phone-width column with a soft gender-tinted wash.
// (Kept this filename/export so routing stays put; it's no longer a pixel device.)
export function PixelPanel({ children }: { children: ReactNode }) {
  return <div className="app-shell">{children}</div>
}
