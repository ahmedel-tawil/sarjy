import { useEffect, useState } from 'react'

// Kokoro's af_heart says about this many words a second at normal speed. Until the
// session tells us how long each sentence's audio is, words are paced by this estimate.
const WORDS_PER_SECOND = 2.6

interface SpokenWordsProps {
  speaking: boolean
  text: string
}

// Sarjy's reply appears word by word while it is spoken, the current word in the accent
// colour; once the voice stops, the whole reply stays.
export function SpokenWords({ speaking, text }: SpokenWordsProps) {
  const words = text.split(/\s+/).filter(Boolean)
  const [shown, setShown] = useState(speaking ? 0 : words.length)

  useEffect(() => {
    if (!speaking || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return
    }
    const timer = window.setInterval(() => {
      setShown((count) => count + 1)
    }, 1000 / WORDS_PER_SECOND)
    return () => {
      window.clearInterval(timer)
    }
  }, [speaking])

  const visible = speaking ? Math.min(shown, words.length) : words.length
  return (
    <p className="text-lg/relaxed text-pretty md:text-xl/relaxed">
      {words.slice(0, visible).map((word, index) => (
        // Words can repeat, so the position is part of the key; the list only grows.
        <span className={speaking && index === visible - 1 ? 'spoken-word text-primary' : 'spoken-word'} key={`${String(index)}-${word}`}>
          {word}{' '}
        </span>
      ))}
    </p>
  )
}
