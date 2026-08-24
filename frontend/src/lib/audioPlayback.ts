export type PlayableAudio = Pick<HTMLMediaElement, 'play' | 'pause'>

/**
 * Call play() before returning to the browser so a trusted tap is not lost.
 * Policy failures are an expected boolean result, not an unhandled rejection.
 */
export function requestPlayback(audio: PlayableAudio): Promise<boolean> {
  try {
    return Promise.resolve(audio.play()).then(
      () => true,
      () => false,
    )
  } catch {
    return Promise.resolve(false)
  }
}

/** Pausing is synchronous and should happen in the same UI event as muting. */
export function pauseImmediately(audio: PlayableAudio): void {
  audio.pause()
}

/** Deduplicate simultaneous gestures, then re-arm after the attempt settles. */
export function createPlaybackRetry(attempt: () => Promise<boolean>): () => Promise<boolean> {
  let inFlight: Promise<boolean> | null = null
  return () => {
    if (inFlight) return inFlight
    let current: Promise<boolean>
    try {
      current = attempt()
    } catch {
      current = Promise.resolve(false)
    }
    const tracked = current.finally(() => {
      if (inFlight === tracked) inFlight = null
    })
    inFlight = tracked
    return tracked
  }
}
