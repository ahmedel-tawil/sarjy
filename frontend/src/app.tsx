import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

import { ConversationThread, type Turn } from '@/components/conversation-thread'
import { FirstLoad, wantsWelcome } from '@/components/first-load'
import { LatencyPanel } from '@/components/latency-panel'
import { MemoryPanel } from '@/components/memory-panel'
import type { OrbPhase } from '@/components/orb-renderer'
import { applyPalette, initialPalette, type Palette, PaletteSwitcher } from '@/components/palette-switcher'
import { RehearsalSession, rehearsedMicLevel } from '@/components/rehearsal-session'
import { SarjyMark } from '@/components/sarjy-mark'
import { TalkOrb } from '@/components/talk-orb'
import { Button } from '@/components/ui/button'
import { useMicLevel } from '@/components/use-mic-level'
import type { RememberedFact } from '@/lib/protocol'
import {
  type Problem,
  type PushToTalk,
  type Status,
  type Visit,
  VoiceSession,
  type VoiceSessionCallbacks,
} from '@/lib/voice-session'

// One screen: the visit's conversation, Sarjy as a sphere of dots you hold to talk to, and
// what Sarjy remembers and how fast it answered beside them (D-80).

const SOCKET_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`

const PHASE_FOR: Record<Status, OrbPhase> = {
  idle: 'rest',
  listening: 'listening',
  speaking: 'speaking',
  thinking: 'thinking',
}

// In development, ?rehearse plays scripted turns, to review the motion without a gateway or
// a microphone. Production builds never rehearse.
const REHEARSE = import.meta.env.DEV && new URLSearchParams(window.location.search).has('rehearse')

const PROBLEM_TEXT: Record<Problem, string> = {
  'connection_lost': 'Lost the connection. Hold the orb to try again.',
  'forget_failed': 'I couldn’t forget you just now. Please try again.',
  'invalid_message': 'Something went wrong on our side. Please try again.',
  'llm_failed': 'I couldn’t think of an answer just now. Please try again.',
  'mic_unavailable': 'Sarjy needs your microphone. Allow it in the browser, then try again.',
  'no_audio': 'I didn’t catch any audio. Hold the orb a little longer.',
  'no_speech': 'I didn’t hear any words. Hold the orb and try again.',
  'playback_failed': 'Couldn’t play the audio back.',
  'rate_limited': 'I’m getting a lot of questions right now. Please try again in a moment.',
  'stt_failed': 'I couldn’t make out what you said. Please try again.',
  'too_many_turns': 'You’re asking faster than I can keep up. Please wait a few minutes, then try again.',
  'tts_failed': 'I have an answer but couldn’t say it out loud. Please try again.',
  'turn_too_long': 'That turn was too long. Try a shorter one.',
  'unknown_voice': 'That voice isn’t available.',
  'visit_limit': 'That’s as many questions as one visit allows. Reload the page to start a new one.',
}

function App() {
  const [status, setStatus] = useState<Status>('idle')
  const [problem, setProblem] = useState<null | Problem>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [waitingForWords, setWaitingForWords] = useState(false)
  const [facts, setFacts] = useState<null | RememberedFact[]>(null)
  const [memoryOpen, setMemoryOpen] = useState(false)
  const [palette, setPalette] = useState<Palette>(initialPalette)
  const [welcomed] = useState(wantsWelcome)
  const [welcoming, setWelcoming] = useState(welcomed)
  const [orbRevealed, setOrbRevealed] = useState(!welcomed)
  const orbRef = useRef<HTMLButtonElement>(null)
  const liveMicLevel = useMicLevel(status === 'listening' && !REHEARSE)
  const micLevel = REHEARSE ? rehearsedMicLevel : liveMicLevel

  const [session] = useState<PushToTalk & Visit>(() => {
    // Each change lands on the newest turn, the one being answered.
    const updateLast = (change: Partial<Turn>): void => {
      setTurns((all) => all.map((turn, index) => (index === all.length - 1 ? { ...turn, ...change } : turn)))
    }
    const callbacks: VoiceSessionCallbacks = {
      onMemory: setFacts,
      onProblem: (next) => {
        setProblem(next)
        if (next !== null) {
          setWaitingForWords(false)
        }
      },
      onReply: (reply) => {
        updateLast({ reply })
      },
      onStatus: (next) => {
        if (next === 'thinking') {
          setWaitingForWords(true)
        }
        setStatus(next)
      },
      onTranscript: (heard) => {
        setWaitingForWords(false)
        setTurns((all) => [...all, { heard, id: all.length, reply: null, ttfaMs: null }])
      },
      onTtfa: (ttfaMs) => {
        updateLast({ ttfaMs })
      },
    }
    return REHEARSE ? new RehearsalSession(callbacks) : new VoiceSession(SOCKET_URL, callbacks)
  })

  useLayoutEffect(() => {
    applyPalette(palette)
  }, [palette])

  useEffect(() => {
    session.connect()
  }, [session])

  // Hold Space to talk, as well as the orb.
  useEffect(() => {
    const ownsKey = (event: KeyboardEvent): boolean =>
      event.code === 'Space' && (event.target === document.body || event.target === orbRef.current)
    const down = (event: KeyboardEvent): void => {
      if (ownsKey(event)) {
        event.preventDefault()
        if (!event.repeat) {
          session.press()
        }
      }
    }
    const up = (event: KeyboardEvent): void => {
      if (ownsKey(event)) {
        session.release()
      }
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
    }
  }, [session])

  const release = () => {
    session.release()
  }
  const forgetMe = () => {
    session.forgetMe()
  }
  const revealOrb = useCallback(() => {
    setOrbRevealed(true)
  }, [])
  const endWelcome = useCallback(() => {
    setWelcoming(false)
  }, [])
  const timed = turns.flatMap((turn) => (turn.ttfaMs === null ? [] : [{ id: turn.id, ttfaMs: turn.ttfaMs }]))
  const statusText = problem === null ? describe(status, waitingForWords) : PROBLEM_TEXT[problem]

  return (
    <div className="flex h-svh flex-col bg-background text-foreground">
      <header className="flex items-start justify-between gap-4 px-4 pt-4 md:px-8 md:pt-6">
        <div className="flex items-center gap-3">
          <SarjyMark className="size-10" />
          <div>
            <h1 className="font-heading text-2xl/none font-semibold tracking-tight">sarjy</h1>
            <p className="text-sm text-muted-foreground">Your Magic Experience concierge</p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <PaletteSwitcher onChange={setPalette} palette={palette} />
          {facts !== null && (
            <div className="md:hidden">
              <Button
                onClick={() => {
                  setMemoryOpen(!memoryOpen)
                }}
                size="sm"
                variant="secondary"
              >
                Remembers {facts.length}
              </Button>
            </div>
          )}
        </div>
      </header>

      <div className="flex min-h-0 flex-1 gap-8 px-4 md:px-8">
        <main className="flex min-h-0 flex-1 flex-col">
          {memoryOpen && facts !== null ? (
            <div className="pt-4 md:hidden">
              <MemoryPanel busy={status !== 'idle'} facts={facts} onForgetMe={forgetMe} orbRef={orbRef} />
            </div>
          ) : null}
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto pt-6">
            <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-end">
              <ConversationThread speaking={status === 'speaking'} turns={turns} />
            </div>
          </div>
          <div className="pb-safe flex flex-col items-center gap-1 pt-2">
            <TalkOrb
              animateIn={welcomed}
              disabled={status === 'thinking' || status === 'speaking'}
              micLevel={micLevel}
              onPress={() => {
                session.press()
              }}
              onRelease={release}
              orbRef={orbRef}
              palette={palette}
              phase={PHASE_FOR[status]}
              revealed={orbRevealed}
            />
            <p aria-live="polite" className={problem === null ? 'text-sm text-muted-foreground' : 'text-sm text-destructive'}>
              <span className="label-in inline-block" key={statusText}>
                {statusText}
              </span>
            </p>
          </div>
        </main>

        <aside className="hidden w-80 shrink-0 flex-col gap-4 overflow-y-auto pb-6 md:flex">
          {facts !== null && <MemoryPanel busy={status !== 'idle'} facts={facts} onForgetMe={forgetMe} orbRef={orbRef} />}
          <LatencyPanel turns={timed} />
        </aside>
      </div>
      {welcoming ? <FirstLoad onDocked={revealOrb} onDone={endWelcome} orbRef={orbRef} /> : null}
    </div>
  )
}

function describe(status: Status, waitingForWords: boolean): string {
  switch (status) {
    case 'idle': {
      return 'Hold to talk, or hold Space'
    }
    case 'listening': {
      return 'Listening… let go to send'
    }
    case 'speaking': {
      return 'Sarjy is speaking'
    }
    case 'thinking': {
      return waitingForWords ? 'Transcribing…' : 'Thinking…'
    }
  }
}

export default App
