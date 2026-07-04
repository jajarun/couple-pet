import { useEffect, useState } from 'react'

export function SpeechBubble({ text, typing }: { text: string; typing?: boolean }) {
  const [shown, setShown] = useState(typing ? '' : text)

  useEffect(() => {
    if (!typing) {
      setShown(text)
      return
    }
    setShown('')
    let i = 0
    const id = setInterval(() => {
      i += 1
      setShown(text.slice(0, i))
      if (i >= text.length) clearInterval(id)
    }, 45)
    return () => clearInterval(id)
  }, [text, typing])

  return (
    <div
      style={{
        display: 'inline-block',
        background: '#fff',
        color: '#111',
        border: '3px solid #101010',
        borderRadius: 10,
        padding: '8px 12px',
        maxWidth: '80%',
      }}
    >
      {shown}
    </div>
  )
}
