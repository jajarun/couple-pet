import { PressButton } from '../components/PressButton'

const ACTIONS: { type: string; label: string }[] = [
  { type: 'scold', label: '骂一顿' },
  { type: 'poke', label: '戳一戳' },
  { type: 'feed_dogfood', label: '喂狗粮' },
  { type: 'hug', label: '抱抱' },
  { type: 'miss_you', label: '想你' },
  { type: 'apologize', label: '道歉' },
]

export function ActionBar({ onAction, disabled }: { onAction: (type: string) => void; disabled?: boolean }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
      {ACTIONS.map((a) => (
        <PressButton key={a.type} onPress={() => onAction(a.type)} disabled={disabled}>
          {a.label}
        </PressButton>
      ))}
    </div>
  )
}
