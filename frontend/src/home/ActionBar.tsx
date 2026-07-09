import { PressButton } from '../components/PressButton'

const ACTIONS: { type: string; label: string; emoji: string }[] = [
  { type: 'scold', label: '骂一顿', emoji: '😤' },
  { type: 'poke', label: '戳一戳', emoji: '👉' },
  { type: 'feed_dogfood', label: '喂狗粮', emoji: '🍬' },
  { type: 'hug', label: '抱抱', emoji: '🤗' },
  { type: 'miss_you', label: '想你', emoji: '💭' },
  { type: 'apologize', label: '道歉', emoji: '🙇' },
]

// 同框限定：TA 也开着页面时才出现，TA 一下线这个键就消失（后端也拦，见 not_together）
const HEADPAT = { type: 'headpat', label: '摸摸头', emoji: '🫳' }

export function ActionBar({
  onAction,
  disabled,
  together,
}: {
  onAction: (type: string) => void
  disabled?: boolean
  together?: boolean
}) {
  const actions = together ? [...ACTIONS, HEADPAT] : ACTIONS
  return (
    <div className="actions-grid">
      {actions.map((a) => (
        <PressButton key={a.type} onPress={() => onAction(a.type)} disabled={disabled}>
          <span className="emoji" aria-hidden="true">{a.emoji}</span>
          <span>{a.label}</span>
        </PressButton>
      ))}
    </div>
  )
}
