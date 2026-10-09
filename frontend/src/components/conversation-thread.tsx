import { useEffect, useRef } from 'react'

import { SpokenWords } from '@/components/spoken-words'

export interface Turn {
  heard: string
  id: number
  reply: null | string
  ttfaMs: null | number
}

interface ConversationThreadProps {
  // True while Sarjy speaks the newest turn's reply.
  speaking: boolean
  turns: Turn[]
}

// The visit's conversation, set like a script: who speaks, then their words. Newest at
// the bottom, next to the orb the words come from.
export function ConversationThread({ speaking, turns }: ConversationThreadProps) {
  const endRef = useRef<HTMLDivElement>(null)
  const last = turns.at(-1)
  // Only the newest reply can be the one being spoken.
  const speakingId = speaking ? last?.id : undefined

  // Keep the newest words in view as they appear.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [turns.length, last?.reply, speaking])

  if (turns.length === 0) {
    return (
      <div className="flex flex-1 flex-col justify-end gap-2 pb-6">
        <p className="text-2xl/snug font-medium text-balance md:text-3xl/snug">Tours, prices and the weather, anywhere in the UAE.</p>
        <p className="text-muted-foreground">Hold the orb, or hold Space, and ask Sarjy.</p>
      </div>
    )
  }

  return (
    <>
      <ol aria-label="Conversation" className="flex flex-col gap-8 pb-6">
      {turns.map((turn) => (
        <li className="turn-in flex flex-col gap-3" key={turn.id}>
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-muted-foreground">You</span>
            <p className="text-muted-foreground">{turn.heard}</p>
          </div>
          {turn.reply !== null && (
            <div className="flex flex-col gap-1">
              <span className="text-xs font-medium text-primary">Sarjy</span>
              <SpokenWords speaking={turn.id === speakingId} text={turn.reply} />
              {turn.ttfaMs !== null && (
                <span className="text-xs text-muted-foreground tabular-nums">First audio after {(turn.ttfaMs / 1000).toFixed(1)} s</span>
              )}
            </div>
          )}
        </li>
      ))}
      </ol>
      <div ref={endRef} />
    </>
  )
}
