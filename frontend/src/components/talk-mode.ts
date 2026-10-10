// How the traveller talks to Sarjy (D-83): hold the orb (or Space) while speaking, or tap
// once to start and again to send, for anyone who finds holding hard. Kept in this browser.

export const TALK_MODES = ['hold', 'tap'] as const

export type TalkMode = (typeof TALK_MODES)[number]

// Space only helps with a keyboard, so the hints mention it only where a mouse or trackpad
// is the main pointer: a phone or tablet in the hand has no Space bar.
export const HAS_KEYBOARD = window.matchMedia('(hover: hover) and (pointer: fine)').matches

const STORAGE_KEY = 'sarjy.talk'

export function initialTalkMode(): TalkMode {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    return TALK_MODES.find((mode) => mode === saved) ?? 'hold'
  } catch {
    // Storage refused: holding is the default.
    return 'hold'
  }
}

export function saveTalkMode(mode: TalkMode): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    // Private windows can refuse storage; the mode still applies for this visit.
  }
}
