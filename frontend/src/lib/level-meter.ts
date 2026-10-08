// How often the microphone level is read while the button is held.
const SAMPLE_EVERY_MS = 50

export interface LoudnessMeter {
  start(): void
  stop(): null | number
}

// Keeps the loudest moment of a recording, so a press with no speech in it can be
// cancelled before Whisper turns its silence into words (D-55).
export class LevelMeter implements LoudnessMeter {
  readonly #analyser: AnalyserNode
  readonly #context: AudioContext
  // Null until a reading is taken, which needs a running audio context.
  #loudest: null | number = null
  readonly #samples: Float32Array<ArrayBuffer>
  #timer: null | number = null

  constructor(context: AudioContext, stream: MediaStream) {
    this.#context = context
    this.#analyser = context.createAnalyser()
    context.createMediaStreamSource(stream).connect(this.#analyser)
    this.#samples = new Float32Array(this.#analyser.fftSize)
  }

  start(): void {
    this.#loudest = null
    this.#timer = window.setInterval(() => {
      this.#sample()
    }, SAMPLE_EVERY_MS)
  }

  // The loudest moment since start(), in dBFS (0 is full scale; digital silence is
  // -Infinity), or null when no reading could be taken.
  stop(): null | number {
    if (this.#timer !== null) {
      window.clearInterval(this.#timer)
      this.#timer = null
    }
    return this.#loudest === null ? null : 20 * Math.log10(this.#loudest)
  }

  #sample(): void {
    if (this.#context.state !== 'running') {
      return
    }
    this.#analyser.getFloatTimeDomainData(this.#samples)
    let sumOfSquares = 0
    for (const sample of this.#samples) {
      sumOfSquares += sample * sample
    }
    this.#loudest = Math.max(this.#loudest ?? 0, Math.sqrt(sumOfSquares / this.#samples.length))
  }
}
