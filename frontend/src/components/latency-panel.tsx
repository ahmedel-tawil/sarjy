import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

// Bars are drawn against this many seconds, so a slow turn reads as long at a glance.
const SCALE_MS = 6000
const RECENT_TURNS = 5

export interface TimedTurn {
  id: number
  ttfaMs: number
}

interface LatencyPanelProps {
  // This visit's answered turns, oldest first.
  turns: TimedTurn[]
}

// Where the live waterfall (M3.2) will go. For now: the last turn's time to first audio,
// and the last few turns as bars for comparison.
export function LatencyPanel({ turns }: LatencyPanelProps) {
  const recent = turns.slice(-RECENT_TURNS)
  const last = recent.at(-1)
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>How fast Sarjy answered</CardTitle>
      </CardHeader>
      <CardContent>
        {last === undefined ? (
          <p className="text-muted-foreground">Ask something to see the time from when you let go to Sarjy’s first sound.</p>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="font-heading text-3xl font-medium tabular-nums">
              {(last.ttfaMs / 1000).toFixed(1)} s <span className="text-sm font-normal text-muted-foreground">to first audio</span>
            </p>
            <ol aria-label="Recent turns" className="flex flex-col gap-1.5">
              {recent.map((turn) => (
                <li className="flex items-center gap-2 text-xs text-muted-foreground tabular-nums" key={turn.id}>
                  <span
                    className="latency-bar"
                    ref={(bar) => {
                      bar?.style.setProperty('--share', `${String(Math.min(100, (turn.ttfaMs / SCALE_MS) * 100))}%`)
                    }}
                  />
                  {(turn.ttfaMs / 1000).toFixed(1)} s
                </li>
              ))}
            </ol>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
