import { Alert02Icon, MicOff01Icon } from '@hugeicons/core-free-icons'
import { HugeiconsIcon } from '@hugeicons/react'

import { PROBLEMS } from '@/components/problems'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

interface ProblemCardsProps {
  // The microphone was refused; the card stays until the next press.
  microphone: boolean
  // The visit's question limit was reached; only a new visit can ask more.
  visitOver: boolean
}

// The two problems that need the traveller to act, shown above the orb (D-81).
export function ProblemCards({ microphone, visitOver }: ProblemCardsProps) {
  return (
    <>
      {microphone ? (
        <div className="w-full max-w-md pb-3">
          <Alert>
            <HugeiconsIcon icon={MicOff01Icon} />
            <AlertTitle>Sarjy can’t hear you yet</AlertTitle>
            <AlertDescription>{PROBLEMS['mic_unavailable'].text}</AlertDescription>
          </Alert>
        </div>
      ) : null}
      {visitOver ? (
        <div className="w-full max-w-md pb-3">
          <Alert>
            <HugeiconsIcon icon={Alert02Icon} />
            <AlertTitle>This visit is full</AlertTitle>
            <AlertDescription>{PROBLEMS['visit_limit'].text}</AlertDescription>
            <div className="col-start-2 pt-2">
              <Button
                onClick={() => {
                  window.location.reload()
                }}
                size="sm"
              >
                Start a new visit
              </Button>
            </div>
          </Alert>
        </div>
      ) : null}
    </>
  )
}
