import { Player } from './player'
import type { EarlierVisit, ErrorCode, RememberedFact, ServerMessage, TourLink } from './protocol'
import { Recorder, type Recording } from './recorder'
import { stagesOf, type TurnStages } from './stages-of'
import { VoiceSocket } from './voice-socket'

// A press shorter than this is a tap, not a question.
const MIN_RECORDING_MS = 300

// Browsers suppress background noise on the microphone, so a silent room sits well below
// this level and speech well above it (D-55).
const SPEECH_DBFS = -45

export type Status = 'idle' | 'listening' | 'speaking' | 'thinking'

export type Problem = 'connection_lost' | 'mic_unavailable' | 'playback_failed' | ErrorCode

// The socket to the gateway: opening, open, or closed and waiting to reconnect (M4.2).
export type Connection = 'connecting' | 'offline' | 'online'

export interface VoiceSessionCallbacks {
  // What Sarjy is doing while a tool runs, such as "Looking for tours in Dubai" (D-94). With
  // sentence streaming a short filler may already be playing when one arrives.
  onActivity?: (text: string) => void
  onConnection?: (connection: Connection) => void
  // The user's last few visits with a question, newest first, when a visit starts (D-92).
  onHistory?: (visits: EarlierVisit[]) => void
  // Everything Sarjy remembers about the user, in full each time it changes.
  onMemory: (facts: RememberedFact[]) => void
  onProblem: (problem: null | Problem) => void
  // The whole reply, for the record: when its first clip plays, or as soon as it arrives
  // if that clip is already playing; also when its voice never came. `links` are the
  // pages of the tours it names, which Sarjy never reads out (D-90).
  onReply: (text: string, links: TourLink[]) => void
  // Each clip as it starts playing, with the words it speaks and how long it lasts, so the
  // page can show them as they are spoken: one clip per sentence when streaming (D-77).
  onSpeak?: (text: string, durationMs: number) => void
  // Where the turn's time went, once both clocks' marks are in (D-79).
  onStages?: (stages: TurnStages) => void
  onStatus: (status: Status) => void
  onTranscript: (text: string) => void
  // Time to first audio: from the button release to the first sample of the reply.
  onTtfa: (milliseconds: number) => void
}

export interface PushToTalk {
  press(): void
  release(): void
}

// What the page needs from the visit besides talking.
export interface Visit {
  // Opens the socket early, so the memory panel fills before the first question.
  connect(): void
  forgetMe(): void
}

// Speaks an earlier reply again, sentence by sentence, in the current voice (D-92). Its
// clips arrive through onSpeak like any reply's; a replay sends no latency marks.
export interface Replayer {
  replay(turnId: string): void
}

// Picks the voice of the next replies; the gateway remembers it for the next visit too.
export interface VoicePicker {
  setVoice(voice: string): void
}

// Live levels for the page to animate, each from 0 to 1 and cheap enough to read every
// frame: the microphone while the button is held, and Sarjy's voice while it speaks.
export interface AudioLevels {
  inputLevel(): number
  outputLevel(): number
}

// What the page knows about the turn waiting for its answer, filled in as the gateway's
// messages arrive.
interface TurnInFlight {
  links: TourLink[]
  // The words of the clip whose binary frame comes next.
  nextText: string
  // A replay of an earlier reply rather than a question being answered.
  replay: boolean
  // Held until the first clip plays, so the words and the voice appear together.
  reply: null | string
  // The gateway's marks, from its last message of the turn.
  serverMarks: null | Readonly<Record<string, number>>
  // performance.now() at the release that ended the turn.
  speechEnd: number
  // Whether the first clip has started playing.
  started: boolean
  // Time to first audio, known once the first clip plays.
  ttfa: null | number
  // The gateway names the turn in a JSON message just before each binary audio frame.
  turnId: null | string
}

export class VoiceSession implements AudioLevels, PushToTalk, Replayer, Visit, VoicePicker {
  readonly #callbacks: VoiceSessionCallbacks
  readonly #player = new Player()
  readonly #recorder = new Recorder()
  // Counted rather than flagged, so press() can tell whether a release happened while
  // it was waiting for the microphone.
  #releases = 0
  readonly #socket: VoiceSocket
  #status: Status = 'idle'
  #turn: null | TurnInFlight = null

  constructor(url: string, callbacks: VoiceSessionCallbacks) {
    this.#callbacks = callbacks
    this.#socket = new VoiceSocket(url, {
      onAudio: (audio) => {
        this.#play(audio)
      },
      onClose: () => {
        this.#callbacks.onConnection?.('offline')
        // A phone that sleeps or a deploy closes an idle socket, and the next press opens a
        // new one, so only a turn still waiting for its answer has lost anything; a reply
        // already playing finishes what it has.
        if (this.#status === 'listening' || this.#status === 'thinking') {
          this.#report('connection_lost')
        } else if (this.#status === 'speaking') {
          this.#endTurnWhenPlayed().catch(() => {
            this.#report('playback_failed')
          })
        }
      },
      onConnecting: () => {
        this.#callbacks.onConnection?.('connecting')
      },
      onMessage: (message) => {
        this.#receive(message)
      },
      onOpen: () => {
        this.#callbacks.onConnection?.('online')
      },
    })
  }

  connect(): void {
    this.#socket.connect()
  }

  forgetMe(): void {
    this.#callbacks.onProblem(null)
    this.#socket.forgetMe()
  }

  inputLevel(): number {
    return this.#recorder.level()
  }

  outputLevel(): number {
    return this.#player.level()
  }

  press(): void {
    // One turn at a time: each speech_end must pair with the audio of its own reply.
    if (this.#status !== 'idle') {
      return
    }
    this.#callbacks.onProblem(null)
    this.#startRecording().catch(() => {
      this.#report('mic_unavailable')
    })
  }

  replay(turnId: string): void {
    // One thing at a time, as with turns: a replay's clips must not mix with an answer's.
    if (this.#status !== 'idle') {
      return
    }
    this.#callbacks.onProblem(null)
    this.#turn = { ...this.#newTurn(), replay: true, turnId }
    this.#setStatus('thinking')
    this.#socket.replay(turnId)
  }

  setVoice(voice: string): void {
    this.#callbacks.onProblem(null)
    this.#socket.setVoice(voice)
  }

  release(): void {
    this.#releases += 1
    if (!this.#recorder.recording) {
      return
    }
    this.#turn = this.#newTurn()
    this.#setStatus('thinking')
    this.#endTurn().catch(() => {
      this.#report('connection_lost')
    })
  }

  // The first clip starts the reply: its moment is `playback_start`, and the held reply
  // appears with it. Every clip then hands its words to the page. A replay only plays.
  #clipStarted(turn: TurnInFlight, text: string, durationMs: number): void {
    if (!turn.started && turn.replay) {
      turn.started = true
      this.#setStatus('speaking')
    }
    if (!turn.started) {
      turn.started = true
      const playbackStart = performance.now()
      this.#setStatus('speaking')
      if (turn.reply !== null) {
        this.#callbacks.onReply(turn.reply, turn.links)
      }
      turn.ttfa = playbackStart - turn.speechEnd
      if (turn.turnId !== null) {
        this.#socket.sendMarks(turn.turnId, turn.speechEnd, playbackStart)
        this.#callbacks.onTtfa(turn.ttfa)
      }
      this.#reportStages(turn)
    }
    this.#callbacks.onSpeak?.(text, durationMs)
  }

  // The gateway has sent every clip of the turn; it ends once the last one has played.
  async #endTurnWhenPlayed(): Promise<void> {
    const turn = this.#turn
    if (turn === null) {
      return
    }
    await this.#player.finished()
    if (this.#turn === turn) {
      this.#turn = null
      this.#setStatus('idle')
    }
  }

  #newTurn(): TurnInFlight {
    return {
      links: [],
      nextText: '',
      replay: false,
      reply: null,
      serverMarks: null,
      speechEnd: performance.now(),
      started: false,
      ttfa: null,
      turnId: null,
    }
  }

  async #endTurn(): Promise<void> {
    const recording = await this.#recorder.stop()
    if (heardSpeech(recording)) {
      this.#socket.endTurn()
    } else {
      this.#socket.cancelTurn()
      this.#report('no_speech')
    }
  }

  #play(audio: ArrayBuffer): void {
    const turn = this.#turn
    // Audio for a turn that already failed has nothing left to say.
    if (turn === null) {
      return
    }
    const text = turn.nextText
    this.#player
      .enqueue(audio, (durationMs) => {
        this.#clipStarted(turn, text, durationMs)
      })
      .catch(() => {
        this.#report('playback_failed')
      })
  }

  #receive(message: ServerMessage): void {
    switch (message.type) {
      case 'activity': {
        // A turn that already failed or was cancelled is doing nothing any more.
        if (this.#turn !== null) {
          this.#callbacks.onActivity?.(message.text)
        }
        break
      }
      case 'audio': {
        if (this.#turn !== null) {
          this.#turn.turnId = message['turn_id']
          this.#turn.nextText = message.text
        }
        break
      }
      case 'error': {
        this.#report(message.code)
        break
      }
      case 'marks': {
        // The last message of a turn: every clip has arrived.
        if (this.#turn !== null) {
          this.#turn.serverMarks = message.marks
          this.#reportStages(this.#turn)
        }
        this.#endTurnWhenPlayed().catch(() => {
          this.#report('playback_failed')
        })
        break
      }
      case 'history': {
        this.#callbacks.onHistory?.(message.visits)
        break
      }
      case 'memory': {
        this.#callbacks.onMemory(message.facts)
        break
      }
      case 'replay_done': {
        this.#endTurnWhenPlayed().catch(() => {
          this.#report('playback_failed')
        })
        break
      }
      case 'reply': {
        const turn = this.#turn
        if (turn !== null) {
          turn.reply = message.text
          turn.links = message.links
          if (turn.started) {
            this.#callbacks.onReply(message.text, message.links)
          }
        }
        break
      }
      case 'transcript': {
        this.#callbacks.onTranscript(message.text)
        break
      }
    }
  }

  // Runs when the first clip plays and when the marks arrive; whichever comes second has
  // both clocks' numbers and reports the stages, once.
  #reportStages(turn: TurnInFlight): void {
    if (turn.ttfa === null || turn.serverMarks === null) {
      return
    }
    const stages = stagesOf(turn.serverMarks, turn.ttfa)
    if (stages !== null) {
      this.#callbacks.onStages?.(stages)
    }
  }

  #report(problem: Problem): void {
    // A reply whose voice never came is still worth reading.
    const turn = this.#turn
    if (turn !== null && !turn.started && turn.reply !== null) {
      this.#callbacks.onReply(turn.reply, turn.links)
    }
    this.#turn = null
    this.#setStatus('idle')
    this.#callbacks.onProblem(problem)
  }

  #setStatus(status: Status): void {
    this.#status = status
    this.#callbacks.onStatus(status)
  }

  async #startRecording(): Promise<void> {
    const releasesBefore = this.#releases
    const context = await this.#player.unlock()
    await this.#recorder.prepare(context)
    // Released while the permission prompt was open: wait for the next press.
    if (this.#releases !== releasesBefore) {
      return
    }
    this.#recorder.start((chunk) => {
      this.#socket.sendAudio(chunk)
    })
    this.#setStatus('listening')
  }
}

function heardSpeech(recording: Recording): boolean {
  if (recording.durationMs < MIN_RECORDING_MS) {
    return false
  }
  // Without a measurement, let the turn through rather than lose real speech.
  return recording.loudestDbfs === null || recording.loudestDbfs >= SPEECH_DBFS
}
