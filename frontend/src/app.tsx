import { Mic01Icon } from '@hugeicons/core-free-icons'
import { HugeiconsIcon } from '@hugeicons/react'
import { useEffect, useState } from 'react'

import { MemoryPanel } from '@/components/memory-panel'
import { Button } from '@/components/ui/button'
import type { RememberedFact } from '@/lib/protocol'
import { type Problem, type Status, VoiceSession } from '@/lib/voice-session'

const SOCKET_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`

const STATUS_TEXT: Record<Status, string> = {
  idle: 'Hold the button and speak',
  listening: 'Listening… let go to send',
  speaking: 'Sarjy is speaking',
  thinking: 'Thinking…',
}

const PROBLEM_TEXT: Record<Problem, string> = {
  'connection_lost': 'Lost the connection. Hold the button to try again.',
  'forget_failed': 'I couldn’t forget you just now. Please try again.',
  'invalid_message': 'Something went wrong on our side. Please try again.',
  'llm_failed': 'I couldn’t think of an answer just now. Please try again.',
  'mic_unavailable': 'Sarjy needs your microphone. Allow it in the browser, then try again.',
  'no_audio': 'I didn’t catch any audio. Hold the button a little longer.',
  'no_speech': 'I didn’t hear any words. Hold the button and try again.',
  'playback_failed': 'Couldn’t play the audio back.',
  'rate_limited': 'I’m getting a lot of questions right now. Please try again in a moment.',
  'stt_failed': 'I couldn’t make out what you said. Please try again.',
  'tts_failed': 'I have an answer but couldn’t say it out loud. Please try again.',
  'turn_too_long': 'That turn was too long. Try a shorter one.',
  'unknown_voice': 'That voice isn’t available.',
}

function App() {
  const [status, setStatus] = useState<Status>('idle')
  const [problem, setProblem] = useState<null | Problem>(null)
  const [heard, setHeard] = useState<null | string>(null)
  const [reply, setReply] = useState<null | string>(null)
  const [ttfa, setTtfa] = useState<null | number>(null)
  // Unknown until the gateway sends the first memory message.
  const [facts, setFacts] = useState<null | RememberedFact[]>(null)
  const [session] = useState(
    () =>
      new VoiceSession(SOCKET_URL, {
        onMemory: setFacts,
        onProblem: setProblem,
        onReply: setReply,
        onStatus: setStatus,
        onTranscript: (text) => {
          setHeard(text)
          setReply(null)
          setTtfa(null)
        },
        onTtfa: setTtfa,
      }),
  )

  useEffect(() => {
    session.connect()
  }, [session])

  const release = () => {
    session.release()
  }

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 p-6">
      <h1 className="font-heading text-4xl font-medium">Sarjy</h1>
      {heard !== null && (
        <section aria-label="Last exchange" className="flex max-w-prose flex-col gap-3 text-center">
          <p className="text-muted-foreground">“{heard}”</p>
          {reply !== null && <p className="text-lg text-pretty">{reply}</p>}
          {ttfa !== null && (
            <p className="text-sm text-muted-foreground tabular-nums">
              First audio after {(ttfa / 1000).toFixed(1)} s
            </p>
          )}
        </section>
      )}
      {/* Holding a button on a phone would otherwise scroll, select text or open a menu. */}
      <div className="touch-none select-none">
        <Button
          aria-pressed={status === 'listening'}
          disabled={status === 'thinking' || status === 'speaking'}
          onContextMenu={(event) => {
            event.preventDefault()
          }}
          onPointerCancel={release}
          onPointerDown={() => {
            session.press()
          }}
          onPointerLeave={release}
          onPointerUp={release}
          size="lg"
        >
          <HugeiconsIcon icon={Mic01Icon} />
          Hold to talk
        </Button>
      </div>
      <p aria-live="polite" className={problem === null ? 'text-muted-foreground' : 'text-destructive'}>
        {problem === null ? STATUS_TEXT[status] : PROBLEM_TEXT[problem]}
      </p>
      {facts !== null && (
        <MemoryPanel
          busy={status !== 'idle'}
          facts={facts}
          onForgetMe={() => {
            session.forgetMe()
          }}
        />
      )}
    </main>
  )
}

export default App
