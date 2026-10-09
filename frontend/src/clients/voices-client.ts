import { z } from 'zod'

// A slow TTS start shouldn't hang the picker; it simply shows the default until reopened.
const TIMEOUT_MS = 5000

const VoiceListSchema = z.object({ default: z.string(), voices: z.array(z.string()) })

// The voices the TTS service carries, by Kokoro id (af_heart, am_adam…), and its default.
export type VoiceList = z.infer<typeof VoiceListSchema>

export interface VoiceCatalogue {
  list(): Promise<VoiceList>
}

// For the voice picker (M4.9): the gateway's GET /voices, which answers 503 while TTS is
// unreachable.
export class VoicesClient implements VoiceCatalogue {
  async list(): Promise<VoiceList> {
    const response = await fetch('/voices', { signal: AbortSignal.timeout(TIMEOUT_MS) })
    if (!response.ok) {
      throw new Error(`GET /voices answered ${String(response.status)}`)
    }
    return VoiceListSchema.parse(await response.json())
  }
}
