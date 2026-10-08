export interface AudioPlayer {
  play(audio: ArrayBuffer, onStart: () => void): Promise<void>
  unlock(): Promise<void>
}

export class Player implements AudioPlayer {
  #context: AudioContext | null = null

  // onStart runs as the first sample is scheduled: the `playback_start` mark.
  async play(audio: ArrayBuffer, onStart: () => void): Promise<void> {
    const context = this.#audioContext()
    const buffer = await context.decodeAudioData(audio)
    const source = context.createBufferSource()
    source.buffer = buffer
    source.connect(context.destination)
    const ended = new Promise<void>((resolve) => {
      source.addEventListener('ended', () => {
        resolve()
      }, { once: true })
    })
    source.start()
    onStart()
    await ended
  }

  // Must run inside a user gesture: Safari keeps audio silent until then.
  async unlock(): Promise<void> {
    const context = this.#audioContext()
    if (context.state === 'suspended') {
      await context.resume()
    }
  }

  #audioContext(): AudioContext {
    this.#context ??= new AudioContext()
    return this.#context
  }
}
