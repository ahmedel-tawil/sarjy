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

// What the page knows about the turn waiting for its answer, filled in as the gateway's
// messages arrive.
interface TurnInFlight {
  // Held until the audio starts, so the words and the voice appear together.
  reply: null | string
  // performance.now() at the release that ended the turn.
  speechEnd: number
  // The gateway names the turn in a JSON message just before its binary audio frame.
  turnId: null | string
}

export class VoiceSession implements PushToTalk {
  readonly #callbacks: VoiceSessionCallbacks
  readonly #player = new Player()
  readonly #recorder = new Recorder()
  // Counted rather than flagged, so press() can tell whether a release happened while
  // it was waiting for the microphone.
  #releases = 0
  readonly #socket: VoiceSocket
  #status: Status = 'idle'
  #turn: null | TurnInFlight = null

  constructor(url: string, callbacks: VoiceSessionCallbacks) {
    this.#callbacks = callbacks
    this.#socket = new VoiceSocket(url, {
      onAudio: (audio) => {
        this.#speak(audio).catch(() => {
          this.#report('playback_failed')
        })
      },
      onClose: () => {
        // A phone that sleeps or a deploy closes an idle socket, and the next press opens a
        // new one, so only a turn still waiting for its answer has lost anything.
        if (this.#status === 'listening' || this.#status === 'thinking') {
          this.#report('connection_lost')
        }
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
    this.#turn = { reply: null, speechEnd: performance.now(), turnId: null }
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
        if (this.#turn !== null) {
          this.#turn.turnId = message['turn_id']
        }
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
        if (this.#turn !== null) {
          this.#turn.reply = message.text
        }
        break
      }
      case 'transcript': {
        this.#callbacks.onTranscript(message.text)
        break
      }
    }
  }

  #report(problem: Problem): void {
    // A reply whose voice never came is still worth reading.
    const reply = this.#turn?.reply ?? null
    if (reply !== null) {
      this.#callbacks.onReply(reply)
    }
    this.#turn = null
    this.#setStatus('idle')
    this.#callbacks.onProblem(problem)
  }

  #setStatus(status: Status): void {
    this.#status = status
    this.#callbacks.onStatus(status)
  }

  async #speak(audio: ArrayBuffer): Promise<void> {
    await this.#player.play(audio, () => {
      const playbackStart = performance.now()
      const turn = this.#turn
      this.#turn = null
      this.#setStatus('speaking')
      if (turn === null) {
        return
      }
      if (turn.reply !== null) {
        this.#callbacks.onReply(turn.reply)
      }
      if (turn.turnId !== null) {
        this.#socket.sendMarks(turn.turnId, turn.speechEnd, playbackStart)
        this.#callbacks.onTtfa(playbackStart - turn.speechEnd)
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
