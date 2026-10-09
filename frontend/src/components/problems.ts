import type { Problem } from '@/lib/voice-session'

// Every problem the page can hear, sorted by what the traveller should see (D-81):
// - hint: a slip of the hand, said quietly under the orb;
// - turn: the question was heard but not answered, noted on that turn in the conversation;
// - microphone, visit: a card above the orb that stays until it is fixed or acted on;
// - trouble: anything else, said under the orb in the error colour.
export type ProblemKind = 'hint' | 'microphone' | 'trouble' | 'turn' | 'visit'

interface ProblemShown {
  kind: ProblemKind
  text: string
}

export const PROBLEMS: Record<Problem, ProblemShown> = {
  'connection_lost': { kind: 'turn', text: 'The connection dropped before Sarjy answered. Ask again once it is back.' },
  'forget_failed': { kind: 'trouble', text: 'Sarjy couldn’t forget you just now. Please try again.' },
  'invalid_message': { kind: 'turn', text: 'Something went wrong on our side. Hold the orb to ask again.' },
  'llm_failed': { kind: 'turn', text: 'Sarjy couldn’t find an answer this time. Hold the orb to ask again.' },
  'mic_unavailable': {
    kind: 'microphone',
    text: 'Allow the microphone for this site in your browser’s address bar, then hold the orb again.',
  },
  'no_audio': { kind: 'hint', text: 'Hold the orb while you speak, then let go.' },
  'no_speech': { kind: 'hint', text: 'Hold the orb while you speak, then let go.' },
  'playback_failed': { kind: 'turn', text: 'Sarjy’s voice didn’t come through, so here is the answer in writing.' },
  'rate_limited': { kind: 'trouble', text: 'Lots of questions right now. Try again in a minute.' },
  'stt_failed': { kind: 'trouble', text: 'Sarjy couldn’t make out what you said. Try again.' },
  'too_many_turns': { kind: 'trouble', text: 'You’re asking faster than Sarjy can keep up. Try again in a few minutes.' },
  'tts_failed': { kind: 'turn', text: 'Sarjy’s voice didn’t come through, so here is the answer in writing.' },
  'turn_too_long': { kind: 'hint', text: 'That was a long one. Try a shorter question.' },
  'unknown_voice': { kind: 'trouble', text: 'That voice isn’t available.' },
  'visit_limit': { kind: 'visit', text: 'That’s as many questions as one visit allows. Start a new visit to keep going; Sarjy still remembers you.' },
}

// What the line under the orb says: a problem in words of its own, or the resting text. The
// microphone and a full visit have cards instead; a turn problem with no turn to note it on
// (no question heard yet) is said here too.
export function statusLine(problem: null | Problem, resting: string): { text: string; trouble: boolean } {
  const shown = problem === null ? null : PROBLEMS[problem]
  if (shown === null || shown.kind === 'microphone' || shown.kind === 'visit') {
    return { text: resting, trouble: false }
  }
  return { text: shown.text, trouble: shown.kind !== 'hint' }
}
