import { Player } from './player'
import type { ServerError } from './protocol'
import { Recorder } from './recorder'
import { VoiceSocket } from './voice-socket'

export type Status = 'idle' | 'listening' | 'playing' | 'waiting'

export type Problem = 'connection_lost' | 'mic_unavailable' | 'playback_failed' | ServerError['code']

export interface EchoSessionCallbacks {
  onProblem: (problem: null | Problem) => void
  onStatus: (status: Status) => void
}

export interface PushToTalk {
  press(): void
  release(): void
}

export class EchoSession implements PushToTalk {
  readonly #callbacks: EchoSessionCallbacks
  readonly #player = new Player()
  readonly #recorder = new Recorder()
  // Counted rather than flagged, so press() can tell whether a release happened while
  // it was waiting for the microphone.
  #releases = 0
  readonly #socket: VoiceSocket

  constructor(url: string, callbacks: EchoSessionCallbacks) {
    this.#callbacks = callbacks
    this.#socket = new VoiceSocket(url, {
      onAudio: (audio) => {
        this.#playBack(audio).catch(() => {
          this.#report('playback_failed')
        })
      },
      onClose: () => {
        this.#report('connection_lost')
      },
      onError: (error) => {
        this.#report(error.code)
      },
    })
  }

  press(): void {
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
    this.#callbacks.onStatus('waiting')
    this.#endTurn().catch(() => {
      this.#report('connection_lost')
    })
  }

  async #startRecording(): Promise<void> {
    const releasesBefore = this.#releases
    await this.#player.unlock()
    await this.#recorder.prepare()
    // Released while the permission prompt was open: wait for the next press.
    if (this.#releases !== releasesBefore) {
      return
    }
    this.#recorder.start((chunk) => {
      this.#socket.sendAudio(chunk)
    })
    this.#callbacks.onStatus('listening')
  }

  async #endTurn(): Promise<void> {
    await this.#recorder.stop()
    this.#socket.endTurn()
  }

  async #playBack(audio: ArrayBuffer): Promise<void> {
    this.#callbacks.onStatus('playing')
    await this.#player.play(audio)
    this.#callbacks.onStatus('idle')
  }

  #report(problem: Problem): void {
    this.#callbacks.onStatus('idle')
    this.#callbacks.onProblem(problem)
  }
}
