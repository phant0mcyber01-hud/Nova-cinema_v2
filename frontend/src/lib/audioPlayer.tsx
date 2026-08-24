import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'

import { getMelodies, type Melody } from '../api'
import { AudioPlayerContext } from './audioContext'

/**
 * The cinema melody belongs to the whole Mini App, not to the "About" page:
 * it starts on entry and keeps playing across navigation. That is only possible
 * if the <audio> element lives above the router, hence a context rather than a
 * hook each page calls.
 */
const mutedStorageKey = 'nova-audio-muted'

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
  const [muted, setMuted] = useState(readStoredMuted)

  // The admin can upload several melodies; the first by sort_order is the one
  // the app plays. The endpoint already returns them in that order.
  useEffect(() => {
    let active = true
    void getMelodies()
      .then(melodies => { if (active) setMelody(melodies[0] ?? null) })
      .catch(() => undefined)
    return () => { active = false }
  }, [])

  // Mobile browsers reject play() without a user gesture. A rejected promise is
  // not an error here: the track stays paused and the toggle reads "off", so
  // one tap on it starts the music.
  useEffect(() => {
    const audio = audioRef.current
    if (!audio || !melody) return
    if (muted) {
      audio.pause()
      return
    }
    void audio.play().catch(() => {
      setMuted(true)
      saveMuted(true)
    })
  }, [melody, muted])

  const toggleMuted = useCallback(() => {
    setMuted(current => {
      const next = !current
      saveMuted(next)
      return next
    })
  }, [])

  return (
    <AudioPlayerContext.Provider value={{ available: melody !== null, muted, toggleMuted }}>
      {melody && (
        <audio ref={audioRef} src={melody.file_url} loop preload="auto" aria-hidden="true" hidden />
      )}
      {children}
    </AudioPlayerContext.Provider>
  )
}
