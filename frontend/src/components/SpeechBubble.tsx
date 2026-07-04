import { useEffect, useState } from 'react'

export function SpeechBubble({ text, typing, fromPet }: { text: string; typing?: boolean; fromPet?: boolean }) {
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

  return <div className={`speech${fromPet ? ' from-pet' : ''}`}>{shown}</div>
}
