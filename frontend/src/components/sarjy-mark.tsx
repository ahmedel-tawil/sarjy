// Sarjy's mark: an S traced by eleven dots that grow like a voice, ending in the accent
// colour (D-80). Coordinates are in a 100-unit box; the view box crops to the dots.

interface TrailDot {
  radius: number
  x: number
  y: number
}

// Sampled evenly along two arcs, from the top right, over the top and down to the bottom left.
export const TRAIL_DOTS: readonly TrailDot[] = [
  { radius: 2.4, x: 66, y: 27.2 },
  { radius: 2.8, x: 55.8, y: 17 },
  { radius: 3.2, x: 41.5, y: 18.3 },
  { radius: 3.6, x: 33.3, y: 30 },
  { radius: 4, x: 37, y: 43.9 },
  { radius: 4.4, x: 50, y: 50 },
  { radius: 4.9, x: 63, y: 56.1 },
  { radius: 5.3, x: 66.7, y: 70 },
  { radius: 5.7, x: 58.5, y: 81.7 },
  { radius: 6.1, x: 44.2, y: 83 },
  { radius: 6.5, x: 34, y: 72.8 },
]

const VIEW_BOX = '16 8 68 84'

interface SarjyMarkProps {
  className?: string
  // On first load each dot pops in after the one before, and can later gather to the centre.
  drawing?: boolean
}

export function SarjyMark({ className, drawing = false }: SarjyMarkProps) {
  const lastIndex = TRAIL_DOTS.length - 1
  return (
    <svg aria-hidden="true" className={className} viewBox={VIEW_BOX}>
      {TRAIL_DOTS.map((dot, index) => (
        <circle
          className={`${index === lastIndex ? 'fill-primary' : 'fill-foreground'} ${drawing ? 'trail-dot' : ''}`}
          cx={dot.x}
          cy={dot.y}
          key={`${String(dot.x)},${String(dot.y)}`}
          r={dot.radius}
          ref={(circle) => {
            // The order sets each dot's delay; the offset is how far it travels to the centre.
            circle?.style.setProperty('--order', String(index))
            circle?.style.setProperty('--to-centre-x', `${String(50 - dot.x)}px`)
            circle?.style.setProperty('--to-centre-y', `${String(50 - dot.y)}px`)
          }}
        />
      ))}
    </svg>
  )
}
