import { z } from 'zod'

// Mirrors gateway/src/sarjy_gateway/messages.py; change both together. Wire keys keep the
// gateway's snake_case, so they are quoted here and read with brackets.

const ErrorCodeSchema = z.enum([
  'forget_failed',
  'invalid_message',
  'llm_failed',
  'no_audio',
  'no_speech',
  'rate_limited',
  'stt_failed',
  'too_many_turns',
  'tts_failed',
  'turn_too_long',
  'unknown_voice',
  'visit_limit',
])

export type ErrorCode = z.infer<typeof ErrorCodeSchema>

const RememberedFactSchema = z.object({ key: z.string(), value: z.string() })

export type RememberedFact = z.infer<typeof RememberedFactSchema>

// A tour the reply names, with its page on the Magic Experience website (D-90).
const TourLinkSchema = z.object({ name: z.string(), url: z.url() })

export type TourLink = z.infer<typeof TourLinkSchema>

export const ServerMessageSchema = z.discriminatedUnion('type', [
  z.object({ code: ErrorCodeSchema, 'turn_id': z.string().nullable(), type: z.literal('error') }),
  z.object({ text: z.string(), 'turn_id': z.string(), type: z.literal('transcript') }),
  z.object({ links: z.array(TourLinkSchema), text: z.string(), 'turn_id': z.string(), type: z.literal('reply') }),
  // Announces the binary WAV frame that comes next, which cannot carry the turn id itself,
  // with the words it speaks: the whole reply, or one sentence when streaming.
  z.object({ text: z.string(), 'turn_id': z.string(), type: z.literal('audio') }),
  // The gateway's marks, in milliseconds since `audio_received` on its own clock.
  z.object({ marks: z.record(z.string(), z.number()), 'turn_id': z.string(), type: z.literal('marks') }),
  // Everything Sarjy remembers, sent in full when the visit starts and after every change.
  z.object({ facts: z.array(RememberedFactSchema), type: z.literal('memory') }),
])

export type ServerMessage = z.infer<typeof ServerMessageSchema>

export const TURN_END_MESSAGE = JSON.stringify({ type: 'turn_end' })

export const TURN_CANCEL_MESSAGE = JSON.stringify({ type: 'turn_cancel' })

export const FORGET_ME_MESSAGE = JSON.stringify({ type: 'forget_me' })

export function setVoiceMessage(voice: string): string {
  return JSON.stringify({ type: 'set_voice', voice })
}

export function browserMarksMessage(turnId: string, speechEnd: number, playbackStart: number): string {
  return JSON.stringify({ 'playback_start': playbackStart, 'speech_end': speechEnd, 'turn_id': turnId, 'type': 'browser_marks' })
}
