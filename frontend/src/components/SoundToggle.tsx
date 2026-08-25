import { useAudioPlayer } from '../lib/audioContext'
import { haptic } from '../lib/haptic'
import Icon from './Icon'

/** Mutes the cinema melody that plays across the whole Mini App. */
export default function SoundToggle() {
  const { available, muted, playing, toggleMuted } = useAudioPlayer()

  // Nothing to toggle until the admin uploads a melody.
  if (!available) return null
  const active = !muted && playing

  return (
    <button
      className={`sound-toggle ${active ? 'on' : 'muted'}`}
      type="button"
      aria-label="Sound"
      aria-pressed={active}
      onClick={() => { haptic.tap(); toggleMuted() }}
    >
      <Icon name={active ? 'music' : 'muted'} />
    </button>
  )
}
