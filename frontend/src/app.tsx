import { WifiDisconnected01Icon } from '@hugeicons/core-free-icons'
import { HugeiconsIcon } from '@hugeicons/react'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

import { type VoiceCatalogue, type VoiceList, VoicesClient } from '@/clients/voices-client'
import { ConversationThread, type Turn } from '@/components/conversation-thread'
import { FirstLoad, wantsWelcome } from '@/components/first-load'
import { LatencyPanel } from '@/components/latency-panel'
import { MemoryPanel } from '@/components/memory-panel'
import type { OrbPhase } from '@/components/orb-renderer'
import { applyPalette, initialPalette, type Palette, PaletteSwitcher } from '@/components/palette-switcher'
import { ProblemCards } from '@/components/problem-cards'
import { PROBLEMS, statusLine } from '@/components/problems'
import { RehearsalSession } from '@/components/rehearsal-session'
import { SarjyMark } from '@/components/sarjy-mark'
import { TalkOrb } from '@/components/talk-orb'
import { Button } from '@/components/ui/button'
import { useVoices } from '@/components/use-voices'
import { VoicePicker } from '@/components/voice-picker'
import type { RememberedFact } from '@/lib/protocol'
import {
  type AudioLevels,
  type Connection,
  type Problem,
  type PushToTalk,
  type Status,
  type Visit,
  type VoicePicker as VoiceSetter,
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
// The fact the gateway keeps the chosen voice under (D-90).
const VOICE_FACT = 'voice'

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
  // A voice just chosen, shown at once while the gateway saves it as the `voice` fact.
  const [picked, setPicked] = useState<null | string>(null)
  const orbRef = useRef<HTMLButtonElement>(null)

  const [{ catalogue, session }] = useState<{
    catalogue: VoiceCatalogue
    session: AudioLevels & PushToTalk & Visit & VoiceSetter
  }>(() => {
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
        if (next === 'unknown_voice') {
          setPicked(null)
        }
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
    if (REHEARSE_AS !== null) {
      const rehearsal = new RehearsalSession(callbacks, REHEARSE_AS === 'problems')
      return { catalogue: rehearsal, session: rehearsal }
    }
    return { catalogue: new VoicesClient(), session: new VoiceSession(SOCKET_URL, callbacks) }
  })

  const voices = useVoices(catalogue)

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
  // The voice is kept as a fact but chosen with the picker, so the memory panel leaves it out.
  const savedVoice = facts?.find((fact) => fact.key === VOICE_FACT)?.value
  const shownFacts = facts?.filter((fact) => fact.key !== VOICE_FACT) ?? null
  const voice = voices === null ? null : chosenVoice(picked ?? savedVoice, voices)
  const chooseVoice = (next: string) => {
    setPicked(next)
    session.setVoice(next)
  }
  const timed = turns.flatMap((turn) =>
    turn.ttfaMs === null ? [] : [{ id: turn.id, stages: turn.stages, ttfaMs: turn.ttfaMs }],
  )
  const line = statusLine(problem, restingText(status, waitingForWords, visitOver, reconnecting))

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
          {shownFacts !== null && (
            <div className="md:hidden">
              <Button
                onClick={() => {
                  setMemoryOpen(!memoryOpen)
                }}
                size="sm"
                variant="secondary"
              >
                Remembers {shownFacts.length}
              </Button>
            </div>
          )}
        </div>
      </header>

      <div className="flex min-h-0 flex-1 gap-8 px-4 md:px-8">
        <main className="flex min-h-0 flex-1 flex-col">
          {memoryOpen && shownFacts !== null ? (
            <div className="pt-4 md:hidden">
              <MemoryPanel busy={status !== 'idle'} facts={shownFacts} onForgetMe={forgetMe} orbRef={orbRef} />
            </div>
          ) : null}
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto pt-6">
            <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-end">
              <ConversationThread turns={turns} />
            </div>
          </div>
          <div className="pb-safe flex flex-col items-center gap-1 pt-2">
            <ProblemCards microphone={problem === 'mic_unavailable'} visitOver={visitOver} />
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
            <p aria-live="polite" className={line.trouble ? 'text-sm text-destructive' : 'text-sm text-muted-foreground'}>
              <span className="label-in inline-block" key={line.text}>
                {line.text}
              </span>
            </p>
            {voices !== null && voice !== null ? (
              <VoicePicker disabled={status !== 'idle'} onChoose={chooseVoice} voice={voice} voices={voices.voices} />
            ) : null}
          </div>
        </main>

        <aside className="hidden w-80 shrink-0 flex-col gap-4 overflow-y-auto pb-6 md:flex">
          {shownFacts !== null && <MemoryPanel busy={status !== 'idle'} facts={shownFacts} onForgetMe={forgetMe} orbRef={orbRef} />}
          <LatencyPanel turns={timed} />
        </aside>
      </div>
      {welcoming ? <FirstLoad onDocked={revealOrb} onDone={endWelcome} orbRef={orbRef} /> : null}
    </div>
  )
}

// The voice to show as chosen: the one picked or saved if TTS still offers it, else its default.
function chosenVoice(wanted: string | undefined, list: VoiceList): string {
  return wanted !== undefined && list.voices.includes(wanted) ? wanted : list.default
}

// What the line under the orb says when there is no problem to report.
function restingText(status: Status, waitingForWords: boolean, visitOver: boolean, reconnecting: boolean): string {
  if (visitOver) {
    return 'Start a new visit to ask more'
  }
  return reconnecting ? 'Waiting for the connection…' : describe(status, waitingForWords)
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
