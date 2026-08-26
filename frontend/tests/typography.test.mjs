import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath, URL } from 'node:url'
import test from 'node:test'

const SRC = fileURLToPath(new URL('../src/', import.meta.url))

/** Glyphs that are absent from many Android/iOS system fonts and render as tofu boxes. */
const TOFU_RISK = /[⌂▣ⓘ◉⚙⌕★✓☏⚲➤▢♫⊘✎🎬🆕🔥📤⭐🔍⏳]/u

function walk(dir) {
  const files = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) files.push(...walk(full))
    else if (/\.(tsx|ts)$/.test(entry.name)) files.push(full)
  }
  return files
}

test('no interface icon relies on a glyph missing from common device fonts', () => {
  const offenders = []
  for (const file of walk(SRC)) {
    const source = readFileSync(file, 'utf8')
    source.split('\n').forEach((line, index) => {
      if (line.trimStart().startsWith('//') || line.trimStart().startsWith('*')) return
      const hit = line.match(TOFU_RISK)
      if (hit) offenders.push(`${file.slice(SRC.length)}:${index + 1} ${hit[0]}`)
    })
  }
  assert.deepEqual(offenders, [], `Glyph icons break on devices without those code points:\n${offenders.join('\n')}`)
})

test('the interface font is bundled with the app instead of borrowed from the device', () => {
  const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'))
  const deps = { ...pkg.dependencies, ...pkg.devDependencies }
  const bundled = Object.keys(deps).some(name => name.includes('fontsource'))
  assert.ok(bundled, 'No self-hosted font package: devices without Inter installed fall back to a random face')

  const entry = readFileSync(new URL('../src/main.tsx', import.meta.url), 'utf8')
  assert.match(entry, /@fontsource-variable\/inter\/wght\.css/, 'The bundled font is never imported, so it is never shipped')

  const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8')
  assert.match(css, /font-family:\s*'Inter Variable'/)
  assert.match(css, /font-synthesis:\s*weight style/)
})

test('bold text stays bold when the bundled font has not loaded yet', () => {
  const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8')
  assert.doesNotMatch(
    css,
    /font-synthesis:\s*none/,
    'font-synthesis:none removes synthetic bold, so fallback fonts render every 800/900 weight flat',
  )
})

test('all form controls inherit one font and iOS cannot zoom the layout on focus', () => {
  const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8')
  assert.match(css, /button\s*,\s*input\s*,\s*select\s*,\s*textarea\s*\{[^}]*font:\s*inherit/s)
  assert.match(css, /max-width:\s*640px[^}]*input[^}]*font-size:\s*16px/s)
  assert.match(css, /text-size-adjust:\s*100%/)
})

test('production assets target older Telegram WebViews instead of only the developer phone', () => {
  const vite = readFileSync(new URL('../vite.config.ts', import.meta.url), 'utf8')
  const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'))
  assert.match(vite, /target:\s*\[[^\]]*es2018[^\]]*chrome69[^\]]*safari12[^\]]*\]/s)
  assert.ok(Array.isArray(pkg.browserslist) && pkg.browserslist.some(item => item.includes('Chrome >= 69')))
  assert.match(pkg.scripts.build, /check:fonts/)
})

test('compact profile stacks its booking metric before it can clip at 320 px', () => {
  const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8')
  assert.match(css, /max-width:\s*380px[\s\S]*compact-profile\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/)
  assert.match(css, /max-width:\s*380px[\s\S]*compact-profile\s*>\s*b[^}]*grid-column:\s*1/)
})

test('older CSS engines keep usable sizes when clamp and aspect-ratio are unsupported', () => {
  const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8')
  assert.match(css, /@supports\s+not\s*\(font-size:\s*clamp/)
  assert.match(css, /@supports\s+not\s*\(aspect-ratio:/)
  assert.match(css, /@supports\s+not\s*\(aspect-ratio:[\s\S]*\.trailer\s*\{[^}]*height:/)
  assert.match(css, /@supports\s+not\s*\(aspect-ratio:[\s\S]*\.seat\s*\{[^}]*height:/)
})
