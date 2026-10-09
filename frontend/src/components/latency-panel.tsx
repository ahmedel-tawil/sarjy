import { cn } from 'cn'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { TurnStages } from '@/lib/stages-of'

// Bars are drawn against this many seconds, so a slow turn reads as long at a glance.
const SCALE_MS = 6000
const RECENT_TURNS = 5

// The stages of a turn in the order they happen, each with its own chart colour (D-79).
const STAGES = [
  { key: 'stt', label: 'Speech to text', tone: 'bg-chart-1' },
  { key: 'firstWord', label: 'First word', tone: 'bg-chart-2' },
  { key: 'firstSentence', label: 'First sentence', tone: 'bg-chart-3' },
  { key: 'tts', label: 'Voice', tone: 'bg-chart-4' },
  { key: 'network', label: 'Network', tone: 'bg-chart-5' },
] as const

export interface TimedTurn {
  id: number
  // Null until the gateway's marks have arrived, or in a rehearsal.
  stages: null | TurnStages
  ttfaMs: number
}

interface LatencyPanelProps {
  // This visit's answered turns, oldest first.
  turns: TimedTurn[]
}

// The live waterfall (M3.2): the last turn's time to first audio as the headline, then
// the last few turns as bars split into their stages, all on one scale for comparison.
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
              {seconds(last.ttfaMs)} s <span className="text-sm font-normal text-muted-foreground">to first audio</span>
            </p>
            <ol aria-label="Recent turns" className="flex flex-col gap-1.5">
              {recent.map((turn) => (
                <li className="flex items-center gap-2 text-xs text-muted-foreground tabular-nums" key={turn.id}>
                  <TurnBar turn={turn} />
                  {seconds(turn.ttfaMs)} s
                </li>
              ))}
            </ol>
            {last.stages === null ? null : <StageLegend stages={last.stages} />}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function StageLegend({ stages }: { stages: TurnStages }) {
  return (
    <dl aria-label="Where the last turn's time went" className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
      {STAGES.map((stage) => (
        <div className="flex items-center gap-1.5" key={stage.key}>
          <span aria-hidden="true" className={cn('size-2 rounded-full', stage.tone)} />
          <dt className="text-muted-foreground">{stage.label}</dt>
          <dd className="tabular-nums">{seconds(stages[stage.key])} s</dd>
        </div>
      ))}
    </dl>
  )
}

// One turn as a bar as long as its time to first audio, split into its stages.
function TurnBar({ turn }: { turn: TimedTurn }) {
  const { stages } = turn
  const label =
    stages === null
      ? `${seconds(turn.ttfaMs)} seconds to first audio`
      : STAGES.map((stage) => `${stage.label} ${seconds(stages[stage.key])} s`).join(', ')
  return (
    <span
      aria-label={label}
      className="latency-bar"
      ref={(bar) => {
        bar?.style.setProperty('--share', share(turn.ttfaMs, SCALE_MS))
      }}
      role="img"
    >
      {stages === null
        ? null
        : STAGES.map((stage) => (
            <span
              className={cn('latency-segment', stage.tone)}
              key={stage.key}
              ref={(segment) => {
                segment?.style.setProperty('--share', share(stages[stage.key], stages.ttfa))
              }}
            />
          ))}
    </span>
  )
}

function seconds(milliseconds: number): string {
  return (milliseconds / 1000).toFixed(1)
}

function share(part: number, whole: number): string {
  return `${String(Math.min(100, (part / whole) * 100))}%`
}
