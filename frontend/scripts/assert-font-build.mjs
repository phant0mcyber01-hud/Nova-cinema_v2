import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import process from 'node:process'
import { fileURLToPath, URL } from 'node:url'

/** Fails the build when the shipped bundle would depend on fonts the device may not have. */
const DIST = fileURLToPath(new URL('../dist/assets/', import.meta.url))
const files = readdirSync(DIST)
const css = files.filter(name => name.endsWith('.css'))
const fonts = files.filter(name => /\.(woff2?|ttf|otf)$/.test(name))

const problems = []
if (!css.length) problems.push('No CSS bundle was produced')

const stylesheet = css.map(name => readFileSync(join(DIST, name), 'utf8')).join('\n')
const faces = stylesheet.match(/@font-face/g) ?? []

if (!faces.length) problems.push('No @font-face in the bundle: the app borrows whatever font the device has')
if (!fonts.length) problems.push('No font files in dist/assets: nothing is actually self-hosted')
if (faces.length && !/font-display:\s*swap/.test(stylesheet)) {
  problems.push('Missing font-display:swap — text stays invisible while the font downloads')
}
if (!/unicode-range:[^;]*0301/i.test(stylesheet) && !/cyrillic/i.test(stylesheet)) {
  const cyrillicFont = fonts.some(name => /cyrillic/i.test(name))
  if (!cyrillicFont) problems.push('No Cyrillic subset: Russian text falls back to a different face than Latin')
}

if (problems.length) {
  process.stdout.write(`Font check failed:\n- ${problems.join('\n- ')}\n`)
  process.exitCode = 1
} else {
  process.stdout.write(`${JSON.stringify({ fontFaces: faces.length, fontFiles: fonts.length, files: fonts }, null, 2)}\n`)
}
