/**
 * A floating "take a booking" call-to-action sits above the bottom nav on the
 * poster screen (Home) -- the client asked for a fast way into the ticket
 * flow right from the main screen, not only through the Tickets tab.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { URL } from 'node:url'

const frontend = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const cta = frontend('src/components/TakeBookingCta.tsx')
const home = frontend('src/pages/Home.tsx')
const css = frontend('src/styles.css')
const ru = frontend('src/i18n/ru.ts')
const uz = frontend('src/i18n/uz.ts')

test('the CTA links straight into the ticket flow', () => {
  assert.match(cta, /to=.\/tickets./)
})

test('the CTA sits above the bottom nav, not overlapping it', () => {
  // bottom-nav is `position: fixed; bottom: 0`; the CTA must be a separate
  // fixed element with its own higher `bottom` offset so it floats just
  // above the tab bar instead of sitting behind or on top of it.
  const block = css.match(/\.take-booking-cta\s*\{[^}]*\}/)?.[0] ?? ''
  assert.match(block, /position:\s*fixed/)
  assert.match(block, /bottom:/)
  assert.doesNotMatch(block, /bottom:\s*0[^.\d]/, 'must float above the nav, not sit at the very bottom')
})

test('Home renders the CTA', () => {
  assert.match(home, /TakeBookingCta/)
  assert.match(home, /from '..\/components\/TakeBookingCta'/)
})

test('the button text exists in both languages and is not the raw tab label', () => {
  assert.match(ru, /takeBooking:/)
  assert.match(uz, /takeBooking:/)
})
