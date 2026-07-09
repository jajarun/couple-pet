import { useEffect, useRef, useState } from 'react'
import { SmileyIcon } from '../components/icons'
import { EMOJI_GROUPS } from './emoji'

/** 输入框右侧的表情选择器。挑完不自动收起——连着点几个是常态。
 *  必须放在一个 position:relative 的容器里（.chat-field），面板贴着它上沿弹。 */
export function EmojiPicker({
  onPick,
  disabled,
}: {
  onPick: (emoji: string) => void
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node
      if (triggerRef.current?.contains(t) || panelRef.current?.contains(t)) return
      setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setOpen(false)
      triggerRef.current?.focus() // Esc 收起后把焦点还给触发键
    }
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="emoji-trigger"
        aria-label="选择表情"
        aria-expanded={open}
        aria-haspopup="dialog"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
      >
        <SmileyIcon />
      </button>

      {open && (
        <div ref={panelRef} className="emoji-panel" role="dialog" aria-label="选择表情">
          {EMOJI_GROUPS.map((g) => (
            <div key={g.label} className="emoji-group">
              <div className="emoji-group-label">{g.label}</div>
              <div className="emoji-grid">
                {g.items.map((e) => (
                  <button key={e} type="button" className="emoji-cell" onClick={() => onPick(e)}>
                    {e}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
