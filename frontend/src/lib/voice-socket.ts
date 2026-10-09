import {
  browserMarksMessage,
  FORGET_ME_MESSAGE,
  replayMessage,
  type ServerMessage,
  ServerMessageSchema,
  setVoiceMessage,
  TURN_CANCEL_MESSAGE,
  TURN_END_MESSAGE,
} from './protocol'

// After an unexpected close, wait this long before reopening, longer each time it fails.
const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 10_000] as const

export interface VoiceChannel {
  cancelTurn(): void
  connect(): void
  endTurn(): void
  forgetMe(): void
  replay(turnId: string): void
  sendAudio(chunk: Blob): void
  sendMarks(turnId: string, speechEnd: number, playbackStart: number): void
  setVoice(voice: string): void
}

export interface VoiceSocketHandlers {
  onAudio: (audio: ArrayBuffer) => void
  onClose: () => void
  onConnecting: () => void
  onMessage: (message: ServerMessage) => void
  onOpen: () => void
}

export class VoiceSocket implements VoiceChannel {
  // Reconnects in a row that failed; back to 0 once one opens.
  #failures = 0
  readonly #handlers: VoiceSocketHandlers
  // Messages sent while connecting wait here, so the first words of a turn are kept.
  #pending: (Blob | string)[] = []
  #reconnectTimer: null | number = null
  #socket: null | WebSocket = null
  readonly #url: string

  constructor(url: string, handlers: VoiceSocketHandlers) {
    this.#url = url
    this.#handlers = handlers
    // A tab coming back into view reconnects at once, rather than waiting for its timer.
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible' && this.#socket === null) {
        this.connect()
      }
    })
  }

  cancelTurn(): void {
    this.#send(TURN_CANCEL_MESSAGE)
  }

  // Opened as the page loads, so the memory panel fills before the first question. After
  // an unexpected close it reopens by itself (M4.2), but only while the tab is visible: an
  // open socket counts as a request on Cloud Run, and a forgotten tab shouldn't keep the
  // gateway busy.
  connect(): void {
    this.#socket ??= this.#open()
  }

  endTurn(): void {
    this.#send(TURN_END_MESSAGE)
  }

  forgetMe(): void {
    this.#send(FORGET_ME_MESSAGE)
  }

  replay(turnId: string): void {
    this.#send(replayMessage(turnId))
  }

  sendAudio(chunk: Blob): void {
    this.#send(chunk)
  }

  sendMarks(turnId: string, speechEnd: number, playbackStart: number): void {
    this.#send(browserMarksMessage(turnId, speechEnd, playbackStart))
  }

  setVoice(voice: string): void {
    this.#send(setVoiceMessage(voice))
  }

  #send(message: Blob | string): void {
    this.#socket ??= this.#open()
    if (this.#socket.readyState === WebSocket.OPEN) {
      this.#socket.send(message)
    } else {
      this.#pending.push(message)
    }
  }

  #open(): WebSocket {
    this.#handlers.onConnecting()
    const socket = new WebSocket(this.#url)
    socket.binaryType = 'arraybuffer'
    socket.addEventListener('open', () => {
      this.#failures = 0
      for (const message of this.#pending) {
        socket.send(message)
      }
      this.#pending = []
      this.#handlers.onOpen()
    })
    socket.addEventListener('message', (event: MessageEvent<unknown>) => {
      this.#receive(event.data)
    })
    socket.addEventListener('close', () => {
      this.#socket = null
      this.#pending = []
      this.#handlers.onClose()
      this.#reconnectLater()
    })
    return socket
  }

  #reconnectLater(): void {
    if (this.#reconnectTimer !== null) {
      return
    }
    const delay = RECONNECT_DELAYS_MS[Math.min(this.#failures, RECONNECT_DELAYS_MS.length - 1)]
    this.#failures += 1
    this.#reconnectTimer = window.setTimeout(() => {
      this.#reconnectTimer = null
      if (document.visibilityState === 'visible') {
        this.connect()
      }
    }, delay)
  }

  #receive(data: unknown): void {
    if (data instanceof ArrayBuffer) {
      this.#handlers.onAudio(data)
      return
    }
    const message = ServerMessageSchema.safeParse(JSON.parse(String(data)))
    if (message.success) {
      this.#handlers.onMessage(message.data)
    }
  }
}
