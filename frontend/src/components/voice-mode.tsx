import { Cancel01Icon, DashboardSpeed02Icon, LinkSquare02Icon, Mic01Icon, SentIcon } from '@hugeicons/core-free-icons'
import { HugeiconsIcon } from '@hugeicons/react'
import { type ReactNode, type RefObject, useEffect, useRef } from 'react'

import type { Turn } from '@/components/conversation-thread'
import { LatencyWaterfall, type TimedTurn } from '@/components/latency-panel'
import { FactList, ForgetMe } from '@/components/memory-panel'
import { SarjyMark } from '@/components/sarjy-mark'
import { SpokenWords } from '@/components/spoken-words'
import type { TalkMode } from '@/components/talk-mode'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverHeader, PopoverTitle, PopoverTrigger } from '@/components/ui/popover'
import type { RememberedFact } from '@/lib/protocol'
import type { AudioLevels, Status } from '@/lib/voice-session'

// How quickly the glow follows the voice: the share of the gap it closes each frame.
const GLOW_FOLLOW = 0.12

// What Sarjy remembers, and Forget me, as the full page's memory panel has them.
interface Memory {
  busy: boolean
  // Null until the visit has connected.
  facts: null | RememberedFact[]
  onForgetMe: () => void
}

interface TalkButton {
  disabled: boolean
  onPress: () => void
  onRelease: () => void
  status: Status
  talkMode: TalkMode
}

interface VoiceModeProps {
  // The microphone and full-visit cards, when one applies.
  cards: ReactNode
  // The voice levels the glow follows.
  levels: AudioLevels
  // The line under the orb: what Sarjy is doing, or how to talk to it.
  line: { id: string; text: string; trouble: boolean }
  memory: Memory
  onClose: () => void
  // The talk orb, drawn large.
  orb: ReactNode
  settings: ReactNode
  talk: TalkButton
  // This visit's answered turns, for the latency waterfall.
  timed: TimedTurn[]
  // The newest exchange, the only one voice mode shows.
  turn: Turn | undefined
}

// Concept two: a screen for talking and little else, after the voice mode of chat apps.
// Sarjy's orb fills the middle and takes turns with the traveller; its words appear under
// it as they are spoken; what it remembers and how fast it answered open from the top bar;
// the full page, with the conversation and earlier visits, is one tap away.
export function VoiceMode({ cards, levels, line, memory, onClose, orb, settings, talk, timed, turn }: VoiceModeProps) {
  const glowRef = useRef<HTMLDivElement>(null)
  useGlow(glowRef, levels, talk.status)

  return (
    <div className="relative flex h-svh flex-col overflow-hidden">
      <div aria-hidden="true" className="voice-glow" ref={glowRef} />
      <header className="relative grid grid-cols-3 items-center px-4 pt-4 md:px-8">
        <div className="justify-self-start">{memory.facts === null ? null : <MemoryButton memory={{ ...memory, facts: memory.facts }} />}</div>
        <div className="flex items-center gap-2 justify-self-center">
          <SarjyMark className="size-6" />
          <span className="font-heading text-lg/none font-semibold tracking-tight">sarjy</span>
        </div>
        <div className="justify-self-end">
          <LatencyButton timed={timed} />
        </div>
      </header>

      <main className="relative flex min-h-0 flex-1 flex-col items-center justify-center gap-4 px-6">
        <div className="orb-large">{orb}</div>
        <p aria-live="polite" className={line.trouble ? 'text-sm text-destructive' : 'text-sm text-muted-foreground'} id={line.id}>
          <span className="label-in inline-block" key={line.text}>
            {line.text}
          </span>
        </p>
        <div className="caption-measure flex min-h-32 w-full flex-col items-center gap-3">
          {talk.status === 'listening' || turn === undefined ? null : <Captions turn={turn} />}
        </div>
      </main>

      <div className="relative flex flex-col items-center gap-3 px-6 pb-2">
        {cards}
        {talk.status === 'idle' && turn !== undefined && turn.links.length > 0 ? <TourLinks turn={turn} /> : null}
      </div>

      <footer className="pb-safe relative flex items-center justify-between px-6 md:justify-center md:gap-6">
        {settings}
        {/* On a phone the microphone and close sit together at the right, as in chat apps;
            on a wider screen all three gather in the middle, under the orb. */}
        <div className="flex items-center gap-3 md:contents">
          <MicButton talk={talk} />
          <Button aria-label="Leave voice mode" onClick={onClose} size="icon-xl" title="Leave voice mode" variant="ghost">
            <HugeiconsIcon icon={Cancel01Icon} />
          </Button>
        </div>
      </footer>
    </div>
  )
}

// "Remembers 3": what Sarjy knows about the traveller, with Forget me.
function MemoryButton({ memory }: { memory: Memory & { facts: RememberedFact[] } }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button size="sm" variant="secondary">
          {/* A new key for each count, so a newly remembered fact shows as it lands. */}
          <span className="label-in inline-block" key={memory.facts.length}>
            Remembers {memory.facts.length}
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start">
        <PopoverHeader>
          <div className="flex items-center justify-between gap-2">
            <PopoverTitle>What Sarjy remembers</PopoverTitle>
            <ForgetMe busy={memory.busy} empty={memory.facts.length === 0} onForgetMe={memory.onForgetMe} />
          </div>
        </PopoverHeader>
        <FactList facts={memory.facts} />
      </PopoverContent>
    </Popover>
  )
}

// The latency waterfall, one tap away: the deep dive, during the demo itself.
function LatencyButton({ timed }: { timed: TimedTurn[] }) {
  const last = timed.at(-1)
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button aria-label="How fast Sarjy answered" size="sm" title="How fast Sarjy answered" variant="secondary">
          <HugeiconsIcon data-icon="inline-start" icon={DashboardSpeed02Icon} />
          <span className="tabular-nums">{last === undefined ? 'Speed' : `${(last.ttfaMs / 1000).toFixed(1)} s`}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end">
        <PopoverHeader>
          <PopoverTitle>How fast Sarjy answered</PopoverTitle>
        </PopoverHeader>
        <LatencyWaterfall turns={timed} />
      </PopoverContent>
    </Popover>
  )
}

// Tap to talk, or hold in hold mode; while listening in tap mode it sends.
function MicButton({ talk }: { talk: TalkButton }) {
  const sending = talk.talkMode === 'tap' && talk.status === 'listening'
  return (
    // Holding a button on a phone would otherwise scroll, select text or open a menu.
    <div className="touch-none select-none">
      <Button
        aria-label={sending ? 'Send' : 'Talk to Sarjy'}
        aria-pressed={talk.status === 'listening'}
        // Space talks here as it does on the orb.
        data-talk=""
        disabled={talk.disabled}
        onContextMenu={(event) => {
          event.preventDefault()
        }}
        onPointerCancel={talk.onRelease}
        onPointerDown={talk.onPress}
        onPointerLeave={talk.onRelease}
        onPointerUp={talk.onRelease}
        size="icon-xl"
        variant={talk.status === 'listening' ? 'default' : 'secondary'}
      >
        <HugeiconsIcon icon={sending ? SentIcon : Mic01Icon} />
      </Button>
    </div>
  )
}

function TourLinks({ turn }: { turn: Turn }) {
  return (
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
        {before === undefined ? null : <p className="caption-before text-muted-foreground">{before.text}</p>}
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
      level += (levelNow(levels, status) - level) * GLOW_FOLLOW
      glow.style.setProperty('--glow', level.toFixed(3))
      frame = requestAnimationFrame(follow)
    }
    frame = requestAnimationFrame(follow)
    return () => {
      cancelAnimationFrame(frame)
    }
  }, [glowRef, levels, status])
}

function levelNow(levels: AudioLevels, status: Status): number {
  if (status === 'listening') {
    return levels.inputLevel()
  }
  return status === 'speaking' ? levels.outputLevel() : 0
}
