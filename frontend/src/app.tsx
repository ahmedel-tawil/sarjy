import { Mic01Icon } from '@hugeicons/core-free-icons'
import { HugeiconsIcon } from '@hugeicons/react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { EchoSession, type Problem, type Status } from '@/lib/echo-session'

const SOCKET_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`

const STATUS_TEXT: Record<Status, string> = {
  idle: 'Hold the button and speak',
  listening: 'Listening… let go to send',
  playing: 'Playing back what you said',
  waiting: 'Sending…',
}

const PROBLEM_TEXT: Record<Problem, string> = {
  'connection_lost': 'Lost the connection. Hold the button to try again.',
  'invalid_message': 'Something went wrong on our side. Please try again.',
  'mic_unavailable': 'Sarjy needs your microphone. Allow it in the browser, then try again.',
  'no_audio': 'I didn’t catch any audio. Hold the button a little longer.',
  'playback_failed': 'Couldn’t play the audio back.',
  'turn_too_long': 'That turn was too long. Try a shorter one.',
}

function App() {
  const [status, setStatus] = useState<Status>('idle')
  const [problem, setProblem] = useState<null | Problem>(null)
  const [session] = useState(() => new EchoSession(SOCKET_URL, { onProblem: setProblem, onStatus: setStatus }))

  const release = () => {
    session.release()
  }

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 p-6">
      <h1 className="font-heading text-4xl font-medium">Sarjy</h1>
      {/* Holding a button on a phone would otherwise scroll, select text or open a menu. */}
      <div className="touch-none select-none">
        <Button
          aria-pressed={status === 'listening'}
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
    </main>
  )
}

export default App
