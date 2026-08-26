/**
 * The frontend booking client must speak the API the backend actually serves.
 *
 * The two halves of the generic booking flow were written in parallel, so this
 * pins the wire contract from both sides at once: every path the client calls
 * is read out of the FastAPI router, and every field the UI renders is read out
 * of the response the router returns. A rename on either side fails here rather
 * than on a viewer's phone.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { URL } from 'node:url'

const frontend = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const backend = path => readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

const router = backend('backend/api/routers/generic_booking.py')
const client = frontend('src/api/booking.ts')
const tickets = frontend('src/pages/booking/TicketsPage.tsx')

/** `@router.get("/dates")` under `prefix="/api/booking"` -> `/booking/dates`. */
const routes = () => {
  const prefix = router.match(/APIRouter\(prefix="\/api(?<prefix>[^"]+)"/).groups.prefix
  return [...router.matchAll(/@router\.(?<verb>get|post|delete|patch)\("(?<path>[^"]*)"\)/g)]
    .map(match => `${match.groups.verb.toUpperCase()} ${prefix}${match.groups.path}`)
}

test('every path the client calls is a route the backend serves', () => {
  const served = routes()
  // `call<T>(...)` spans several lines once the generic gets long, so the path
  // is matched on its own: every request literal starts with `/booking`.
  const called = [...client.matchAll(/['"`](?<path>\/booking[\w/${}.\-?=&]*)/g)]
    .map(match => match.groups.path.replace(/\$\{[^}]*\}/g, '').replace(/\?.*$/, ''))

  assert.ok(called.length >= 4, `the client should call the whole flow, saw ${called.length}`)
  for (const path of called) {
    const method = served.find(route => route.endsWith(` ${path}`))
    assert.ok(method, `the backend serves no ${path}; it serves ${served.join(', ')}`)
  }
})

test('the client posts a request to the endpoint that files one', () => {
  assert.match(client, /'\/booking\/requests'/)
  assert.doesNotMatch(client, /call<[^>]*>\('\/bookings'/, 'POST /bookings is the legacy movie-bound route')
})

test('confirming sends the selection the backend validates the hold against', () => {
  // The backend re-reads the caller's live hold from date+time+party_size; a
  // token invented on the client would be silently ignored and the request
  // refused with 409.
  assert.doesNotMatch(client, /hold_token/, 'the backend issues no hold token')
  assert.match(client, /party_size/)
  for (const field of ['first_name', 'last_name', 'phone', 'telegram_username', 'comment']) {
    assert.match(client, new RegExp(field), `contact field ${field} is required by the API`)
  }
})

test('the slot type only promises fields the backend sends', () => {
  const slotType = client.match(/export type BookingSlot = \{(?<body>[^}]*)\}/).groups.body
  const served = router.match(/slots\.append\(\s*\{(?<body>[\s\S]*?)\}\s*\)/).groups.body
  for (const field of slotType.split(';').map(item => item.split(':')[0].trim()).filter(Boolean)) {
    assert.match(served, new RegExp(`"${field}"`), `the backend never sends slot.${field}`)
  }
})

test('the hold type only promises fields the backend sends', () => {
  const holdType = client.match(/export type BookingHold = \{(?<body>[^}]*)\}/).groups.body
  for (const field of holdType.split(';').map(item => item.split(':')[0].trim()).filter(Boolean)) {
    assert.match(router, new RegExp(`"${field}"`), `the backend never sends hold.${field}`)
  }
})

test('the dates screen reads the shape the backend returns', () => {
  // `/booking/dates` returns objects carrying how full each day is, not strings.
  assert.match(router, /"date": show_date/)
  assert.match(tickets, /\.date\b/, 'the date list is objects, so the UI must read .date')
})

test('money and capacity come from the server, never from a constant in the UI', () => {
  assert.doesNotMatch(tickets, /30[ _]?000/, 'the price is an admin setting')
  assert.doesNotMatch(tickets, /\bcurrency\s*[:=]\s*'/, 'the currency is an admin setting')
})

test('the viewer is never shown a seat, a row or a capacity token', () => {
  assert.doesNotMatch(tickets, /seatLabel|toggleSeat|row-|\brows\b/i)
  assert.match(tickets, /aria-hidden/, 'the 3x4 grid is decoration, not a control')
})

test('the administrator contacts come from the admin panel, not the bundle', () => {
  const contacts = frontend('src/components/AdminContacts.tsx')
  const hook = frontend('src/lib/useAdminContacts.ts')
  const success = frontend('src/pages/booking/Success.tsx')
  // A number baked into the build cannot be changed without a redeploy.
  for (const [name, source] of [['tickets', tickets], ['success', success], ['component', contacts]]) {
    assert.doesNotMatch(source, /\d{2}\s?\d{3}\s?\d{2}\s?\d{2}/, `${name} hardcodes a phone number`)
    assert.doesNotMatch(source, /@Hhkcjoj/i, `${name} hardcodes a Telegram handle`)
  }
  assert.match(hook, /admin_phone/)
  assert.match(hook, /admin_telegram/)
  // Tappable, not plain text: this is the number a viewer has to call.
  assert.match(contacts, /href=\{`tel:/)
  assert.match(contacts, /t\.me\//)
})
