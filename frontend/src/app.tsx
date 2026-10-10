import { AiVoiceIcon, WifiDisconnected01Icon } from '@hugeicons/core-free-icons'
import { HugeiconsIcon } from '@hugeicons/react'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

import { type VoiceCatalogue, type VoiceList, VoicesClient } from '@/clients/voices-client'
import { ConversationThread, type Turn } from '@/components/conversation-thread'
import { EarlierVisits, type Replay } from '@/components/earlier-visits'
import { FirstLoad, wantsWelcome } from '@/components/first-load'
import { LatencyPanel } from '@/components/latency-panel'
import { MemoryPanel } from '@/components/memory-panel'
import type { OrbPhase } from '@/components/orb-renderer'
import { applyPalette, initialPalette, type Palette, PaletteSwitcher } from '@/components/palette-switcher'
import { ProblemCards } from '@/components/problem-cards'
import { PROBLEMS, statusLine } from '@/components/problems'
import { RehearsalSession } from '@/components/rehearsal-session'
import { SarjyMark } from '@/components/sarjy-mark'
import { SettingsMenu } from '@/components/settings-menu'
import { HAS_KEYBOARD, initialTalkMode, saveTalkMode, type TalkMode } from '@/components/talk-mode'
import { TalkOrb } from '@/components/talk-orb'
import { Button } from '@/components/ui/button'
import { useTalkControls } from '@/components/use-talk-controls'
import { useVoices } from '@/components/use-voices'
import { VoiceMode } from '@/components/voice-mode'
import type { EarlierVisit, RememberedFact } from '@/lib/protocol'
import {
  type AudioLevels,
  type Connection,
  type Problem,
  type PushToTalk,
  type Replayer,
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
// The line under the orb, which also describes the orb to screen readers (D-83).
const STATUS_LINE_ID = 'orb-status'

// The fact the gateway keeps the chosen voice under (D-90).
const VOICE_FACT = 'voice'

// How long "Back online" shows after a dropped connection recovers.
const BACK_ONLINE_MS = 2500

// The line under the orb at rest, with Space only where there is a keyboard.
const RESTING: Readonly<Record<TalkMode, string>> = HAS_KEYBOARD
  ? { hold: 'Hold to talk, or hold Space', tap: 'Tap to talk, or press Space' }
  : { hold: 'Hold to talk', tap: 'Tap to talk' }

const REHEARSE_AS = import.meta.env.DEV ? new URLSearchParams(window.location.search).get('rehearse') : null

// In development, ?concept=voice opens concept two, a full-screen voice mode for phones; it
// works with ?rehearse too. Production builds never show it.
const VOICE_CONCEPT = import.meta.env.DEV && new URLSearchParams(window.location.search).get('concept') === 'voice'

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
  // The visitor's earlier visits, newest first, and the earlier answer being replayed (D-84).
  const [history, setHistory] = useState<EarlierVisit[]>([])
  const [replay, setReplay] = useState<null | Replay>(null)
  // What Sarjy is doing right now, from the tool loop: "Checking tomorrow's weather in
  // Dubai" (D-94). Cleared when it starts speaking again and when the turn ends.
  const [activity, setActivity] = useState<null | string>(null)
  const [talkMode, setTalkMode] = useState<TalkMode>(initialTalkMode)
  const [voiceMode, setVoiceMode] = useState(VOICE_CONCEPT)
  const orbRef = useRef<HTMLButtonElement>(null)

  const [{ catalogue, session, startReplay }] = useState<{
    catalogue: VoiceCatalogue
    session: AudioLevels & PushToTalk & Replayer & Visit & VoiceSetter
    startReplay: (turnId: string) => void
  }>(() => {
    // Each change lands on the newest turn, the one being answered.
    const updateLast = (change: (turn: Turn) => Partial<Turn>): void => {
      setTurns((all) => all.map((turn, index) => (index === all.length - 1 ? { ...turn, ...change(turn) } : turn)))
    }
    let wasOnline = false
    let nextId = 0
    // A replay's clips belong to the earlier answer being replayed, not to today's last turn.
    let replayingId: null | string = null
    // The turn whose question was heard but whose answer has not started yet: a problem
    // until then belongs to it, and is noted on it in the conversation.
    let answering: null | number = null
    const callbacks: VoiceSessionCallbacks = {
      onActivity: setActivity,
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
      onHistory: setHistory,
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
        setActivity(null)
        const replayed = replayingId
        if (replayed !== null) {
          setReplay((current) => (current?.turnId === replayed ? { ...current, clips: [...current.clips, { durationMs, startedAt: performance.now(), text }] } : current))
          return
        }
        answering = null
        updateLast((turn) => ({ clips: [...turn.clips, { durationMs, startedAt: performance.now(), text }] }))
      },
      onStatus: (next) => {
        if (next === 'thinking') {
          setWaitingForWords(true)
        }
        if (next === 'idle') {
          replayingId = null
          setReplay(null)
          setActivity(null)
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
    const rehearsal = REHEARSE_AS === null ? null : new RehearsalSession(callbacks, REHEARSE_AS === 'problems')
    const visit = rehearsal ?? new VoiceSession(SOCKET_URL, callbacks)
    const replayAnswer = (turnId: string): void => {
      replayingId = turnId
      setReplay({ clips: [], turnId })
      visit.replay(turnId)
    }
    return { catalogue: rehearsal ?? new VoicesClient(), session: visit, startReplay: replayAnswer }
  })

  const voices = useVoices(catalogue)
  const talk = useTalkControls({ orbRef, paused: welcoming, session, status, talkMode })

  useLayoutEffect(() => {
    applyPalette(palette)
  }, [palette])

  useEffect(() => {
    session.connect()
  }, [session])


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
  const line = statusLine(problem, restingText({ activity, reconnecting, replaying: replay !== null, status, talkMode, visitOver, waitingForWords }))
  const chooseTalkMode = (mode: TalkMode) => {
    setTalkMode(mode)
    saveTalkMode(mode)
  }
  const talkDisabled = visitOver || reconnecting || status === 'thinking' || status === 'speaking'
  const orb = (
    <TalkOrb
      animateIn={welcomed}
      describedBy={STATUS_LINE_ID}
      disabled={talkDisabled}
      label={orbLabel(talkMode, status)}
      levels={session}
      onPress={talk.onPress}
      onRelease={talk.onRelease}
      orbRef={orbRef}
      palette={palette}
      phase={PHASE_FOR[status]}
      revealed={orbRevealed}
    />
  )
  const cards = <ProblemCards microphone={problem === 'mic_unavailable'} visitOver={visitOver} />

  if (voiceMode) {
    return (
      <div className="bg-background text-foreground">
        <div className="contents" inert={welcoming}>
          <VoiceMode
            cards={cards}
            disabled={talkDisabled}
            levels={session}
            line={{ id: STATUS_LINE_ID, ...line }}
            onClose={() => {
              setVoiceMode(false)
            }}
            onPress={talk.onPress}
            onRelease={talk.onRelease}
            orb={orb}
            settings={
              <SettingsMenu
                busy={status !== 'idle'}
                colours={{ onChange: setPalette, palette }}
                large
                onTalkMode={chooseTalkMode}
                onVoice={chooseVoice}
                talkMode={talkMode}
                voice={voice}
                voices={voices?.voices ?? null}
              />
            }
            status={status}
            talkMode={talkMode}
            turn={turns.at(-1)}
          />
        </div>
        {welcoming ? <FirstLoad onDocked={revealOrb} onDone={endWelcome} orbRef={orbRef} /> : null}
      </div>
    )
  }

  return (
    <div className="flex h-svh flex-col bg-background text-foreground">
      {/* While the welcome covers the page, nothing under it takes focus. */}
      <div className="contents" inert={welcoming}>
      <header className="flex items-start justify-between gap-4 px-4 pt-4 md:px-8 md:pt-6">
        <div className="flex items-center gap-3">
          <SarjyMark className="size-10" />
          <div>
            <h1 className="font-heading text-2xl/none font-semibold tracking-tight">sarjy</h1>
            <p className="text-sm text-muted-foreground">Your Magic Experience concierge</p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-1">
            {VOICE_CONCEPT ? (
              <Button
                aria-label="Voice mode"
                onClick={() => {
                  setVoiceMode(true)
                }}
                size="icon-sm"
                title="Voice mode"
                variant="ghost"
              >
                <HugeiconsIcon icon={AiVoiceIcon} />
              </Button>
            ) : null}
            <PaletteSwitcher onChange={setPalette} palette={palette} />
            <SettingsMenu
              busy={status !== 'idle'}
              onTalkMode={chooseTalkMode}
              onVoice={chooseVoice}
              talkMode={talkMode}
              voice={voice}
              voices={voices?.voices ?? null}
            />
          </div>
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
              {history.length > 0 ? (
                <EarlierVisits busy={status !== 'idle' || visitOver} onReplay={startReplay} replay={replay} visits={history} />
              ) : null}
              <ConversationThread returning={history.length > 0} talkMode={talkMode} turns={turns} />
            </div>
          </div>
          <div className="pb-safe flex flex-col items-center gap-1 pt-2">
            {cards}
            {orb}
            <p aria-live="polite" className={line.trouble ? 'text-sm text-destructive' : 'text-sm text-muted-foreground'} id={STATUS_LINE_ID}>
              <span className="label-in inline-block" key={line.text}>
                {line.text}
              </span>
            </p>
          </div>
        </main>

        <aside className="hidden w-80 shrink-0 flex-col gap-4 overflow-y-auto pb-6 md:flex">
          {shownFacts !== null && <MemoryPanel busy={status !== 'idle'} facts={shownFacts} onForgetMe={forgetMe} orbRef={orbRef} />}
          <LatencyPanel turns={timed} />
        </aside>
      </div>
      </div>
      {welcoming ? <FirstLoad onDocked={revealOrb} onDone={endWelcome} orbRef={orbRef} /> : null}
    </div>
  )
}

// The voice to show as chosen: the one picked or saved if TTS still offers it, else its default.
function chosenVoice(wanted: string | undefined, list: VoiceList): string {
  return wanted !== undefined && list.voices.includes(wanted) ? wanted : list.default
}

interface Moment {
  // The tool Sarjy is running, said in words; it can follow a short spoken filler (D-94).
  activity: null | string
  reconnecting: boolean
  // An earlier answer is being spoken again, rather than a new one (D-84).
  replaying: boolean
  status: Status
  talkMode: TalkMode
  visitOver: boolean
  waitingForWords: boolean
}

// What the line under the orb says when there is no problem to report.
function restingText(moment: Moment): string {
  if (moment.visitOver) {
    return 'Start a new visit to ask more'
  }
  if (moment.reconnecting) {
    return 'Waiting for the connection…'
  }
  if (moment.activity !== null) {
    return moment.activity
  }
  if (moment.replaying) {
    return moment.status === 'speaking' ? 'Sarjy is replaying an earlier answer' : 'Getting that answer ready…'
  }
  return describe(moment.status, moment.waitingForWords, moment.talkMode)
}

// The orb's name for screen readers, which changes in tap mode once it is listening.
function orbLabel(talkMode: TalkMode, status: Status): string {
  if (talkMode === 'hold') {
    return 'Hold to talk to Sarjy'
  }
  return status === 'listening' ? 'Tap to send' : 'Tap to talk to Sarjy'
}

function describe(status: Status, waitingForWords: boolean, talkMode: TalkMode): string {
  switch (status) {
    case 'idle': {
      return RESTING[talkMode]
    }
    case 'listening': {
      return talkMode === 'hold' ? 'Listening… let go to send' : 'Listening… tap again to send'
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
