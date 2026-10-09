import { useCallback, useEffect, useRef } from 'react'

// Speech sits between these levels; quieter reads as 0 and louder as 1.
const QUIET_DBFS = -60
const LOUD_DBFS = -15

// A microphone meter of the page's own, so the orb can follow the traveller's voice
// without changing frontend/src/lib. It opens a second stream while the orb is held;
// once the recorder exposes its level (asked of M3, D-80), this hook goes away.
export function useMicLevel(active: boolean): () => number {
  const level = useRef(0)

  useEffect(() => {
    if (!active) {
      return
    }
    let closed = false
    let frame = 0
    let stream: MediaStream | null = null
    let context: AudioContext | null = null

    const measure = (analyser: AnalyserNode, samples: Float32Array<ArrayBuffer>): void => {
      analyser.getFloatTimeDomainData(samples)
      let sumOfSquares = 0
      for (const sample of samples) {
        sumOfSquares += sample * sample
      }
      const dbfs = 20 * Math.log10(Math.sqrt(sumOfSquares / samples.length) || 1e-6)
      level.current = Math.min(1, Math.max(0, (dbfs - QUIET_DBFS) / (LOUD_DBFS - QUIET_DBFS)))
      frame = requestAnimationFrame(() => {
        measure(analyser, samples)
      })
    }

    const open = async (): Promise<void> => {
      const opened = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream = opened
      if (closed) {
        stopTracks(opened)
        return
      }
      context = new AudioContext()
      const analyser = context.createAnalyser()
      context.createMediaStreamSource(opened).connect(analyser)
      measure(analyser, new Float32Array(analyser.fftSize))
    }

    open().catch(() => {
      // Without a meter the orb simply stays calm; the recording itself is unaffected.
      level.current = 0
    })

    return () => {
      closed = true
      cancelAnimationFrame(frame)
      if (stream !== null) {
        stopTracks(stream)
      }
      context?.close().catch(() => {
        // The context is being thrown away either way.
      })
      level.current = 0
    }
  }, [active])

  return useCallback(() => level.current, [])
}

function stopTracks(stream: MediaStream): void {
  for (const track of stream.getTracks()) {
    track.stop()
  }
}
