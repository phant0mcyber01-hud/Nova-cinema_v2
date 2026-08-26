/**
 * The contact form on the tickets screen used the legacy `.booking-form`
 * 2-column grid (an old fixed-seat booking layout with a magic
 * `:nth-child(3)` rule). Reused on 5 different fields, that grid put the
 * "Контакты и итог" heading next to the hold-timer note in two columns, and
 * squeezed the total price against the "Отправить заявку" button -- both
 * visible readability bugs on a real device (see screenshot).
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { URL } from 'node:url'

const frontend = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const ticketsPage = frontend('src/pages/booking/TicketsPage.tsx')
const css = frontend('src/styles.css')

test('the contact section no longer reuses the legacy fixed-seat grid class', () => {
  assert.doesNotMatch(ticketsPage, /className="contact-form booking-form"/)
})

test('its own class spans full width single column, not the old 2-col nth-child(3) grid', () => {
  const block = css.match(/\.request-form\s*\{[^}]*\}/)?.[0] ?? ''
  assert.match(block, /display:\s*grid/)
  assert.doesNotMatch(css, /\.request-form input:nth-child\(3\)/, 'must not carry the old fixed-seat column hack')
})

test('the summary total is not squeezed into a row with the submit button', () => {
  // .summary-total must be its own block-level element, not inline/flex-row
  // sharing space with a sibling button on narrow screens.
  const block = css.match(/\.summary-total\s*\{[^}]*\}/)?.[0] ?? ''
  assert.match(block, /display:\s*(flex|grid)/)
  assert.match(block, /justify-content:\s*space-between|flex-direction:\s*column/)
})
