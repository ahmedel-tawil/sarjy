import { speechRhythm } from '@/components/orb-renderer'
import type { RememberedFact } from '@/lib/protocol'
import type { PushToTalk, Visit, VoiceSessionCallbacks } from '@/lib/voice-session'

// A stand-in for VoiceSession that plays scripted turns, so the screen's motion can
// be reviewed without a gateway or a microphone. Development only, opened with ?rehearse;
// the words below are examples, not Sarjy's answers.

interface ScriptedTurn {
  fact?: RememberedFact
  question: string
  reply: string
}

const SCRIPT: readonly ScriptedTurn[] = [
  {
    question: 'I’m in Abu Dhabi next week with two kids. What can we do under 400 dirhams?',
    reply: 'Here are two family picks in Abu Dhabi under 400 dirhams. I can share the links for both.',
  },
  {
    fact: { key: 'favourite_colour', value: 'green' },
    question: 'My favourite colour is green, and I don’t like heights.',
    reply: 'Got it, green it is, and I’ll keep you on the ground.',
  },
  {
    question: 'Is tomorrow afternoon good for a desert safari?',
    reply: 'Tomorrow afternoon will be hot, so an evening safari is the cooler choice.',
  },
  {
    question: 'How much is the buggy dune bashing tour?',
    reply: 'The price for that one is on request. I can share the page so you can ask.',
  },
]

// Stands in for the microphone, so the dunes ripple during a rehearsed question.
export function rehearsedMicLevel(): number {
  return speechRhythm(performance.now() / 1000)
}

const HEARD_AFTER_MS = 900
const SPEAKS_AFTER_MS = 2200
const MS_PER_WORD = 260

export class RehearsalSession implements PushToTalk, Visit {
  readonly #callbacks: VoiceSessionCallbacks
  #facts: RememberedFact[] = []
  #listening = false
  #turn = 0

  constructor(callbacks: VoiceSessionCallbacks) {
    this.#callbacks = callbacks
  }

  connect(): void {
    this.#callbacks.onMemory(this.#facts)
  }

  forgetMe(): void {
    this.#facts = []
    this.#callbacks.onMemory(this.#facts)
  }

  press(): void {
    this.#listening = true
    this.#callbacks.onProblem(null)
    this.#callbacks.onStatus('listening')
  }

  release(): void {
    if (!this.#listening) {
      return
    }
    this.#listening = false
    const turn = SCRIPT[this.#turn % SCRIPT.length]
    this.#turn += 1
    this.#callbacks.onStatus('thinking')
    window.setTimeout(() => {
      this.#callbacks.onTranscript(turn.question)
      if (turn.fact !== undefined) {
        this.#facts = [...this.#facts.filter((fact) => fact.key !== turn.fact?.key), turn.fact]
        this.#callbacks.onMemory(this.#facts)
      }
    }, HEARD_AFTER_MS)
    window.setTimeout(() => {
      this.#callbacks.onStatus('speaking')
      this.#callbacks.onReply(turn.reply)
      this.#callbacks.onTtfa(SPEAKS_AFTER_MS)
    }, SPEAKS_AFTER_MS)
    window.setTimeout(
      () => {
        this.#callbacks.onStatus('idle')
      },
      SPEAKS_AFTER_MS + turn.reply.split(' ').length * MS_PER_WORD,
    )
  }
}
