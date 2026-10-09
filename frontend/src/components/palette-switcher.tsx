import { Button } from '@/components/ui/button'

// Three palettes, each a block of tokens in index.css, switched by data-palette on <html>
// (D-80). The visitor's choice is kept in this browser; without one, a system in dark mode
// starts in Night.

export const PALETTES = ['pearl', 'night', 'coral'] as const

export type Palette = (typeof PALETTES)[number]

const NAMES: Record<Palette, string> = { coral: 'Coral', night: 'Night', pearl: 'Pearl' }

const SWATCHES: Record<Palette, string> = {
  coral: 'size-4 rounded-full bg-swatch-coral',
  night: 'size-4 rounded-full bg-swatch-night ring-1 ring-foreground/20',
  pearl: 'size-4 rounded-full bg-swatch-pearl',
}

const STORAGE_KEY = 'sarjy.palette'

export function applyPalette(palette: Palette): void {
  document.documentElement.dataset.palette = palette
  // shadcn's components switch their dark-mode details on this class.
  document.documentElement.classList.toggle('dark', palette === 'night')
  try {
    window.localStorage.setItem(STORAGE_KEY, palette)
  } catch {
    // Private windows can refuse storage; the palette still applies for this visit.
  }
}

export function initialPalette(): Palette {
  let saved: null | string = null
  try {
    saved = window.localStorage.getItem(STORAGE_KEY)
  } catch {
    // Storage refused: fall back to the system's preference.
  }
  const chosen = PALETTES.find((palette) => palette === saved)
  if (chosen !== undefined) {
    return chosen
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'night' : 'pearl'
}

interface PaletteSwitcherProps {
  onChange: (palette: Palette) => void
  palette: Palette
}

export function PaletteSwitcher({ onChange, palette }: PaletteSwitcherProps) {
  return (
    <div aria-label="Colours" className="flex gap-1" role="group">
      {PALETTES.map((option) => (
        <Button
          aria-label={`${NAMES[option]} colours`}
          aria-pressed={option === palette}
          key={option}
          onClick={() => {
            onChange(option)
          }}
          size="icon-sm"
          title={NAMES[option]}
          variant={option === palette ? 'secondary' : 'ghost'}
        >
          <span className={SWATCHES[option]} />
        </Button>
      ))}
    </div>
  )
}
