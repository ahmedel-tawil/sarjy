import { LevelMeter } from './level-meter'

// Chrome records Opus in WebM; Safari only records AAC in MP4.
const MIME_TYPES = ['audio/webm;codecs=opus', 'audio/mp4'] as const

// Short chunks let the upload overlap speech instead of starting at release.
const CHUNK_MS = 250

export interface AudioRecorder {
  // The microphone's level right now while recording, from 0 to 1; 0 otherwise.
  level(): number
  prepare(context: AudioContext): Promise<void>
  readonly recording: boolean
  start(onChunk: (chunk: Blob) => void): void
  stop(): Promise<Recording>
}

export interface Recording {
  durationMs: number
  // The loudest moment in dBFS, or null when the level could not be measured.
  loudestDbfs: null | number
}

export class Recorder implements AudioRecorder {
  #meter: LevelMeter | null = null
  #recorder: MediaRecorder | null = null
  #startedAt = 0
  #stream: MediaStream | null = null

  get recording(): boolean {
    return this.#recorder !== null
  }

  level(): number {
    return this.#recorder === null || this.#meter === null ? 0 : this.#meter.current()
  }

  // The first call shows the permission prompt; later turns reuse the stream while it
  // still hears. iOS ends or mutes it when the screen locks, and recording it then would
  // send silence, so it is asked for again (D-85). The meter shares the player's context.
  async prepare(context: AudioContext): Promise<void> {
    if (this.#stream !== null && hears(this.#stream)) {
      return
    }
    if (this.#stream !== null) {
      for (const track of this.#stream.getTracks()) {
        track.stop()
      }
    }
    this.#stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    this.#meter = new LevelMeter(context, this.#stream)
  }

  start(onChunk: (chunk: Blob) => void): void {
    if (this.#stream === null || this.#meter === null) {
      throw new Error('call prepare() before start()')
    }
    const mimeType = MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type))
    const recorder = new MediaRecorder(this.#stream, mimeType === undefined ? undefined : { mimeType })
    recorder.addEventListener('dataavailable', (event) => {
      if (event.data.size > 0) {
        onChunk(event.data)
      }
    })
    recorder.start(CHUNK_MS)
    this.#meter.start()
    this.#startedAt = performance.now()
    this.#recorder = recorder
  }

  async stop(): Promise<Recording> {
    const recorder = this.#recorder
    this.#recorder = null
    const recording = {
      durationMs: performance.now() - this.#startedAt,
      loudestDbfs: this.#meter === null ? null : this.#meter.stop(),
    }
    if (recorder === null || recorder.state === 'inactive') {
      return recording
    }
    // "stop" fires after the last chunk, so the caller can end the turn safely.
    const stopped = new Promise<void>((resolve) => {
      recorder.addEventListener('stop', () => {
        resolve()
      }, { once: true })
    })
    recorder.stop()
    await stopped
    return recording
  }
}

function hears(stream: MediaStream): boolean {
  return stream.getAudioTracks().some((track) => track.readyState === 'live' && !track.muted)
}
