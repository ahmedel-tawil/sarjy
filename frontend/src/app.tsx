import { Alert02Icon, MicOff01Icon, WifiDisconnected01Icon } from '@hugeicons/core-free-icons'
import { HugeiconsIcon } from '@hugeicons/react'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

import { ConversationThread, type Turn } from '@/components/conversation-thread'
import { FirstLoad, wantsWelcome } from '@/components/first-load'
import { LatencyPanel } from '@/components/latency-panel'
import { MemoryPanel } from '@/components/memory-panel'
import type { OrbPhase } from '@/components/orb-renderer'
import { applyPalette, initialPalette, type Palette, PaletteSwitcher } from '@/components/palette-switcher'
import { PROBLEMS } from '@/components/problems'
import { RehearsalSession } from '@/components/rehearsal-session'
import { SarjyMark } from '@/components/sarjy-mark'
import { TalkOrb } from '@/components/talk-orb'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import type { RememberedFact } from '@/lib/protocol'
import {
  type AudioLevels,
  type Connection,
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
// How long "Back online" shows after a dropped connection recovers.
const BACK_ONLINE_MS = 2500

const REHEARSE_AS = import.meta.env.DEV ? new URLSearchParams(window.location.search).get('rehearse') : null

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
  // Once the visit's question limit is reached, only a new visit can ask more.
  const [visitOver, setVisitOver] = useState(false)
  // A connection that was up and dropped; the socket reconnects by itself (D-90).
  const [reconnecting, setReconnecting] = useState(false)
  const [backOnline, setBackOnline] = useState(false)
  const orbRef = useRef<HTMLButtonElement>(null)

  const [session] = useState<AudioLevels & PushToTalk & Visit>(() => {
    // Each change lands on the newest turn, the one being answered.
    const updateLast = (change: (turn: Turn) => Partial<Turn>): void => {
      setTurns((all) => all.map((turn, index) => (index === all.length - 1 ? { ...turn, ...change(turn) } : turn)))
    }
    let wasOnline = false
    let nextId = 0
    // The turn whose question was heard but whose answer has not started yet: a problem
    // until then belongs to it, and is noted on it in the conversation.
    let answering: null | number = null
    const callbacks: VoiceSessionCallbacks = {
      // The first connection as the page opens says nothing; only a drop and its recovery do.
      onConnection: (connection: Connection) => {
        if (connection === 'online') {
          if (wasOnline) {
            setBackOnline(true)
            window.setTimeout(() => {
              setBackOnline(false)
            }, BACK_ONLINE_MS)
          }
          wasOnline = true
          setReconnecting(false)
        } else if (wasOnline) {
          setReconnecting(true)
        }
      },
      onMemory: setFacts,
      onProblem: (next) => {
        if (next === null) {
          setProblem(null)
          return
        }
        setWaitingForWords(false)
        if (next === 'visit_limit') {
          setVisitOver(true)
        }
        const spoiled = answering
        if (PROBLEMS[next].kind === 'turn' && spoiled !== null) {
          answering = null
          setTurns((all) => all.map((turn) => (turn.id === spoiled ? { ...turn, trouble: PROBLEMS[next].text } : turn)))
          setProblem(null)
          return
        }
        setProblem(next)
      },
      onReply: (reply, links) => {
        updateLast(() => ({ links, reply }))
      },
      onSpeak: (text, durationMs) => {
        answering = null
        updateLast((turn) => ({ clips: [...turn.clips, { durationMs, text }] }))
      },
      onStatus: (next) => {
        if (next === 'thinking') {
          setWaitingForWords(true)
        }
        setStatus(next)
      },
      onTranscript: (heard) => {
        setWaitingForWords(false)
        const id = nextId
        nextId += 1
        answering = id
        setTurns((all) => [...all, { clips: [], heard, id, links: [], reply: null, stages: null, trouble: null, ttfaMs: null }])
      },
      onStages: (stages) => {
        updateLast(() => ({ stages }))
      },
      onTtfa: (ttfaMs) => {
        updateLast(() => ({ ttfaMs }))
      },
    }
    return REHEARSE_AS === null ? new VoiceSession(SOCKET_URL, callbacks) : new RehearsalSession(callbacks, REHEARSE_AS === 'problems')
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
  const timed = turns.flatMap((turn) =>
    turn.ttfaMs === null ? [] : [{ id: turn.id, stages: turn.stages, ttfaMs: turn.ttfaMs }],
  )
  const shown = problem === null ? null : PROBLEMS[problem]
  const inLine = shown !== null && (shown.kind === 'hint' || shown.kind === 'trouble') ? shown : null
  const idleText = visitOver ? 'Start a new visit to ask more' : reconnecting ? 'Waiting for the connection…' : describe(status, waitingForWords)
  const statusText = inLine === null ? idleText : inLine.text

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
          <p aria-live="polite" className="flex items-center gap-1.5 text-xs text-muted-foreground">
            {reconnecting ? (
              <>
                <HugeiconsIcon className="size-4" icon={WifiDisconnected01Icon} />
                Reconnecting…
              </>
            ) : null}
            {backOnline && !reconnecting ? 'Back online' : null}
          </p>
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
              <ConversationThread turns={turns} />
            </div>
          </div>
          <div className="pb-safe flex flex-col items-center gap-1 pt-2">
            {shown?.kind === 'microphone' ? (
              <div className="w-full max-w-md pb-3">
                <Alert>
                  <HugeiconsIcon icon={MicOff01Icon} />
                  <AlertTitle>Sarjy can’t hear you yet</AlertTitle>
                  <AlertDescription>{shown.text}</AlertDescription>
                </Alert>
              </div>
            ) : null}
            {visitOver ? (
              <div className="w-full max-w-md pb-3">
                <Alert>
                  <HugeiconsIcon icon={Alert02Icon} />
                  <AlertTitle>This visit is full</AlertTitle>
                  <AlertDescription>{PROBLEMS['visit_limit'].text}</AlertDescription>
                  <div className="col-start-2 pt-2">
                    <Button
                      onClick={() => {
                        window.location.reload()
                      }}
                      size="sm"
                    >
                      Start a new visit
                    </Button>
                  </div>
                </Alert>
              </div>
            ) : null}
            <TalkOrb
              animateIn={welcomed}
              disabled={visitOver || reconnecting || status === 'thinking' || status === 'speaking'}
              levels={session}
              onPress={() => {
                session.press()
              }}
              onRelease={release}
              orbRef={orbRef}
              palette={palette}
              phase={PHASE_FOR[status]}
              revealed={orbRevealed}
            />
            <p aria-live="polite" className={inLine?.kind === 'trouble' ? 'text-sm text-destructive' : 'text-sm text-muted-foreground'}>
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
