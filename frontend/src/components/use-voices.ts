import { useEffect, useState } from 'react'

import type { VoiceCatalogue, VoiceList } from '@/clients/voices-client'

// The voices TTS offers, or null while unknown or unreachable, in which case no picker shows
// and Sarjy keeps the voice it has (D-82).
export function useVoices(catalogue: VoiceCatalogue): null | VoiceList {
  const [voices, setVoices] = useState<null | VoiceList>(null)

  useEffect(() => {
    let current = true
    const load = async (): Promise<void> => {
      const list = await catalogue.list()
      if (current) {
        setVoices(list)
      }
    }
    load().catch(() => {
      setVoices(null)
    })
    return () => {
      current = false
    }
  }, [catalogue])

  return voices
}
