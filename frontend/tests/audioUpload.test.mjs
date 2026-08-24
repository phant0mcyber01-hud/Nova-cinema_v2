import assert from 'node:assert/strict'
import test from 'node:test'

import { AUDIO_MAX_BYTES, audioChunkRanges } from '../src/lib/audioUpload.ts'

test('20+ MB audio is split below nginx 1 MiB request limit without gaps', () => {
  const size = 20_500_000
  const ranges = audioChunkRanges(size)
  assert.equal(ranges.length, 21)
  assert.deepEqual(ranges[0], { start: 0, end: 1_000_000 })
  assert.deepEqual(ranges.at(-1), { start: 20_000_000, end: size })
  for (const [index, range] of ranges.entries()) {
    assert.equal(range.start, index === 0 ? 0 : ranges[index - 1].end)
    assert(range.end - range.start <= 1_000_000)
  }
})

test('audio above 50 MB is rejected before network upload', () => {
  assert.equal(AUDIO_MAX_BYTES, 50_000_000)
  assert.throws(() => audioChunkRanges(AUDIO_MAX_BYTES + 1), /50 MB/)
})

test('empty audio is rejected before network upload', () => {
  assert.throws(() => audioChunkRanges(0), /empty/i)
})
