import { PressButton } from '../components/PressButton'

const ACTIONS: { type: string; label: string; emoji: string }[] = [
  { type: 'scold', label: '骂一顿', emoji: '😤' },
  { type: 'poke', label: '戳一戳', emoji: '👉' },
  { type: 'feed_dogfood', label: '喂狗粮', emoji: '🍬' },
  { type: 'hug', label: '抱抱', emoji: '🤗' },
  { type: 'miss_you', label: '想你', emoji: '💭' },
  { type: 'apologize', label: '道歉', emoji: '🙇' },
]

export function ActionBar({ onAction, disabled }: { onAction: (type: string) => void; disabled?: boolean }) {
  return (
    <div className="actions-grid">
      {ACTIONS.map((a) => (
        <PressButton key={a.type} onPress={() => onAction(a.type)} disabled={disabled}>
          <span className="emoji" aria-hidden="true">{a.emoji}</span>
          <span>{a.label}</span>
        </PressButton>
      ))}
    </div>
  )
}
