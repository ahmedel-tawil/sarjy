import { z } from 'zod'

// Mirrors gateway/src/sarjy_gateway/messages.py; change both together.

export const ServerErrorSchema = z.object({
  code: z.enum([
    'invalid_message',
    'llm_failed',
    'no_audio',
    'no_speech',
    'rate_limited',
    'stt_failed',
    'tts_failed',
    'turn_too_long',
    'unknown_voice',
  ]),
  type: z.literal('error'),
})

export type ServerError = z.infer<typeof ServerErrorSchema>

export const TURN_END_MESSAGE = JSON.stringify({ type: 'turn_end' })
