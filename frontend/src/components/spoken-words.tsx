import { Fragment } from 'react'

// A word stays in the accent colour a little longer than it takes to say, then settles.
const HIGHLIGHT_STRETCH = 1.5
const SHORTEST_HIGHLIGHT_MS = 240

const SIZES = {
  caption: 'text-2xl/snug font-medium text-balance',
  earlier: 'text-pretty',
  reply: 'text-lg/relaxed text-pretty md:text-xl/relaxed',
} as const

// One clip of Sarjy's voice and the words it speaks: a sentence when streaming (D-77).
export interface SpokenClip {
  durationMs: number
  // performance.now() as the clip started playing.
  startedAt: number
  text: string
}

interface TimedWord {
  atMs: number
  lengthMs: number
  text: string
}

// Sarjy's reply, word by word as it is spoken. Each clip's words arrive as its audio starts
// and are spread across the clip's length, longer words taking longer; a CSS delay reveals
// each one at its moment, in the accent colour, before it settles into ink.
// An earlier visit's answer is set smaller than the current visit's (D-84), and voice mode's
// caption larger.
export function SpokenWords({ clips, size = 'reply' }: { clips: SpokenClip[]; size?: keyof typeof SIZES }) {
  return (
    <p className={SIZES[size]}>
      {clips.map((clip, clipIndex) =>
        timeWords(clip).map((word, index) => (
          // Clips and their words only append, so their positions are stable keys.
          <Fragment key={`${String(clipIndex)}-${String(index)}-${word.text}`}>
            <span
              className={size === 'caption' ? 'caption-word' : 'spoken-word'}
              ref={(span) => {
                // Timed once, from when the clip started: words drawn after it began, as when
                // the page switches layout, reveal on time, and ones already said simply show.
                if (span !== null && span.style.getPropertyValue('--word-at') === '') {
                  span.style.setProperty('--word-at', `${String(Math.round(word.atMs - (performance.now() - clip.startedAt)))}ms`)
                  span.style.setProperty('--word-ms', `${String(Math.round(word.lengthMs))}ms`)
                }
              }}
            >
              {word.text}
            </span>{' '}
          </Fragment>
        )),
      )}
    </p>
  )
}

// Kokoro gives no word timings, so a word's share of the clip follows its letters, plus one
// for the gap after it.
function timeWords(clip: SpokenClip): TimedWord[] {
  const words = clip.text.split(/\s+/).filter(Boolean)
  const total = words.reduce((sum, word) => sum + word.length + 1, 0)
  let before = 0
  return words.map((text) => {
    const share = (text.length + 1) / total
    const atMs = (before / total) * clip.durationMs
    before += text.length + 1
    return { atMs, lengthMs: Math.max(SHORTEST_HIGHLIGHT_MS, share * clip.durationMs * HIGHLIGHT_STRETCH), text }
  })
}
