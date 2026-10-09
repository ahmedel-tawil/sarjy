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

interface MemoryPanelProps {
  // While a turn runs, Forget me waits, so it can't race the turn's own saves.
  busy: boolean
  facts: RememberedFact[]
  onForgetMe: () => void
}

export function MemoryPanel({ busy, facts, onForgetMe }: MemoryPanelProps) {
  return (
    <div className="w-full max-w-sm">
      <Card size="sm">
        <CardHeader>
          <CardTitle>What Sarjy remembers</CardTitle>
          <CardAction>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button disabled={busy || facts.length === 0} size="sm" variant="ghost">
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
          </CardAction>
        </CardHeader>
        <CardContent>
          {facts.length === 0 ? (
            <p className="text-muted-foreground">Nothing yet. Tell Sarjy what you like, and it will remember.</p>
          ) : (
            <dl className="flex flex-col gap-1">
              {facts.map((fact) => (
                <div className="flex justify-between gap-4" key={fact.key}>
                  <dt className="text-muted-foreground">{label(fact.key)}</dt>
                  <dd className="text-right">{fact.value}</dd>
                </div>
              ))}
            </dl>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// Keys are saved as favourite_colour; people read "Favourite colour".
function label(key: string): string {
  const words = key.replaceAll('_', ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}
