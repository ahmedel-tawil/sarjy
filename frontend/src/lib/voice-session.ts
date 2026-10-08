import { Player } from './player'
import type { ErrorCode, ServerMessage } from './protocol'
import { Recorder, type Recording } from './recorder'
import { VoiceSocket } from './voice-socket'

// A press shorter than this is a tap, not a question.
const MIN_RECORDING_MS = 300

// Browsers suppress background noise on the microphone, so a silent room sits well below
// this level and speech well above it (D-55).
const SPEECH_DBFS = -45

export type Status = 'idle' | 'listening' | 'speaking' | 'thinking'

export type Problem = 'connection_lost' | 'mic_unavailable' | 'playback_failed' | ErrorCode

export interface VoiceSessionCallbacks {
  onProblem: (problem: null | Problem) => void
  onReply: (text: string) => void
  onStatus: (status: Status) => void
  onTranscript: (text: string) => void
  // Time to first audio: from the button release to the first sample of the reply.
  onTtfa: (milliseconds: number) => void
}

export interface PushToTalk {
  press(): void
  release(): void
}

export class VoiceSession implements PushToTalk {
  // The gateway names the turn in a JSON message just before its binary audio frame.
  #audioTurnId: null | string = null
  readonly #callbacks: VoiceSessionCallbacks
  readonly #player = new Player()
  readonly #recorder = new Recorder()
  // Counted rather than flagged, so press() can tell whether a release happened while
  // it was waiting for the microphone.
  #releases = 0
  readonly #socket: VoiceSocket
  // performance.now() at the release that ended the turn in flight.
  #speechEnd: null | number = null
  #status: Status = 'idle'

  constructor(url: string, callbacks: VoiceSessionCallbacks) {
    this.#callbacks = callbacks
    this.#socket = new VoiceSocket(url, {
      onAudio: (audio) => {
        this.#speak(audio).catch(() => {
          this.#report('playback_failed')
        })
      },
      onClose: () => {
        this.#report('connection_lost')
      },
      onMessage: (message) => {
        this.#receive(message)
      },
    })
  }

  press(): void {
    // One turn at a time: each speech_end must pair with the audio of its own reply.
    if (this.#status !== 'idle') {
      return
    }
    this.#callbacks.onProblem(null)
    this.#startRecording().catch(() => {
      this.#report('mic_unavailable')
    })
  }

  release(): void {
    this.#releases += 1
    if (!this.#recorder.recording) {
      return
    }
    this.#speechEnd = performance.now()
    this.#setStatus('thinking')
    this.#endTurn().catch(() => {
      this.#report('connection_lost')
    })
  }

  async #endTurn(): Promise<void> {
    const recording = await this.#recorder.stop()
    if (heardSpeech(recording)) {
      this.#socket.endTurn()
    } else {
      this.#socket.cancelTurn()
      this.#report('no_speech')
    }
  }

  #receive(message: ServerMessage): void {
    switch (message.type) {
      case 'audio': {
        this.#audioTurnId = message['turn_id']
        break
      }
      case 'error': {
        this.#report(message.code)
        break
      }
      case 'marks': {
        // The latency waterfall (M3.2) draws these; the gateway already logs them.
        break
      }
      case 'reply': {
        this.#callbacks.onReply(message.text)
        break
      }
      case 'transcript': {
        this.#callbacks.onTranscript(message.text)
        break
      }
    }
  }

  #report(problem: Problem): void {
    this.#audioTurnId = null
    this.#speechEnd = null
    this.#setStatus('idle')
    this.#callbacks.onProblem(problem)
  }

  #setStatus(status: Status): void {
    this.#status = status
    this.#callbacks.onStatus(status)
  }

  async #speak(audio: ArrayBuffer): Promise<void> {
    const turnId = this.#audioTurnId
    const speechEnd = this.#speechEnd
    this.#audioTurnId = null
    this.#speechEnd = null
    await this.#player.play(audio, () => {
      const playbackStart = performance.now()
      this.#setStatus('speaking')
      if (turnId !== null && speechEnd !== null) {
        this.#socket.sendMarks(turnId, speechEnd, playbackStart)
        this.#callbacks.onTtfa(playbackStart - speechEnd)
      }
    })
    this.#setStatus('idle')
  }

  async #startRecording(): Promise<void> {
    const releasesBefore = this.#releases
    const context = await this.#player.unlock()
    await this.#recorder.prepare(context)
    // Released while the permission prompt was open: wait for the next press.
    if (this.#releases !== releasesBefore) {
      return
    }
    this.#recorder.start((chunk) => {
      this.#socket.sendAudio(chunk)
    })
    this.#setStatus('listening')
  }
}

function heardSpeech(recording: Recording): boolean {
  if (recording.durationMs < MIN_RECORDING_MS) {
    return false
  }
  // Without a measurement, let the turn through rather than lose real speech.
  return recording.loudestDbfs === null || recording.loudestDbfs >= SPEECH_DBFS
}
