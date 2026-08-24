import { createContext, useContext } from 'react'

/**
 * Split out from audioPlayer.tsx: a file that exports both a component and a
 * hook trips `react-refresh/only-export-components` under `--max-warnings=0`.
 * The context and the hook that reads it have no JSX, so they live here.
 */
export type AudioContextValue = {
  /** No melody uploaded yet — the toggle has nothing to control. */
  available: boolean
  muted: boolean
  toggleMuted: () => void
}

export const AudioPlayerContext = createContext<AudioContextValue | null>(null)

export function useAudioPlayer() {
  const context = useContext(AudioPlayerContext)
  if (!context) throw new Error('useAudioPlayer must be used inside AudioProvider')
  return context
}
