// How often the microphone level is read while the button is held.
const SAMPLE_EVERY_MS = 50

// Speech peaks around a quarter of full scale, so this maps a speaking voice near 1.
const LEVEL_GAIN = 4

export interface LoudnessMeter {
  // The microphone's level right now, from 0 (silent) to 1.
  current(): number
  start(): void
  stop(): null | number
}

// The RMS amplitude of the samples, the measure the speech gate and the levels share.
export function rmsOf(samples: Float32Array<ArrayBuffer>): number {
  let sumOfSquares = 0
  for (const sample of samples) {
    sumOfSquares += sample * sample
  }
  return Math.sqrt(sumOfSquares / samples.length)
}

// A level from 0 to 1 for the page to draw, from the samples' RMS amplitude.
export function levelOf(samples: Float32Array<ArrayBuffer>): number {
  return Math.min(1, rmsOf(samples) * LEVEL_GAIN)
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

  current(): number {
    if (this.#timer === null || this.#context.state !== 'running') {
      return 0
    }
    this.#analyser.getFloatTimeDomainData(this.#samples)
    return levelOf(this.#samples)
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
    this.#loudest = Math.max(this.#loudest ?? 0, rmsOf(this.#samples))
  }
}
