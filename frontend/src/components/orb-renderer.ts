import type { AudioLevels } from '@/lib/voice-session'

// Sarjy's presence: a sphere of dots drawn on a canvas. It turns slowly at rest, ripples
// with the traveller's voice while listening, sweeps a band of light while thinking and
// pulses while speaking.

export type OrbPhase = 'listening' | 'rest' | 'speaking' | 'thinking'

interface Dot {
  x: number
  y: number
  z: number
}

// What the talk control needs from the drawing.
export interface Orb {
  assemble(): void
  refreshColours(): void
  setPhase(phase: OrbPhase): void
  start(): void
  stop(): void
}

// Colours come from CSS custom properties, so the palette lives in one stylesheet.
interface OrbColours {
  dot: string
  lit: string
}

const DOTS = sphereDots(320)
const TILT = 0.35
// The sphere's share of the canvas, leaving room to grow while listening.
const RADIUS_SHARE = 0.36
// How long the orb takes to grow in, top dots first.
const FORM_MS = 600

export class OrbRenderer implements Orb {
  readonly #canvas: HTMLCanvasElement
  #colours: OrbColours
  readonly #context: CanvasRenderingContext2D
  // When the orb started growing in; null when it is simply there, Infinity while it waits.
  #formStart: null | number
  #frame = 0
  #last = 0
  #level = 0
  readonly #levels: AudioLevels
  #phase: OrbPhase = 'rest'
  readonly #reducedMotion: MediaQueryList
  #spin = 0
  // Each phase's share of the drawing, eased so changes blend instead of jumping.
  #weights: Record<OrbPhase, number> = { listening: 0, rest: 1, speaking: 0, thinking: 0 }

  // startHidden keeps the orb empty until assemble(), for the first-load welcome.
  constructor(canvas: HTMLCanvasElement, levels: AudioLevels, startHidden = false) {
    const context = canvas.getContext('2d')
    if (context === null) {
      throw new Error('This browser cannot draw on a canvas')
    }
    this.#canvas = canvas
    this.#context = context
    this.#levels = levels
    this.#colours = readColours(canvas)
    this.#reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    this.#formStart = startHidden ? Infinity : null
  }

  assemble(): void {
    this.#formStart = performance.now()
  }

  // The palette can change while the page is open.
  refreshColours(): void {
    this.#colours = readColours(this.#canvas)
  }

  setPhase(phase: OrbPhase): void {
    this.#phase = phase
  }

  start(): void {
    this.#last = performance.now()
    this.#frame = requestAnimationFrame(this.#draw)
  }

  stop(): void {
    cancelAnimationFrame(this.#frame)
  }

  readonly #draw = (now: number): void => {
    const still = this.#reducedMotion.matches
    const dt = still ? 0 : Math.min(0.05, (now - this.#last) / 1000)
    const time = still ? 2 : now / 1000
    this.#last = now
    for (const phase of ['listening', 'rest', 'speaking', 'thinking'] as const) {
      this.#weights[phase] = ease(this.#weights[phase], phase === this.#phase ? 1 : 0, dt, 0.12, still)
    }
    this.#level = ease(this.#level, this.#targetLevel(still), dt, 0.06, still)
    this.#spin += dt * (0.2 + this.#weights.thinking * 0.9)
    const formed = still || this.#formStart === null ? 1 : Math.min(1, Math.max(0, (now - this.#formStart) / FORM_MS))
    this.#render(time, formed)
    this.#frame = requestAnimationFrame(this.#draw)
  }

  // Matches the canvas's drawing buffer to its size on screen, sharp on dense screens.
  #fit(): number {
    const canvas = this.#canvas
    const size = canvas.clientWidth
    const ratio = Math.min(2, window.devicePixelRatio || 1)
    if (canvas.width !== Math.round(size * ratio)) {
      canvas.width = Math.round(size * ratio)
      canvas.height = Math.round(size * ratio)
    }
    this.#context.setTransform(ratio, 0, 0, ratio, 0, 0)
    return size
  }

  #render(time: number, formed: number): void {
    const size = this.#fit()
    const context = this.#context
    const { listening, rest, speaking, thinking } = this.#weights
    context.clearRect(0, 0, size, size)
    const center = size / 2
    const radius = size * RADIUS_SHARE * (0.6 + 0.4 * easeOut(formed)) * (1 + listening * (0.06 + this.#level * 0.12) + speaking * this.#level * 0.05)
    const brightness = 0.55 * rest + listening + thinking + speaking
    // While thinking, a band of light sweeps around the sphere, the way a lighthouse turns.
    const sweep = time * 1.6
    const band = { x: Math.cos(sweep) * 0.8, y: Math.sin(time * 0.7) * 0.6, z: Math.sin(sweep) * 0.8 }
    const spinCos = Math.cos(this.#spin)
    const spinSin = Math.sin(this.#spin)
    const tiltCos = Math.cos(TILT)
    const tiltSin = Math.sin(TILT)
    // Back half first, then the front, so near dots cover far ones.
    for (const front of [false, true]) {
      for (const dot of DOTS) {
        const x = dot.x * spinCos - dot.z * spinSin
        const turnedZ = dot.x * spinSin + dot.z * spinCos
        const y = dot.y * tiltCos - turnedZ * tiltSin
        const z = dot.y * tiltSin + turnedZ * tiltCos
        if (z >= 0 !== front) {
          continue
        }
        // Growing in, the top dots arrive first.
        const arrival = easeOut(Math.min(1, Math.max(0, formed * 1.6 - ((1 - dot.y) / 2) * 0.6)))
        if (arrival === 0) {
          continue
        }
        const depth = (z + 1) / 2
        const voice = listening * this.#level * Math.max(0, Math.sin(dot.y * 6 + time * 10))
        const light = thinking * Math.max(0, (dot.x * band.x + dot.y * band.y + dot.z * band.z - 0.55) / 0.45) ** 2
        const speech = speaking * this.#level * Math.max(0, Math.sin(depth * 7 - time * 9))
        const lit = Math.min(1, Math.max(voice, light, speech))
        const perspective = 3 / (3 - z)
        context.globalAlpha = Math.min(1, (0.18 + 0.82 * depth) * brightness + lit * 0.5) * arrival
        context.fillStyle = lit > 0.3 ? this.#colours.lit : this.#colours.dot
        context.beginPath()
        context.arc(
          center + x * radius * perspective,
          center - y * radius * perspective,
          (0.6 + 1.1 * depth) * (1 + lit * 0.8) * (size / 112) * (0.4 + 0.6 * arrival),
          0,
          Math.PI * 2,
        )
        context.fill()
      }
    }
    context.globalAlpha = 1
  }

  #targetLevel(still: boolean): number {
    if (still) {
      return 0
    }
    if (this.#phase === 'listening') {
      return this.#levels.inputLevel()
    }
    return this.#phase === 'speaking' ? this.#levels.outputLevel() : 0
  }
}

function easeOut(progress: number): number {
  return 1 - (1 - progress) ** 3
}

// Moves current toward target, covering most of the way in about three time constants.
function ease(current: number, target: number, dt: number, seconds: number, still: boolean): number {
  return still ? target : current + (target - current) * (1 - Math.exp(-dt / seconds))
}

function readColours(element: Element): OrbColours {
  const styles = getComputedStyle(element)
  return {
    dot: styles.getPropertyValue('--orb-dot').trim(),
    lit: styles.getPropertyValue('--orb-lit').trim(),
  }
}

// Points spread evenly over a sphere, row by row from top to bottom.
function sphereDots(count: number): Dot[] {
  const golden = Math.PI * (3 - Math.sqrt(5))
  return Array.from({ length: count }, (_, index) => {
    const y = 1 - ((index + 0.5) / count) * 2
    const ring = Math.sqrt(1 - y * y)
    return { x: Math.cos(index * golden) * ring, y, z: Math.sin(index * golden) * ring }
  })
}
