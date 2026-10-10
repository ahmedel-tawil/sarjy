import { ArrowDown01Icon, PlayIcon } from '@hugeicons/core-free-icons'
import { HugeiconsIcon } from '@hugeicons/react'

import { type SpokenClip, SpokenWords } from '@/components/spoken-words'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import type { EarlierVisit } from '@/lib/protocol'

// When a visit started, in the visitor's own time: "Thursday 8 Oct, 9:40 pm".
const VISIT_TIME = new Intl.DateTimeFormat(undefined, {
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  month: 'short',
  weekday: 'long',
})

// The earlier answer being spoken again, and its clips so far.
export interface Replay {
  clips: SpokenClip[]
  turnId: string
}

interface EarlierVisitsProps {
  // While anything runs, replay waits, as turns do: one thing at a time.
  busy: boolean
  onReplay: (turnId: string) => void
  replay: null | Replay
  // Newest first, as the gateway sends them (D-92).
  visits: EarlierVisit[]
}

// The visitor's earlier visits above today's conversation, oldest at the top so the thread
// reads in time order. The most recent is open; older ones are folded (D-84).
export function EarlierVisits({ busy, onReplay, replay, visits }: EarlierVisitsProps) {
  const oldestFirst = visits.toReversed()
  return (
    <section aria-label="Earlier visits" className="flex flex-col gap-4 pb-8">
      {oldestFirst.map((visit, index) => (
        <Collapsible defaultOpen={index === oldestFirst.length - 1} key={visit['started_at']}>
          <CollapsibleTrigger asChild>
            <Button size="sm" variant="ghost">
              <HugeiconsIcon className="transition-transform group-data-[state=open]/button:rotate-180" data-icon="inline-start" icon={ArrowDown01Icon} />
              {VISIT_TIME.format(new Date(visit['started_at']))}
              <span aria-hidden="true">·</span>
              {visit.turns.length === 1 ? '1 question' : `${String(visit.turns.length)} questions`}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <ol className="flex flex-col gap-5 pt-3 pl-6">
              {visit.turns.map((turn) => {
                const replaying = replay?.turnId === turn['turn_id'] ? replay : null
                return (
                  <li className="flex flex-col gap-2" key={turn['turn_id']}>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-xs font-medium text-muted-foreground">You</span>
                      <p className="text-sm text-muted-foreground">{turn.transcript}</p>
                    </div>
                    <div className="flex flex-col gap-0.5">
                      <div className="flex items-center gap-1">
                        <span className="text-xs font-medium text-primary">Sarjy</span>
                        <Button
                          aria-label="Hear this answer again"
                          disabled={busy}
                          onClick={() => {
                            onReplay(turn['turn_id'])
                          }}
                          size="icon-xs"
                          title="Hear this answer again"
                          variant="ghost"
                        >
                          <HugeiconsIcon icon={PlayIcon} />
                        </Button>
                      </div>
                      {replaying !== null && replaying.clips.length > 0 ? (
                        <SpokenWords clips={replaying.clips} size="earlier" />
                      ) : (
                        <p className="text-pretty">{turn.reply}</p>
                      )}
                    </div>
                  </li>
                )
              })}
            </ol>
          </CollapsibleContent>
        </Collapsible>
      ))}
      <p className="pt-2 text-xs font-medium text-muted-foreground">This visit</p>
    </section>
  )
}
