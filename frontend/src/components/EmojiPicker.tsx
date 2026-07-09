import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { AVATAR_EMOJI_GROUPS } from '../avatarOptions'

/**
 * 点分身本人换造型：28 个 emoji 平铺要占掉半屏，收进底部抽屉里。
 *
 * 选中即关闭（一次点击就够），但**不落库**——外面那颗「保存」键仍是唯一的提交点，
 * 跟名字输入框的语义保持一致。
 */
export function EmojiPicker({ value, onChange }: { value: string; onChange: (em: string) => void }) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)

  const close = () => {
    setOpen(false)
    triggerRef.current?.focus() // 抽屉收回时把焦点还给触发它的那颗按钮
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="face-picker"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-label={`换造型，当前 ${value}`}
      >
        <span className="face-picker-face">{value}</span>
        <span className="face-picker-badge" aria-hidden="true">✏️</span>
      </button>

      <AnimatePresence>
        {open && (
          <EmojiSheet
            value={value}
            onPick={(em) => {
              onChange(em)
              close()
            }}
            onClose={close}
          />
        )}
      </AnimatePresence>
    </>
  )
}

/**
 * 挂到 body 上，别长在触发它的那棵子树里：
 * ① `position: fixed` 一旦碰上带 transform 的祖先就会改锚到那个祖先上；
 * ② 页面的 `text-align` / 字号会一路继承进来（设置页的 .center 就干过这事）。
 */
function EmojiSheet({
  value,
  onPick,
  onClose,
}: {
  value: string
  onPick: (em: string) => void
  onClose: () => void
}) {
  const sheetRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    sheetRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return createPortal(
    <motion.div
      className="sheet-backdrop"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        ref={sheetRef}
        className="sheet"
        data-testid="emoji-sheet"
        role="dialog"
        aria-modal="true"
        aria-label="挑个造型"
        tabIndex={-1}
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 30, stiffness: 320 }}
        onClick={(e) => e.stopPropagation()} // 点面板本身不该把它关掉
      >
        <div className="sheet-grip" aria-hidden="true" />
        <div className="sheet-head">
          <strong>挑个造型</strong>
          <button type="button" className="btn-ghost sheet-close" onClick={onClose}>
            关闭
          </button>
        </div>

        <div className="sheet-body">
          {AVATAR_EMOJI_GROUPS.map((group) => (
            <div key={group.label} className="stack" style={{ gap: 8 }}>
              <span className="tiny muted">{group.label}</span>
              <div className="emoji-chips">
                {group.emojis.map((em) => (
                  <button
                    type="button"
                    key={em}
                    className="emoji-chip"
                    aria-label={`emoji-${em}`}
                    aria-pressed={em === value}
                    onClick={() => onPick(em)}
                  >
                    {em}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </motion.div>
    </motion.div>,
    document.body,
  )
}
