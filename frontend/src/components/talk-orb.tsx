import { type RefObject, useEffect, useRef } from 'react'

import { type OrbPhase, OrbRenderer } from '@/components/orb-renderer'
import type { AudioLevels } from '@/lib/voice-session'

interface TalkOrbProps {
  // The orb grows in when revealed, rather than simply being there.
  animateIn: boolean
  // The id of the line under the orb, read out as its current state (D-83).
  describedBy: string
  disabled: boolean
  // What the orb does when pressed: hold or tap, to talk or to send.
  label: string
  // The microphone while the orb is held, and Sarjy's voice while it speaks.
  levels: AudioLevels
  onPress: () => void
  onRelease: () => void
  orbRef: RefObject<HTMLButtonElement | null>
  // Changing it re-reads the orb's colours from the stylesheet.
  palette: string
  phase: OrbPhase
  revealed: boolean
}

// The talk control is Sarjy itself: hold or tap the orb to speak to it.
export function TalkOrb({ animateIn, describedBy, disabled, label, levels, onPress, onRelease, orbRef, palette, phase, revealed }: TalkOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rendererRef = useRef<null | OrbRenderer>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (canvas === null) {
      return
    }
    const renderer = new OrbRenderer(canvas, levels, animateIn)
    rendererRef.current = renderer
    renderer.start()
    return () => {
      renderer.stop()
      rendererRef.current = null
    }
  }, [animateIn, levels])

  useEffect(() => {
    if (animateIn && revealed) {
      rendererRef.current?.assemble()
    }
  }, [animateIn, revealed])

  useEffect(() => {
    rendererRef.current?.setPhase(phase)
  }, [phase])

  useEffect(() => {
    rendererRef.current?.refreshColours()
  }, [palette])

  return (
    // Holding a button on a phone would otherwise scroll, select text or open a menu.
    <div className="touch-none select-none">
      <button
        aria-describedby={describedBy}
        aria-keyshortcuts="Space"
        aria-label={label}
        aria-pressed={phase === 'listening'}
        className="talk-orb"
        disabled={disabled}
        onContextMenu={(event) => {
          event.preventDefault()
        }}
        onPointerCancel={onRelease}
        onPointerDown={onPress}
        onPointerLeave={onRelease}
        onPointerUp={onRelease}
        ref={orbRef}
        type="button"
      >
        <canvas aria-hidden="true" className="size-full" ref={canvasRef} />
      </button>
    </div>
  )
}
