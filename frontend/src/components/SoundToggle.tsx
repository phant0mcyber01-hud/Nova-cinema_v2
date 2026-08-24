import { useAudioPlayer } from '../lib/audioContext'
import { haptic } from '../lib/haptic'

/** Mutes the cinema melody that plays across the whole Mini App. */
export default function SoundToggle() {
  const { available, muted, toggleMuted } = useAudioPlayer()

  // Nothing to toggle until the admin uploads a melody.
  if (!available) return null

  return (
    <button
      className={`sound-toggle ${muted ? 'muted' : 'on'}`}
      type="button"
      aria-label="Sound"
      aria-pressed={!muted}
      onClick={() => { haptic.tap(); toggleMuted() }}
    >
      {muted ? '⊘' : '♫'}
    </button>
  )
}
