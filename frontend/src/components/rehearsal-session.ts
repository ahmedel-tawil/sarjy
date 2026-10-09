import type { VoiceCatalogue, VoiceList } from '@/clients/voices-client'
import type { EarlierVisit, RememberedFact, TourLink } from '@/lib/protocol'
import type {
  AudioLevels,
  Problem,
  PushToTalk,
  Replayer,
  Status,
  Visit,
  VoicePicker,
  VoiceSessionCallbacks,
} from '@/lib/voice-session'

// A stand-in for VoiceSession that plays scripted turns, so the screen's motion and its
// problem states can be reviewed without a gateway or a microphone. Development only:
// ?rehearse plays answered turns, ?rehearse=problems one failure after another. The
// words below are examples, not Sarjy's answers.

interface ScriptedTurn {
  // What the tool loop would announce while the answer is being worked out (D-94).
  activity?: string
  fact?: RememberedFact
  links?: TourLink[]
  question: string
  reply: string
}

// A failing turn, in the order VoiceSession reports it: what was heard and said, if
// anything, then the problem.
interface ScriptedProblem {
  problem: Problem
  question?: string
  reply?: string
}

const PROBLEM_SCRIPT: readonly ScriptedProblem[] = [
  { problem: 'mic_unavailable' },
  { problem: 'no_speech' },
  { problem: 'llm_failed', question: 'Which tours run on Friday morning?' },
  { problem: 'tts_failed', question: 'Is the dhow cruise good for kids?', reply: 'Yes, it is calm, and children love the lights.' },
  { problem: 'connection_lost', question: 'Can we see the Louvre on Monday?' },
  { problem: 'rate_limited' },
  { problem: 'visit_limit' },
]

const SCRIPT: readonly ScriptedTurn[] = [
  {
    question: 'I’m in Abu Dhabi next week with two kids. What can we do under 400 dirhams?',
    activity: 'Looking for tours in Abu Dhabi',
    links: [
      { name: 'Example family tour', url: 'https://example.com/tours/family' },
      { name: 'Example park day', url: 'https://example.com/tours/park' },
    ],
    reply: 'Here are two family picks in Abu Dhabi under 400 dirhams. I can share the links for both.',
  },
  {
    fact: { key: 'favourite_colour', value: 'green' },
    question: 'My favourite colour is green, and I don’t like heights.',
    reply: 'Got it, green it is, and I’ll keep you on the ground.',
  },
  {
    activity: 'Checking tomorrow’s weather in Dubai',
    question: 'Is tomorrow afternoon good for a desert safari?',
    reply: 'Tomorrow afternoon will be hot, so an evening safari is the cooler choice.',
  },
  {
    question: 'How much is the buggy dune bashing tour?',
    reply: 'The price for that one is on request. I can share the page so you can ask.',
  },
]

// Kokoro's voices that the deployed TTS carries (D-49).
const VOICES: VoiceList = { default: 'af_heart', voices: ['af_heart', 'af_bella', 'af_sarah', 'am_michael', 'am_adam'] }

const HOUR_MS = 3_600_000

// Two example earlier visits, newest first as the gateway sends them (D-92).
function earlierVisits(): EarlierVisit[] {
  return [
    {
      'started_at': hoursAgo(26),
      turns: [
        { reply: 'Here are two family picks in Abu Dhabi. Both are under 400 dirhams.', 'turn_id': 'earlier-1', transcript: 'What can we do in Abu Dhabi with kids?' },
        { reply: 'Tomorrow will be warm, so the evening is the cooler choice.', 'turn_id': 'earlier-2', transcript: 'Is tomorrow good for a desert safari?' },
      ],
    },
    {
      'started_at': hoursAgo(75),
      turns: [{ reply: 'The price for that tour is on request. I can share its page.', 'turn_id': 'earlier-3', transcript: 'How much is the buggy tour?' }],
    },
  ]
}

const HEARD_AFTER_MS = 900
const ACTIVITY_AFTER_MS = 1300
const RECONNECTS_AFTER_MS = 2000
const SPEAKS_AFTER_MS = 2200
// Roughly Kokoro's pace, so each scripted sentence lasts about as long as a real one.
const MS_PER_WORD = 380

export class RehearsalSession implements AudioLevels, PushToTalk, Replayer, Visit, VoiceCatalogue, VoicePicker {
  readonly #callbacks: VoiceSessionCallbacks
  #connected = false
  #facts: RememberedFact[] = []
  readonly #history = earlierVisits()
  #status: Status = 'idle'
  #turn = 0
  readonly #withProblems: boolean

  constructor(callbacks: VoiceSessionCallbacks, withProblems = false) {
    this.#callbacks = callbacks
    this.#withProblems = withProblems
  }

  // React's development mode connects twice; like the real socket, only the first counts.
  connect(): void {
    if (this.#connected) {
      return
    }
    this.#connected = true
    this.#callbacks.onConnection?.('connecting')
    this.#callbacks.onConnection?.('online')
    this.#callbacks.onMemory(this.#facts)
    this.#callbacks.onHistory?.(this.#history)
  }

  forgetMe(): void {
    this.#facts = []
    this.#callbacks.onMemory(this.#facts)
  }

  // Speaks an earlier answer again, sentence by sentence, as the gateway does (D-92).
  replay(turnId: string): void {
    if (this.#status !== 'idle') {
      return
    }
    const reply = this.#history.flatMap((visit) => visit.turns).find((turn) => turn['turn_id'] === turnId)?.reply
    if (reply === undefined) {
      this.#callbacks.onProblem('replay_failed')
      return
    }
    this.#setStatus('thinking')
    this.#speak(reply, HEARD_AFTER_MS)
  }

  list(): Promise<VoiceList> {
    return Promise.resolve(VOICES)
  }

  // Kept as the `voice` fact, as the gateway does (D-90).
  setVoice(voice: string): void {
    this.#facts = [...this.#facts.filter((fact) => fact.key !== 'voice'), { key: 'voice', value: voice }]
    this.#callbacks.onMemory(this.#facts)
  }

  // With no microphone or voice, both levels follow a speech-like rhythm while they apply.
  inputLevel(): number {
    return this.#status === 'listening' ? speechRhythm(performance.now() / 1000) : 0
  }

  outputLevel(): number {
    return this.#status === 'speaking' ? speechRhythm(performance.now() / 1000) : 0
  }

  press(): void {
    this.#callbacks.onProblem(null)
    if (this.#withProblems && this.#nextProblem().problem === 'mic_unavailable') {
      this.#turn += 1
      this.#callbacks.onProblem('mic_unavailable')
      return
    }
    this.#setStatus('listening')
  }

  release(): void {
    if (this.#status !== 'listening') {
      return
    }
    if (this.#withProblems) {
      this.#fail(this.#nextProblem())
      this.#turn += 1
      return
    }
    const turn = SCRIPT[this.#turn % SCRIPT.length]
    this.#turn += 1
    this.#setStatus('thinking')
    window.setTimeout(() => {
      this.#callbacks.onTranscript(turn.question)
      if (turn.fact !== undefined) {
        this.#facts = [...this.#facts.filter((fact) => fact.key !== turn.fact?.key), turn.fact]
        this.#callbacks.onMemory(this.#facts)
      }
    }, HEARD_AFTER_MS)
    const { activity } = turn
    if (activity !== undefined) {
      window.setTimeout(() => {
        this.#callbacks.onActivity?.(activity)
      }, ACTIVITY_AFTER_MS)
    }
    window.setTimeout(() => {
      this.#setStatus('speaking')
      this.#callbacks.onReply(turn.reply, turn.links ?? [])
      this.#callbacks.onTtfa(SPEAKS_AFTER_MS)
    }, SPEAKS_AFTER_MS)
    // One clip per sentence, back to back, as the gateway streams them (D-77).
    let startsAt = SPEAKS_AFTER_MS
    for (const sentence of sentencesOf(turn.reply)) {
      const durationMs = sentence.split(' ').length * MS_PER_WORD
      window.setTimeout(() => {
        this.#callbacks.onSpeak?.(sentence, durationMs)
      }, startsAt)
      startsAt += durationMs
    }
    window.setTimeout(() => {
      this.#setStatus('idle')
    }, startsAt)
  }

  #fail(scripted: ScriptedProblem): void {
    if (scripted.problem === 'no_speech') {
      this.#setStatus('idle')
      this.#callbacks.onProblem('no_speech')
      return
    }
    this.#setStatus('thinking')
    const { question, reply } = scripted
    if (question !== undefined) {
      window.setTimeout(() => {
        this.#callbacks.onTranscript(question)
      }, HEARD_AFTER_MS)
    }
    window.setTimeout(() => {
      if (reply !== undefined) {
        this.#callbacks.onReply(reply, [])
      }
      // A dropped socket reports itself first, then reconnects a few seconds later.
      if (scripted.problem === 'connection_lost') {
        this.#callbacks.onConnection?.('offline')
        window.setTimeout(() => {
          this.#callbacks.onConnection?.('connecting')
        }, RECONNECTS_AFTER_MS)
        window.setTimeout(() => {
          this.#callbacks.onConnection?.('online')
        }, RECONNECTS_AFTER_MS * 2)
      }
      this.#setStatus('idle')
      this.#callbacks.onProblem(scripted.problem)
    }, SPEAKS_AFTER_MS)
  }

  #nextProblem(): ScriptedProblem {
    return PROBLEM_SCRIPT[this.#turn % PROBLEM_SCRIPT.length]
  }

  // One clip per sentence, back to back, as the gateway streams them (D-77), then idle.
  #speak(text: string, startsAt: number): void {
    window.setTimeout(() => {
      this.#setStatus('speaking')
    }, startsAt)
    let at = startsAt
    for (const sentence of sentencesOf(text)) {
      const durationMs = sentence.split(' ').length * MS_PER_WORD
      window.setTimeout(() => {
        this.#callbacks.onSpeak?.(sentence, durationMs)
      }, at)
      at += durationMs
    }
    window.setTimeout(() => {
      this.#setStatus('idle')
    }, at)
  }

  #setStatus(status: Status): void {
    this.#status = status
    this.#callbacks.onStatus(status)
  }
}

function sentencesOf(text: string): string[] {
  return text.match(/[^.!?]+[.!?]+/g)?.map((sentence) => sentence.trim()) ?? [text]
}

// Syllable-like bursts with short pauses, between 0 and 1.
function speechRhythm(time: number): number {
  const syllables = Math.max(0, Math.sin(time * 8.5)) ** 0.6
  const phrase = Math.sin(time * 0.8) > -0.7 ? 1 : 0.1
  return Math.min(1, syllables * (0.6 + 0.4 * Math.sin(time * 2.1 + 1.3)) * phrase)
}

function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * HOUR_MS).toISOString()
}
