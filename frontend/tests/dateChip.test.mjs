/**
 * The date step is its own designed calendar strip, not a plain button grid.
 *
 * The client asked for the day picker specifically to look considered: each
 * day reads as weekday + day number + month, with a fill meter showing how
 * much of the hall is still free -- not a bare formatted string in a box.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { URL } from 'node:url'

const frontend = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const tickets = frontend('src/pages/booking/TicketsPage.tsx')
const i18n = frontend('src/i18n/index.ts')
const styles = frontend('src/styles.css')

test('the date step renders a dedicated day chip, not the plain option grid', () => {
  assert.match(tickets, /date-strip/)
  assert.match(tickets, /date-chip/)
  // The time-of-day step keeps its own simple grid -- only the date step is redesigned.
  assert.match(tickets, /ticket-options/, 'the time step still exists')
})

test('each day chip shows the weekday, the day number and the month separately', () => {
  assert.match(tickets, /formatDateParts/)
  assert.match(tickets, /date-chip-weekday/)
  assert.match(tickets, /date-chip-day/)
  assert.match(tickets, /date-chip-month/)
})

test('a fill meter shows real availability, not a decorative constant', () => {
  assert.match(tickets, /date-chip-meter/)
  // The bar's width has to come from the same available/capacity the label uses.
  assert.match(tickets, /available/)
  assert.match(tickets, /capacity/)
})

test('a full day is visibly disabled, not just unclickable', () => {
  assert.match(tickets, /date-chip[^`]*full/)
})

test('formatDateParts is exported and reuses the noon anchor that dodges DST/offset drift', () => {
  const body = i18n.match(/export const formatDateParts[\s\S]*?\n\}/)
  assert.ok(body, 'formatDateParts must be exported from i18n')
  assert.match(body[0], /T12:00:00/, 'must anchor at noon like formatDateShort, or month boundaries can shift a day')
  assert.match(body[0], /weekday/)
  assert.match(body[0], /month/)
})

test('formatDateShort keeps working for the screens that still use a single string', () => {
  // Profile.tsx's booking history reads one formatted string; it must not break.
  assert.match(i18n, /export const formatDateShort/)
  const profile = frontend('src/pages/profile/Profile.tsx')
  assert.match(profile, /formatDateShort/)
})

test('the day chip has its own visual treatment in CSS, not a reused button style', () => {
  assert.match(styles, /\.date-strip/)
  assert.match(styles, /\.date-chip/)
  assert.match(styles, /\.date-chip\.active/, 'the selected day must look selected')
  assert.match(styles, /\.date-chip-meter/)
})

test('the date strip scrolls horizontally instead of wrapping into a grid', () => {
  const rule = styles.match(/\.date-strip\{(?<body>[^}]*)\}/)
  assert.ok(rule, '.date-strip rule not found')
  assert.match(rule.groups.body, /overflow-x/)
})
