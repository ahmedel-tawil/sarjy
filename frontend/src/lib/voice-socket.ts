import { browserMarksMessage, type ServerMessage, ServerMessageSchema, TURN_END_MESSAGE } from './protocol'

export interface VoiceChannel {
  endTurn(): void
  sendAudio(chunk: Blob): void
  sendMarks(turnId: string, speechEnd: number, playbackStart: number): void
}

export interface VoiceSocketHandlers {
  onAudio: (audio: ArrayBuffer) => void
  onClose: () => void
  onMessage: (message: ServerMessage) => void
}

export class VoiceSocket implements VoiceChannel {
  readonly #handlers: VoiceSocketHandlers
  // Messages sent while connecting wait here, so the first words of a turn are kept.
  #pending: (Blob | string)[] = []
  #socket: null | WebSocket = null
  readonly #url: string

  constructor(url: string, handlers: VoiceSocketHandlers) {
    this.#url = url
    this.#handlers = handlers
  }

  endTurn(): void {
    this.#send(TURN_END_MESSAGE)
  }

  sendAudio(chunk: Blob): void {
    this.#send(chunk)
  }

  sendMarks(turnId: string, speechEnd: number, playbackStart: number): void {
    this.#send(browserMarksMessage(turnId, speechEnd, playbackStart))
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
    const socket = new WebSocket(this.#url)
    socket.binaryType = 'arraybuffer'
    socket.addEventListener('open', () => {
      for (const message of this.#pending) {
        socket.send(message)
      }
      this.#pending = []
    })
    socket.addEventListener('message', (event: MessageEvent<unknown>) => {
      this.#receive(event.data)
    })
    socket.addEventListener('close', () => {
      this.#socket = null
      this.#pending = []
      this.#handlers.onClose()
    })
    return socket
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
