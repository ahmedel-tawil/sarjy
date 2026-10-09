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
  'tts_failed',
  'turn_too_long',
  'unknown_voice',
])

export type ErrorCode = z.infer<typeof ErrorCodeSchema>

const RememberedFactSchema = z.object({ key: z.string(), value: z.string() })

export type RememberedFact = z.infer<typeof RememberedFactSchema>

export const ServerMessageSchema = z.discriminatedUnion('type', [
  z.object({ code: ErrorCodeSchema, 'turn_id': z.string().nullable(), type: z.literal('error') }),
  z.object({ text: z.string(), 'turn_id': z.string(), type: z.literal('transcript') }),
  z.object({ text: z.string(), 'turn_id': z.string(), type: z.literal('reply') }),
  // Announces the binary WAV frame that comes next, which cannot carry the turn id itself.
  z.object({ 'turn_id': z.string(), type: z.literal('audio') }),
  // The gateway's marks, in milliseconds since `audio_received` on its own clock.
  z.object({ marks: z.record(z.string(), z.number()), 'turn_id': z.string(), type: z.literal('marks') }),
  // Everything Sarjy remembers, sent in full when the visit starts and after every change.
  z.object({ facts: z.array(RememberedFactSchema), type: z.literal('memory') }),
])

export type ServerMessage = z.infer<typeof ServerMessageSchema>

export const TURN_END_MESSAGE = JSON.stringify({ type: 'turn_end' })

export const TURN_CANCEL_MESSAGE = JSON.stringify({ type: 'turn_cancel' })

export const FORGET_ME_MESSAGE = JSON.stringify({ type: 'forget_me' })

export function browserMarksMessage(turnId: string, speechEnd: number, playbackStart: number): string {
  return JSON.stringify({ 'playback_start': playbackStart, 'speech_end': speechEnd, 'turn_id': turnId, 'type': 'browser_marks' })
}
