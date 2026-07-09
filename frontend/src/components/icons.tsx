// 线性图标：一律用 currentColor 上色，好跟着性别主题走（男蓝白字 / 女粉深玫瑰字）。
// 圆角线帽 + 2px 描边，跟全站「扁平但柔和」的调子一致。

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const

/** 纸飞机：斜杠那一笔是机身折线，少了它就只是个箭头 */
export function PaperPlaneIcon({ size = 21 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="m22 2-7 20-4-9-9-4Z" {...base} />
      <path d="M22 2 11 13" {...base} />
    </svg>
  )
}

/** 笑脸：两只眼睛是「零长度圆角线段」画出来的圆点 */
export function SmileyIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="9" {...base} />
      <path d="M8.4 14.6s1.3 1.7 3.6 1.7 3.6-1.7 3.6-1.7" {...base} />
      <path d="M9 9.6h.01" {...base} />
      <path d="M15 9.6h.01" {...base} />
    </svg>
  )
}
