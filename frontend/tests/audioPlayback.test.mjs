import assert from 'node:assert/strict'
import test from 'node:test'

import { createPlaybackRetry, pauseImmediately, requestPlayback } from '../src/lib/audioPlayback.ts'

test('requestPlayback calls play synchronously in the trusted event stack', async () => {
  let calls = 0
  const audio = {
    play() {
      calls += 1
      return Promise.resolve()
    },
    pause() {},
  }

  const result = requestPlayback(audio)
  assert.equal(calls, 1, 'play() must run before the click handler returns')
  assert.equal(await result, true)
})

test('a browser autoplay rejection is handled without throwing', async () => {
  const audio = {
    play() { return Promise.reject(new Error('autoplay blocked')) },
    pause() {},
  }

  assert.equal(await requestPlayback(audio), false)
})

test('muting pauses synchronously', () => {
  let paused = false
  pauseImmediately({ play: () => Promise.resolve(), pause: () => { paused = true } })
  assert.equal(paused, true)
})

test('gesture playback is re-armed after a rejected attempt', async () => {
  let calls = 0
  const retry = createPlaybackRetry(async () => {
    calls += 1
    return calls > 1
  })

  assert.equal(await retry(), false)
  assert.equal(await retry(), true)
  assert.equal(calls, 2)
})

test('gesture playback deduplicates concurrent activation events', async () => {
  let calls = 0
  let release
  const pending = new Promise(resolve => { release = resolve })
  const retry = createPlaybackRetry(async () => {
    calls += 1
    await pending
    return true
  })

  const first = retry()
  const second = retry()
  assert.equal(first, second)
  assert.equal(calls, 1)
  release()
  assert.equal(await first, true)
})
