/**
 * A compact "take a booking" call-to-action sits in the header next to the
 * language switch -- the client asked for a fast way into the ticket
 * flow right from the main screen, without floating over the catalog.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { URL } from 'node:url'

const frontend = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const cta = frontend('src/components/TakeBookingCta.tsx')
const home = frontend('src/pages/Home.tsx')
const shell = frontend('src/components/Shell.tsx')
const ru = frontend('src/i18n/ru.ts')
const uz = frontend('src/i18n/uz.ts')

test('the CTA links straight into the ticket flow', () => {
  assert.match(cta, /to=.\/tickets./)
})

test('the CTA is docked in the header, not floating over the catalog', () => {
  assert.match(shell, /headerExtra/, 'Shell must accept a header slot for the CTA')
  assert.doesNotMatch(cta, /position:\s*fixed/)
})

test('Home renders the CTA in the header', () => {
  assert.match(home, /TakeBookingCta/)
  assert.match(home, /from '..\/components\/TakeBookingCta'/)
  assert.match(home, /headerExtra=\{<TakeBookingCta/)
})

test('the button text exists in both languages and is not the raw tab label', () => {
  assert.match(ru, /takeBooking:/)
  assert.match(uz, /takeBooking:/)
})
