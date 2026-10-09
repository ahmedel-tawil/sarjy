import { useEffect, useRef } from 'react'

import { type SpokenClip, SpokenWords } from '@/components/spoken-words'
import type { TurnStages } from '@/lib/stages-of'

export interface Turn {
  // Sarjy's voice, clip by clip, as each one started playing.
  clips: SpokenClip[]
  heard: string
  id: number
  // The whole reply, shown as text only if its voice never played.
  reply: null | string
  // Where the turn's time went, once both clocks' marks are in (M3.2).
  stages: null | TurnStages
  ttfaMs: null | number
}

// The visit's conversation, set like a script: who speaks, then their words. Newest at
// the bottom, next to the orb the words come from.
export function ConversationThread({ turns }: { turns: Turn[] }) {
  const endRef = useRef<HTMLDivElement>(null)
  const last = turns.at(-1)

  // Keep the newest words in view as they appear.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [turns.length, last?.clips.length, last?.reply])

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
            {turn.clips.length > 0 || turn.reply !== null ? (
              <div className="flex flex-col gap-1">
                <span className="text-xs font-medium text-primary">Sarjy</span>
                {turn.clips.length > 0 ? (
                  <SpokenWords clips={turn.clips} />
                ) : (
                  <p className="text-lg/relaxed text-pretty md:text-xl/relaxed">{turn.reply}</p>
                )}
                {turn.ttfaMs === null ? null : (
                  <span className="text-xs text-muted-foreground tabular-nums">First audio after {(turn.ttfaMs / 1000).toFixed(1)} s</span>
                )}
              </div>
            ) : null}
          </li>
        ))}
      </ol>
      <div ref={endRef} />
    </>
  )
}
