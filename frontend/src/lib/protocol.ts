import { z } from 'zod'

// Mirrors gateway/src/sarjy_gateway/messages.py; change both together.

export const ServerErrorSchema = z.object({
  code: z.enum(['invalid_message', 'no_audio', 'turn_too_long']),
  type: z.literal('error'),
})

export type ServerError = z.infer<typeof ServerErrorSchema>

export const TURN_END_MESSAGE = JSON.stringify({ type: 'turn_end' })
