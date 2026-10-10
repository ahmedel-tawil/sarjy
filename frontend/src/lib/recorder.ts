import { LevelMeter } from './level-meter'

// Chrome records Opus in WebM; Safari only records AAC in MP4.
const MIME_TYPES = ['audio/webm;codecs=opus', 'audio/mp4'] as const

// Short chunks let the upload overlap speech instead of starting at release.
const CHUNK_MS = 250

// Safari's Audio Session API, which TypeScript's DOM types don't have yet.
type AudioSessionType = 'auto' | 'playback'

declare global {
  interface Navigator {
    readonly audioSession?: { type: AudioSessionType }
  }
}

export interface AudioRecorder {
  // Closes the microphone, so the browser stops showing it in use. A recording still
  // running ends there, and its last chunk is dropped.
  close(): void
  // The microphone's level right now while recording, from 0 to 1; 0 otherwise.
  level(): number
  // Opens the microphone for one question; the first time shows the permission prompt.
  open(context: AudioContext): Promise<void>
  readonly recording: boolean
  start(onChunk: (chunk: Blob) => void): void
  // Ends the recording once its last chunk is out, then closes the microphone.
  stop(): Promise<Recording>
}

export interface Recording {
  durationMs: number
  // The loudest moment in dBFS, or null when the level could not be measured.
  loudestDbfs: null | number
}

// The microphone is open only while Sarjy listens, so the browser and the system show it
// in use only then (D-86).
export class Recorder implements AudioRecorder {
  #meter: LevelMeter | null = null
  #recorder: MediaRecorder | null = null
  #startedAt = 0
  #stream: MediaStream | null = null

  get recording(): boolean {
    return this.#recorder !== null
  }

  close(): void {
    if (this.#recorder !== null && this.#recorder.state !== 'inactive') {
      this.#recorder.stop()
    }
    this.#recorder = null
    this.#meter?.close()
    this.#meter = null
    if (this.#stream !== null) {
      for (const track of this.#stream.getTracks()) {
        track.stop()
      }
      this.#stream = null
    }
    // With the microphone closed, an iPhone's silent switch would mute Sarjy's voice.
    setAudioSession('playback')
  }

  level(): number {
    return this.#recorder === null || this.#meter === null ? 0 : this.#meter.current()
  }

  // The meter shares the player's audio context.
  async open(context: AudioContext): Promise<void> {
    // Lets Safari pick its recording mode while the microphone is open.
    setAudioSession('auto')
    this.#stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    this.#meter = new LevelMeter(context, this.#stream)
  }

  start(onChunk: (chunk: Blob) => void): void {
    const stream = this.#stream
    if (stream === null || this.#meter === null) {
      throw new Error('call open() before start()')
    }
    const mimeType = MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type))
    const recorder = new MediaRecorder(stream, mimeType === undefined ? undefined : { mimeType })
    recorder.addEventListener('dataavailable', (event) => {
      // Once close() has run, the chunk has no turn left to join.
      if (event.data.size > 0 && this.#stream === stream) {
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
    if (recorder !== null && recorder.state !== 'inactive') {
      // "stop" fires after the last chunk, so the caller can end the turn safely.
      const stopped = new Promise<void>((resolve) => {
        recorder.addEventListener('stop', () => {
          resolve()
        }, { once: true })
      })
      recorder.stop()
      await stopped
    }
    this.close()
    return recording
  }
}

function setAudioSession(type: AudioSessionType): void {
  if (navigator.audioSession !== undefined) {
    navigator.audioSession.type = type
  }
}
