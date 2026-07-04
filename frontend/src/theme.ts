export type Gender = 'male' | 'female'

/** Paint the whole app in the keeper's gender color (男→蓝 / 女→淡粉).
 *  Unknown/null falls back to the neutral lavender defined in tokens.css. */
export function applyTheme(gender?: Gender | null): void {
  const el = document.documentElement
  if (gender === 'male' || gender === 'female') el.dataset.theme = gender
  else delete el.dataset.theme
}
