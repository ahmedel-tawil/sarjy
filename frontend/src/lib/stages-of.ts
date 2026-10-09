// One turn's stages in milliseconds, computed as docs/LATENCY.md defines the gaps: the
// gateway's four on its own clock, time to first audio on the browser's, and the network
// and the browser as what is left (D-79).
export interface TurnStages {
  firstSentence: number
  firstWord: number
  network: number
  stt: number
  ttfa: number
  tts: number
}

// The gateway's marks, in milliseconds since `audio_received` on its clock, and the time
// to first audio the browser measured. Null when a mark is missing.
export function stagesOf(marks: Readonly<Partial<Record<string, number>>>, ttfa: number): null | TurnStages {
  const received = marks['audio_received']
  const heard = marks['stt_done']
  const firstWord = marks['llm_first_token']
  const firstSentence = marks['first_sentence_ready']
  const voiced = marks['tts_first_byte']
  if (
    received === undefined ||
    heard === undefined ||
    firstWord === undefined ||
    firstSentence === undefined ||
    voiced === undefined
  ) {
    return null
  }
  return {
    firstSentence: firstSentence - firstWord,
    firstWord: firstWord - heard,
    // Never below zero: the two clocks only agree on durations, to a few milliseconds.
    network: Math.max(0, ttfa - (voiced - received)),
    stt: heard - received,
    ttfa,
    tts: voiced - firstSentence,
  }
}
