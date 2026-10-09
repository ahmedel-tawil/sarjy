import { type RefObject, useEffect, useRef, useState } from 'react'

import { SarjyMark } from '@/components/sarjy-mark'

// When each step starts, from the moment the page appears (D-80).
const DOCK_AT_MS = 1300
const ORB_FORMS_AT_MS = 1850
const DONE_AT_MS = 2150

// Every visit opens with the welcome; under reduced motion the page simply appears.
export function wantsWelcome(): boolean {
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

interface FirstLoadProps {
  // Called as the gathered dots reach the orb, so it can grow out of them.
  onDocked: () => void
  // Called when the welcome is over, or skipped with a tap or a key.
  onDone: () => void
  orbRef: RefObject<HTMLButtonElement | null>
}

// The welcome: Sarjy's voice trail draws itself, its name appears, then the trail gathers
// into a ball that flies to the talk control and becomes the orb, while the page fades in.
export function FirstLoad({ onDocked, onDone, orbRef }: FirstLoadProps) {
  const markRef = useRef<HTMLDivElement>(null)
  const [docking, setDocking] = useState(false)

  useEffect(() => {
    const dock = window.setTimeout(() => {
      const mark = markRef.current
      const orb = orbRef.current?.getBoundingClientRect()
      if (mark !== null && orb !== undefined) {
        const from = mark.getBoundingClientRect()
        mark.style.setProperty('--dock-x', `${String(orb.x + orb.width / 2 - (from.x + from.width / 2))}px`)
        mark.style.setProperty('--dock-y', `${String(orb.y + orb.height / 2 - (from.y + from.height / 2))}px`)
      }
      setDocking(true)
    }, DOCK_AT_MS)
    const formOrb = window.setTimeout(onDocked, ORB_FORMS_AT_MS)
    const done = window.setTimeout(onDone, DONE_AT_MS)
    // Any key skips the welcome, as a tap does.
    const skip = (): void => {
      onDocked()
      onDone()
    }
    window.addEventListener('keydown', skip)
    return () => {
      window.clearTimeout(dock)
      window.clearTimeout(formOrb)
      window.clearTimeout(done)
      window.removeEventListener('keydown', skip)
    }
  }, [onDocked, onDone, orbRef])

  return (
    <div
      aria-hidden="true"
      className="first-load"
      data-docking={docking ? '' : undefined}
      onPointerDown={() => {
        onDocked()
        onDone()
      }}
    >
      <div className="flex items-center gap-4">
        <div className="first-load-mark" ref={markRef}>
          <SarjyMark className="size-full" drawing />
        </div>
        <span className="first-load-word">sarjy</span>
      </div>
    </div>
  )
}
