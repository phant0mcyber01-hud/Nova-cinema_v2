export const AUDIO_CHUNK_BYTES = 1_000_000
export const AUDIO_MAX_BYTES = 50_000_000

export type AudioChunkRange = { start: number; end: number }

/** Deterministic ranges keep every multipart request below the proxy's 10 MB cap. */
export function audioChunkRanges(size: number): AudioChunkRange[] {
  if (!Number.isSafeInteger(size) || size <= 0) throw new Error('Audio file is empty')
  if (size > AUDIO_MAX_BYTES) throw new Error('Audio file exceeds 50 MB')
  const ranges: AudioChunkRange[] = []
  for (let start = 0; start < size; start += AUDIO_CHUNK_BYTES) {
    ranges.push({ start, end: Math.min(start + AUDIO_CHUNK_BYTES, size) })
  }
  return ranges
}

/** 128 bits encoded as lowercase hex; the server accepts no path characters. */
export function createAudioUploadId(): string {
  const bytes = new Uint8Array(16)
  globalThis.crypto.getRandomValues(bytes)
  return Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('')
}
