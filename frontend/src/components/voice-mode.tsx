import { Cancel01Icon, LinkSquare02Icon, Mic01Icon, SentIcon } from '@hugeicons/core-free-icons'
import { HugeiconsIcon } from '@hugeicons/react'
import { type ReactNode, type RefObject, useEffect, useRef } from 'react'

import type { Turn } from '@/components/conversation-thread'
import { SarjyMark } from '@/components/sarjy-mark'
import { SpokenWords } from '@/components/spoken-words'
import type { TalkMode } from '@/components/talk-mode'
import { Button } from '@/components/ui/button'
import type { AudioLevels, Status } from '@/lib/voice-session'

// How quickly the glow follows the voice: the share of the gap it closes each frame.
const GLOW_FOLLOW = 0.12

interface VoiceModeProps {
  // The microphone and full-visit cards, when one applies.
  cards: ReactNode
  disabled: boolean
  // The voice levels the glow follows.
  levels: AudioLevels
  // The line under the orb: what Sarjy is doing, or how to talk to it.
  line: { id: string; text: string; trouble: boolean }
  onClose: () => void
  onPress: () => void
  onRelease: () => void
  // The talk orb, drawn large.
  orb: ReactNode
  settings: ReactNode
  status: Status
  talkMode: TalkMode
  // The newest exchange, the only one voice mode shows.
  turn: Turn | undefined
}

// Concept two: a phone screen for talking and little else, after the voice mode of chat
// apps. Sarjy's orb fills the middle and takes turns with the traveller; its words appear
// under it as they are spoken; the full page, with the memory and latency panels, is one
// tap away.
export function VoiceMode({ cards, disabled, levels, line, onClose, onPress, onRelease, orb, settings, status, talkMode, turn }: VoiceModeProps) {
  const glowRef = useRef<HTMLDivElement>(null)
  useGlow(glowRef, levels, status)
  const sending = talkMode === 'tap' && status === 'listening'

  return (
    <div className="relative flex h-svh flex-col overflow-hidden">
      <div aria-hidden="true" className="voice-glow" ref={glowRef} />
      <header className="relative flex items-center justify-center gap-2 pt-4">
        <SarjyMark className="size-6" />
        <span className="font-heading text-lg/none font-semibold tracking-tight">sarjy</span>
      </header>

      <main className="relative flex min-h-0 flex-1 flex-col items-center justify-center gap-4 px-6">
        <div className="orb-large">{orb}</div>
        <p aria-live="polite" className={line.trouble ? 'text-sm text-destructive' : 'text-sm text-muted-foreground'} id={line.id}>
          <span className="label-in inline-block" key={line.text}>
            {line.text}
          </span>
        </p>
        <div className="flex min-h-32 w-full max-w-md flex-col items-center gap-3 text-center">
          {status === 'listening' || turn === undefined ? null : <Captions turn={turn} />}
        </div>
      </main>

      <div className="relative flex flex-col items-center gap-3 px-6 pb-2">
        {cards}
        {status === 'idle' && turn !== undefined && turn.links.length > 0 ? (
          <ul aria-label="Tours Sarjy mentioned" className="turn-in flex flex-wrap justify-center gap-2">
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
      </div>

      <footer className="pb-safe relative flex items-center justify-between px-6">
        {settings}
        <div className="flex items-center gap-3">
          {/* Holding a button on a phone would otherwise scroll, select text or open a menu. */}
          <div className="touch-none select-none">
            <Button
              aria-label={sending ? 'Send' : 'Talk to Sarjy'}
              aria-pressed={status === 'listening'}
              disabled={disabled}
              onContextMenu={(event) => {
                event.preventDefault()
              }}
              onPointerCancel={onRelease}
              onPointerDown={onPress}
              onPointerLeave={onRelease}
              onPointerUp={onRelease}
              size="icon-xl"
              variant={status === 'listening' ? 'default' : 'secondary'}
            >
              <HugeiconsIcon icon={sending ? SentIcon : Mic01Icon} />
            </Button>
          </div>
          <Button aria-label="Leave voice mode" onClick={onClose} size="icon-xl" title="Leave voice mode" variant="ghost">
            <HugeiconsIcon icon={Cancel01Icon} />
          </Button>
        </div>
      </footer>
    </div>
  )
}

// The newest exchange as captions: the traveller's words until Sarjy answers, then Sarjy's
// sentence being spoken, with the one before it fading above.
function Captions({ turn }: { turn: Turn }) {
  const current = turn.clips.at(-1)
  const before = turn.clips.at(-2)
  if (current !== undefined) {
    return (
      <>
        {before === undefined ? null : <p className="line-clamp-2 text-muted-foreground">{before.text}</p>}
        {/* A new key for each sentence, so its words reveal from the start. */}
        <div className="turn-in" key={`${String(turn.id)}-${String(turn.clips.length)}`}>
          <SpokenWords clips={[current]} size="caption" />
        </div>
        {turn.ttfaMs === null ? null : (
          <span className="text-xs text-muted-foreground tabular-nums">First audio after {(turn.ttfaMs / 1000).toFixed(1)} s</span>
        )}
      </>
    )
  }
  if (turn.trouble !== null) {
    return <p className="text-destructive">{turn.trouble}</p>
  }
  // A reply whose voice never came is still worth reading.
  if (turn.reply !== null) {
    return <p className="text-xl/snug text-balance">{turn.reply}</p>
  }
  return <p className="turn-in text-lg text-balance text-muted-foreground">“{turn.heard}”</p>
}

// Brightens the glow with whoever is speaking: the traveller while listening, Sarjy while it
// talks. Under reduced motion it holds still.
function useGlow(glowRef: RefObject<HTMLDivElement | null>, levels: AudioLevels, status: Status): void {
  useEffect(() => {
    const glow = glowRef.current
    if (glow === null || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return
    }
    let level = 0
    let frame = 0
    const follow = (): void => {
      const target = status === 'listening' ? levels.inputLevel() : status === 'speaking' ? levels.outputLevel() : 0
      level += (target - level) * GLOW_FOLLOW
      glow.style.setProperty('--glow', level.toFixed(3))
      frame = requestAnimationFrame(follow)
    }
    frame = requestAnimationFrame(follow)
    return () => {
      cancelAnimationFrame(frame)
    }
  }, [glowRef, levels, status])
}
