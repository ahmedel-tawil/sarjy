import { levelOf } from './level-meter'

// The gestures a browser accepts for starting audio. On a touchscreen a finger going down
// is not one, only lifting it, so on an iPhone the orb's press alone cannot start Sarjy's
// voice (D-85).
const WAKE_EVENTS = ['keydown', 'pointerup', 'touchend'] as const

export interface AudioPlayer {
  // Plays this clip right after the ones already queued; resolves when it has ended.
  enqueue(audio: ArrayBuffer, onStart: (durationMs: number) => void): Promise<void>
  // Resolves once every clip queued so far has ended.
  finished(): Promise<void>
  // How loud the output is right now, from 0 (silent) to 1.
  level(): number
  unlock(): AudioContext
}

interface Output {
  analyser: AnalyserNode
  context: AudioContext
  samples: Float32Array<ArrayBuffer>
}

// A promise inside an object, because an async function that returns a promise waits for
// it: the next clip must be scheduled now, not once this one has ended.
interface ScheduledClip {
  ended: Promise<void>
}

// A promise that resolves once open() is called, so the next clip knows when it may be
// scheduled.
class Gate {
  readonly opened: Promise<void>
  #open: (() => void) | null = null

  constructor() {
    this.opened = new Promise<void>((resolve) => {
      this.#open = resolve
    })
  }

  open(): void {
    this.#open?.()
  }
}

// Plays a reply's clips back to back (D-77): each is scheduled on the audio clock for the
// moment the previous one ends, so sentences join with no gap and never overlap.
export class Player implements AudioPlayer {
  // Resolves when the last scheduled clip has finished playing.
  #lastEnded: Promise<void> = Promise.resolve()
  // On the audio context's clock: when the queue is free for the next clip.
  #nextStart = 0
  #output: null | Output = null
  // Resolves once the last queued clip has been scheduled, or failed to decode. Each clip
  // waits for it, which keeps clips in the order they arrived even when a later one
  // decodes faster.
  #scheduled: Promise<void> = Promise.resolve()

  async enqueue(audio: ArrayBuffer, onStart: (durationMs: number) => void): Promise<void> {
    const previous = this.#scheduled
    const gate = new Gate()
    this.#scheduled = gate.opened
    let clip: ScheduledClip
    try {
      await previous
      clip = await this.#schedule(audio, onStart)
    } finally {
      gate.open()
    }
    this.#lastEnded = clip.ended
    await clip.ended
  }

  async finished(): Promise<void> {
    await this.#scheduled
    await this.#lastEnded
  }

  level(): number {
    if (this.#output === null) {
      return 0
    }
    const { analyser, samples } = this.#output
    analyser.getFloatTimeDomainData(samples)
    return levelOf(samples)
  }

  // Called on a press: Safari keeps audio silent until a gesture starts it. Returns the
  // context, so the recorder's level meter can share it.
  unlock(): AudioContext {
    const { context } = this.#outputNodes()
    this.#wake()
    return context
  }

  #outputNodes(): Output {
    if (this.#output === null) {
      const context = new AudioContext()
      const analyser = context.createAnalyser()
      analyser.connect(context.destination)
      this.#output = { analyser, context, samples: new Float32Array(analyser.fftSize) }
      // Any later gesture, and coming back to the page, starts the audio again: iOS stops
      // it for a locked screen, a call or Siri, even halfway through a reply.
      for (const type of WAKE_EVENTS) {
        window.addEventListener(type, () => {
          this.#wake()
        }, { capture: true })
      }
      document.addEventListener('visibilitychange', () => {
        this.#wake()
      })
    }
    return this.#output
  }

  // Decodes the clip and schedules it after the queue. onStart runs as its first sample
  // plays: for the first clip, the `playback_start` mark.
  async #schedule(audio: ArrayBuffer, onStart: (durationMs: number) => void): Promise<ScheduledClip> {
    const { analyser, context } = this.#outputNodes()
    const buffer = await context.decodeAudioData(audio)
    const source = context.createBufferSource()
    source.buffer = buffer
    source.connect(analyser)
    const ended = new Promise<void>((resolve) => {
      source.addEventListener('ended', () => {
        resolve()
      }, { once: true })
    })
    const startAt = Math.max(context.currentTime, this.#nextStart)
    this.#nextStart = startAt + buffer.duration
    source.start(startAt)
    const durationMs = buffer.duration * 1000
    window.setTimeout(() => {
      onStart(durationMs)
    }, (startAt - context.currentTime) * 1000)
    return { ended }
  }

  // Starts the audio if anything stopped it: before the first gesture it is 'suspended',
  // and iOS uses 'interrupted' after a lock. Not awaited, because iOS can hold the promise
  // until an interruption ends, and a recording must not wait for that.
  #wake(): void {
    const context = this.#output?.context
    if (context === undefined || context.state === 'running' || context.state === 'closed') {
      return
    }
    context.resume().catch(() => {
      // Refused without a gesture; the next tap tries again.
    })
  }
}
