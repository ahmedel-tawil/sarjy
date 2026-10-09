import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

interface VoicePickerProps {
  disabled: boolean
  onChoose: (voice: string) => void
  // The voice in use, by Kokoro id.
  voice: string
  voices: string[]
}

// Sarjy's voice, chosen beside the talk control (D-82). The gateway applies a new voice to
// the next reply and keeps it as the user's `voice` fact for their next visit (D-90).
export function VoicePicker({ disabled, onChoose, voice, voices }: VoicePickerProps) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <span>Voice</span>
      <Select disabled={disabled} onValueChange={onChoose} value={voice}>
        <SelectTrigger aria-label="Sarjy’s voice" size="sm">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {voices.map((id) => (
            <SelectItem key={id} value={id}>
              {friendlyName(id)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

// Kokoro names its voices by accent, gender and name (af_heart, am_adam); people read the
// name: Heart, Adam.
export function friendlyName(id: string): string {
  const name = id.split('_').at(-1) ?? id
  return name.charAt(0).toUpperCase() + name.slice(1)
}
