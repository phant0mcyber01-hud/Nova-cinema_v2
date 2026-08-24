import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'

import { getMelodies, type Melody } from '../api'
import { AudioPlayerContext } from './audioContext'
import { createPlaybackRetry, pauseImmediately, requestPlayback } from './audioPlayback'

/** The audio element stays above the router, so navigation never restarts it. */
const mutedStorageKey = 'nova-audio-muted-v2'

const readStoredMuted = () => {
  try {
    return window.localStorage.getItem(mutedStorageKey) === '1'
  } catch {
    return false
  }
}

const saveMuted = (muted: boolean) => {
  try {
    window.localStorage.setItem(mutedStorageKey, muted ? '1' : '0')
  } catch {
    // Private mode without storage: the preference just lasts this visit.
  }
}

export function AudioProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [melody, setMelody] = useState<Melody | null>(null)
  const [available, setAvailable] = useState(false)
  const [muted, setMuted] = useState(readStoredMuted)
  const [playing, setPlaying] = useState(false)
  const mutedRef = useRef(muted)

  // main.tsx starts this cached request before React mounts. About reuses it.
  useEffect(() => {
    let active = true
    void getMelodies()
      .then(melodies => {
        if (!active) return
        const primary = melodies[0] ?? null
        setMelody(primary)
        setAvailable(primary !== null)
      })
      .catch(() => { if (active) setAvailable(false) })
    return () => { active = false }
  }, [])

  const attemptPlayback = useCallback((audio: HTMLAudioElement) => requestPlayback(audio), [])

  useEffect(() => { mutedRef.current = muted }, [muted])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio || !melody) return
    if (muted) {
      pauseImmediately(audio)
      setPlaying(false)
      return
    }
    // A browser policy rejection is temporary; never persist it as user mute.
    void attemptPlayback(audio)
  }, [attemptPlayback, melody, muted])

  // If autoplay is forbidden, retry during an activation-granting click/key.
  // The sound button performs its own synchronous play() call.
  useEffect(() => {
    if (!melody || muted || playing) return
    const retry = createPlaybackRetry(() => {
      const audio = audioRef.current
      if (!audio || mutedRef.current) return Promise.resolve(false)
      return attemptPlayback(audio)
    })
    const unlock = (event: Event) => {
      if (event.target instanceof Element && event.target.closest('.sound-toggle')) return
      void retry()
    }
    document.addEventListener('click', unlock, { capture: true })
    document.addEventListener('keydown', unlock, { capture: true })
    return () => {
      document.removeEventListener('click', unlock, { capture: true })
      document.removeEventListener('keydown', unlock, { capture: true })
    }
  }, [attemptPlayback, melody, muted, playing])

  useEffect(() => {
    if (!melody) return
    const resumeAfterBackground = () => {
      const audio = audioRef.current
      if (document.visibilityState === 'visible' && audio?.paused && !mutedRef.current) {
        void attemptPlayback(audio)
      }
    }
    document.addEventListener('visibilitychange', resumeAfterBackground)
    return () => document.removeEventListener('visibilitychange', resumeAfterBackground)
  }, [attemptPlayback, melody])

  const toggleMuted = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return

    if (muted || !playing) {
      mutedRef.current = false
      setMuted(false)
      saveMuted(false)
      // This must stay directly in the click stack for mobile autoplay policy.
      void attemptPlayback(audio)
      return
    }

    mutedRef.current = true
    pauseImmediately(audio)
    setPlaying(false)
    setMuted(true)
    saveMuted(true)
  }, [attemptPlayback, muted, playing])

  return (
    <AudioPlayerContext.Provider value={{ available, muted, playing, toggleMuted }}>
      {melody && (
        <audio
          ref={audioRef}
          src={melody.file_url}
          loop
          autoPlay={!muted}
          playsInline
          preload="auto"
          aria-hidden="true"
          hidden
          onCanPlay={event => { if (!mutedRef.current) void attemptPlayback(event.currentTarget) }}
          onPlaying={event => {
            if (mutedRef.current) {
              pauseImmediately(event.currentTarget)
              setPlaying(false)
            } else {
              setPlaying(true)
            }
          }}
          onEnded={event => {
            if (!mutedRef.current) {
              event.currentTarget.currentTime = 0
              void attemptPlayback(event.currentTarget)
            }
          }}
          onPause={() => setPlaying(false)}
          onError={() => { setAvailable(false); setPlaying(false) }}
        />
      )}
      {children}
    </AudioPlayerContext.Provider>
  )
}
