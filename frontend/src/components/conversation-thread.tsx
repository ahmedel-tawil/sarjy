import { LinkSquare02Icon } from '@hugeicons/core-free-icons'
import { HugeiconsIcon } from '@hugeicons/react'
import { useEffect, useRef } from 'react'

import { type SpokenClip, SpokenWords } from '@/components/spoken-words'
import { HAS_KEYBOARD, type TalkMode } from '@/components/talk-mode'
import { Button } from '@/components/ui/button'
import type { TourLink } from '@/lib/protocol'
import type { TurnStages } from '@/lib/stages-of'

export interface Turn {
  // Sarjy's voice, clip by clip, as each one started playing.
  clips: SpokenClip[]
  heard: string
  id: number
  // The tours the reply named, with their pages; Sarjy never reads addresses aloud (D-90).
  links: TourLink[]
  // The whole reply, shown as text only if its voice never played.
  reply: null | string
  // Where the turn's time went, once both clocks' marks are in (M3.2).
  stages: null | TurnStages
  // Why the question went unanswered, or answered only in writing (D-81).
  trouble: null | string
  ttfaMs: null | number
}

// Questions from the demo scenarios, so a first-time visitor sees what Sarjy is for.
const EXAMPLES = [
  'What can we do in Abu Dhabi with two kids under 400 dirhams?',
  'Is tomorrow afternoon good for a desert safari?',
  'My favourite colour is green, and I don’t like heights.',
] as const

// The visit's conversation, set like a script: who speaks, then their words. Newest at
// the bottom, next to the orb the words come from.
// How to ask, for the talk mode in use (D-83), with Space only where there is a keyboard.
const HOW_TO_ASK: Readonly<Record<TalkMode, string>> = HAS_KEYBOARD
  ? {
      hold: 'Hold the orb, or hold Space, and ask Sarjy. Let go when you’re done.',
      tap: 'Tap the orb, or press Space, and ask Sarjy. Tap again when you’re done.',
    }
  : {
      hold: 'Hold the orb and ask Sarjy. Let go when you’re done.',
      tap: 'Tap the orb and ask Sarjy. Tap again when you’re done.',
    }

interface ConversationThreadProps {
  // A visitor with earlier visits is welcomed back rather than shown example questions.
  returning: boolean
  talkMode: TalkMode
  turns: Turn[]
}

export function ConversationThread({ returning, talkMode, turns }: ConversationThreadProps) {
  const endRef = useRef<HTMLDivElement>(null)
  const last = turns.at(-1)

  // Keep the newest words in view as they appear.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [turns.length, last?.clips.length, last?.reply, returning])

  if (turns.length === 0 && returning) {
    return (
      <div className="flex flex-col gap-2 pb-6">
        <p className="text-2xl/snug font-medium text-balance md:text-3xl/snug">Welcome back.</p>
        <p className="text-muted-foreground">{HOW_TO_ASK[talkMode]} Or hear an earlier answer again with its play button.</p>
        <div ref={endRef} />
      </div>
    )
  }

  if (turns.length === 0) {
    return (
      <div className="flex flex-1 flex-col justify-end gap-4 pb-6">
        <div className="flex flex-col gap-2">
          <p className="text-2xl/snug font-medium text-balance md:text-3xl/snug">Tours, prices and the weather, anywhere in the UAE.</p>
          <p className="text-muted-foreground">{HOW_TO_ASK[talkMode]}</p>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-muted-foreground">Try asking</span>
          <ul className="flex flex-col gap-1">
            {EXAMPLES.map((example) => (
              <li className="text-pretty" key={example}>
                “{example}”
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm text-muted-foreground">The first time you use the orb, your browser asks to use the microphone.</p>
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
            {turn.clips.length > 0 || turn.reply !== null || turn.trouble !== null ? (
              <div className="flex flex-col gap-1">
                <span className="text-xs font-medium text-primary">Sarjy</span>
                {turn.clips.length > 0 ? <SpokenWords clips={turn.clips} /> : null}
                {turn.clips.length === 0 && turn.reply !== null ? (
                  <p className="text-lg/relaxed text-pretty md:text-xl/relaxed">{turn.reply}</p>
                ) : null}
                {turn.links.length > 0 ? (
                  <ul aria-label="Tours Sarjy mentioned" className="flex flex-wrap gap-2 pt-1">
                    {turn.links.map((link) => (
                      <li key={link.url}>
                        <Button asChild size="sm" variant="outline">
                          <a aria-label={`${link.name}, opens the tour page in a new tab`} href={link.url} rel="noopener noreferrer" target="_blank">
                            {link.name}
                            <HugeiconsIcon data-icon="inline-end" icon={LinkSquare02Icon} />
                          </a>
                        </Button>
                      </li>
                    ))}
                  </ul>
                ) : null}
                {turn.trouble === null ? null : <p className="text-sm text-destructive">{turn.trouble}</p>}
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
