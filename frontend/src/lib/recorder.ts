// Chrome records Opus in WebM; Safari only records AAC in MP4.
const MIME_TYPES = ['audio/webm;codecs=opus', 'audio/mp4'] as const

// Short chunks let the upload overlap speech instead of starting at release.
const CHUNK_MS = 250

export interface AudioRecorder {
  prepare(): Promise<void>
  readonly recording: boolean
  start(onChunk: (chunk: Blob) => void): void
  stop(): Promise<void>
}

export class Recorder implements AudioRecorder {
  #recorder: MediaRecorder | null = null
  #stream: MediaStream | null = null

  get recording(): boolean {
    return this.#recorder !== null
  }

  // The first call shows the permission prompt; later turns reuse the stream.
  async prepare(): Promise<void> {
    this.#stream ??= await navigator.mediaDevices.getUserMedia({ audio: true })
  }

  start(onChunk: (chunk: Blob) => void): void {
    if (this.#stream === null) {
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
    this.#recorder = recorder
  }

  async stop(): Promise<void> {
    const recorder = this.#recorder
    this.#recorder = null
    if (recorder === null || recorder.state === 'inactive') {
      return
    }
    // "stop" fires after the last chunk, so the caller can end the turn safely.
    const stopped = new Promise<void>((resolve) => {
      recorder.addEventListener('stop', () => {
        resolve()
      }, { once: true })
    })
    recorder.stop()
    await stopped
  }
}
