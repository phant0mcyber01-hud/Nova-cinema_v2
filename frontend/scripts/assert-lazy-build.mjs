import assert from 'node:assert/strict'
import { gzipSync } from 'node:zlib'
import { readdirSync, readFileSync } from 'node:fs'
import { basename } from 'node:path'
import { stdout } from 'node:process'
import { URL } from 'node:url'

const dist = new URL('../dist/', import.meta.url)
const html = readFileSync(new URL('index.html', dist), 'utf8')
const entryMatch = html.match(/<script[^>]+src="([^"]+\.js)"/)
assert(entryMatch, 'production HTML must contain a JS entry')
assert(!html.includes('/api/melodies'), 'production HTML must not preload removed music')

const entryName = basename(entryMatch[1])
const assetsDir = new URL('assets/', dist)
const chunks = readdirSync(assetsDir).filter(name => name.endsWith('.js')).sort()
const entry = readFileSync(new URL(`assets/${entryName}`, dist))

assert(
  chunks.length >= 8,
  `expected route-level splitting (>= 8 JS chunks), found ${chunks.length}: ${chunks.join(', ')}`,
)
assert(
  entry.byteLength < 310_000,
  `entry bundle is still too large (${entry.byteLength} bytes); route pages are probably eager`,
)
assert(
  chunks.some(name => /ProtectedAdminRoute|Admin/i.test(name)),
  `admin must be outside the public entry; chunks: ${chunks.join(', ')}`,
)

stdout.write(`${JSON.stringify({
  entry: entryName,
  entryBytes: entry.byteLength,
  entryGzipBytes: gzipSync(entry).byteLength,
  jsChunkCount: chunks.length,
  chunks,
}, null, 2)}\n`)
