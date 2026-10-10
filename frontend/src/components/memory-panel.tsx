import { type RefObject, useLayoutEffect, useRef } from 'react'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { RememberedFact } from '@/lib/protocol'

const FLY_MS = 600

interface MemoryPanelProps {
  // While a turn runs, Forget me waits, so it can't race the turn's own saves.
  busy: boolean
  facts: RememberedFact[]
  onForgetMe: () => void
  // A newly saved fact flies out of the orb onto the shelf.
  orbRef: RefObject<HTMLButtonElement | null>
}

export function MemoryPanel({ busy, facts, onForgetMe, orbRef }: MemoryPanelProps) {
  const chipRefs = useRef(new Map<string, HTMLLIElement>())
  // Null until the first list arrives: facts known when the page opens don't fly.
  const known = useRef<null | Set<string>>(null)

  useLayoutEffect(() => {
    const before = known.current
    known.current = new Set(facts.map((fact) => `${fact.key}=${fact.value}`))
    const orb = orbRef.current?.getBoundingClientRect()
    if (before === null || orb === undefined || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return
    }
    for (const fact of facts) {
      const chip = chipRefs.current.get(fact.key)
      if (chip === undefined || before.has(`${fact.key}=${fact.value}`)) {
        continue
      }
      const box = chip.getBoundingClientRect()
      const dx = orb.x + orb.width / 2 - (box.x + box.width / 2)
      const dy = orb.y + orb.height / 2 - (box.y + box.height / 2)
      chip.animate(
        [
          { opacity: 0.2, transform: `translate(${String(dx)}px, ${String(dy)}px) scale(0.2)` },
          { opacity: 1, transform: 'none' },
        ],
        { duration: FLY_MS, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' },
      )
    }
  }, [facts, orbRef])

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>What Sarjy remembers</CardTitle>
        <CardAction>
          <ForgetMe busy={busy} empty={facts.length === 0} onForgetMe={onForgetMe} />
        </CardAction>
      </CardHeader>
      <CardContent>
        <FactList chipRefs={chipRefs} facts={facts} />
      </CardContent>
    </Card>
  )
}

interface ForgetMeProps {
  busy: boolean
  // Nothing remembered, so nothing to forget.
  empty: boolean
  onForgetMe: () => void
}

// Forget me, behind a confirmation, since it can't be undone.
export function ForgetMe({ busy, empty, onForgetMe }: ForgetMeProps) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button disabled={busy || empty} size="sm" variant="ghost">
          Forget me
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Forget what Sarjy knows about you?</AlertDialogTitle>
          <AlertDialogDescription>
            Sarjy deletes everything it remembers about you. This can’t be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep</AlertDialogCancel>
          <AlertDialogAction onClick={onForgetMe} variant="destructive">
            Forget me
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

interface FactListProps {
  // Where each chip is, for the panel's fly-in; voice mode's list has no fly-in.
  chipRefs?: RefObject<Map<string, HTMLLIElement>>
  facts: RememberedFact[]
}

// What Sarjy remembers, one chip per fact.
export function FactList({ chipRefs, facts }: FactListProps) {
  if (facts.length === 0) {
    return <p className="text-muted-foreground">Nothing yet. Tell Sarjy what you like, and it will remember.</p>
  }
  return (
    <ul className="flex flex-wrap gap-2">
      {facts.map((fact) => (
        <li
          className="flex flex-col rounded-xl bg-muted px-3 py-2"
          key={fact.key}
          ref={(element) => {
            if (element === null) {
              chipRefs?.current.delete(fact.key)
            } else {
              chipRefs?.current.set(fact.key, element)
            }
          }}
        >
          <span className="text-xs text-muted-foreground">{label(fact.key)}</span>
          <span className="font-medium">{fact.value}</span>
        </li>
      ))}
    </ul>
  )
}

// Keys are saved as favourite_colour; people read "Favourite colour".
function label(key: string): string {
  const words = key.replaceAll('_', ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}
