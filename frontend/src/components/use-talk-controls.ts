import { type RefObject, useCallback, useEffect } from 'react'

import type { TalkMode } from '@/components/talk-mode'
import type { PushToTalk, Status } from '@/lib/voice-session'

interface TalkControls {
  onPress: () => void
  onRelease: () => void
}

interface TalkControlsOptions {
  orbRef: RefObject<HTMLButtonElement | null>
  // While the welcome plays, keys skip it instead of talking.
  paused: boolean
  session: PushToTalk
  status: Status
  talkMode: TalkMode
}

// The orb and the Space key in either talk mode (D-83): holding presses and releasing
// sends; tapping starts, and a second tap sends.
export function useTalkControls({ orbRef, paused, session, status, talkMode }: TalkControlsOptions): TalkControls {
  const onPress = useCallback(() => {
    if (talkMode === 'tap' && status === 'listening') {
      session.release()
      return
    }
    session.press()
  }, [session, status, talkMode])

  const onRelease = useCallback(() => {
    if (talkMode === 'hold') {
      session.release()
    }
  }, [session, talkMode])

  useEffect(() => {
    const ownsKey = (event: KeyboardEvent): boolean =>
      !paused && event.code === 'Space' && (event.target === document.body || event.target === orbRef.current)
    const down = (event: KeyboardEvent): void => {
      if (ownsKey(event)) {
        event.preventDefault()
        if (!event.repeat) {
          onPress()
        }
      }
    }
    const up = (event: KeyboardEvent): void => {
      if (ownsKey(event)) {
        onRelease()
      }
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
    }
  }, [onPress, onRelease, orbRef, paused])

  return { onPress, onRelease }
}
