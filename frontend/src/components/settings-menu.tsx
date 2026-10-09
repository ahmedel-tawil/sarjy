import { Settings02Icon } from '@hugeicons/core-free-icons'
import { HugeiconsIcon } from '@hugeicons/react'

import type { TalkMode } from '@/components/talk-mode'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverHeader, PopoverTitle, PopoverTrigger } from '@/components/ui/popover'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { VoicePicker } from '@/components/voice-picker'

interface SettingsMenuProps {
  // While a turn runs the settings wait, so a change can't land half-way through it.
  busy: boolean
  onTalkMode: (mode: TalkMode) => void
  onVoice: (voice: string) => void
  talkMode: TalkMode
  // The voice in use and the ones TTS offers; null hides the voice setting (D-82).
  voice: null | string
  voices: null | string[]
}

const TALK_CHOICES: readonly { description: string; label: string; mode: TalkMode }[] = [
  { description: 'Hold the orb, or Space, while you speak.', label: 'Hold to talk', mode: 'hold' },
  { description: 'Tap once to start and again to send. Space works the same way.', label: 'Tap to talk', mode: 'tap' },
]

// A gear beside the colour swatches opens Sarjy's settings: its voice, and how you talk to
// it (D-83).
export function SettingsMenu({ busy, onTalkMode, onVoice, talkMode, voice, voices }: SettingsMenuProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button aria-label="Settings" size="icon-sm" title="Settings" variant="ghost">
          <HugeiconsIcon icon={Settings02Icon} />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end">
        <div className="flex flex-col gap-5">
          <PopoverHeader>
            <PopoverTitle>Settings</PopoverTitle>
          </PopoverHeader>
          {voice !== null && voices !== null ? (
            <VoicePicker disabled={busy} onChoose={onVoice} voice={voice} voices={voices} />
          ) : null}
          <fieldset className="flex flex-col gap-3" disabled={busy}>
            <legend className="pb-3 text-sm font-medium">How you talk</legend>
            <RadioGroup
              onValueChange={(value) => {
                const chosen = TALK_CHOICES.find((choice) => choice.mode === value)
                if (chosen !== undefined) {
                  onTalkMode(chosen.mode)
                }
              }}
              value={talkMode}
            >
              {TALK_CHOICES.map((choice) => (
                <label className="flex items-start gap-3" htmlFor={`talk-${choice.mode}`} key={choice.mode}>
                  <RadioGroupItem id={`talk-${choice.mode}`} value={choice.mode} />
                  <span className="flex flex-col gap-0.5">
                    <span className="text-sm font-medium">{choice.label}</span>
                    <span className="text-sm text-muted-foreground">{choice.description}</span>
                  </span>
                </label>
              ))}
            </RadioGroup>
          </fieldset>
        </div>
      </PopoverContent>
    </Popover>
  )
}
