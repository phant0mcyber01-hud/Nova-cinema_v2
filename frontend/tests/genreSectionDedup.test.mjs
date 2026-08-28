import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { URL } from 'node:url'

const home = readFileSync(new URL('../src/pages/Home.tsx', import.meta.url), 'utf8')

test('genre labels are canonicalized before filtering and section generation', () => {
  assert.match(home, /const canonicalGenre/)
  assert.match(home, /split\(', '\)|split\(','\)/)
  assert.match(home, /map\(canonicalGenre\)/)
})
