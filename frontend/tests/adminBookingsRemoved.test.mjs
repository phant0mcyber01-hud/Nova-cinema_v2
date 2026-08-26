/**
 * The bookings tab is gone from the Mini App's own admin panel.
 *
 * Every request now moves through the bot's own DM (contact/confirm/propose/
 * decline buttons on the notification, see test_admin_bot_actions.py on the
 * backend side). Keeping a second, weaker copy of the same workflow inside
 * the Mini App -- window.prompt() for a time, window.confirm() for a status
 * change -- just gives the administrator two places that can disagree.
 *
 * The dashboard tile counting pending requests stays: it is a read-only
 * number, not a place to act on one.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { URL } from 'node:url'

const frontend = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const admin = frontend('src/pages/admin/Admin.tsx')
const api = frontend('src/api/admin.ts')
const ru = frontend('src/i18n/ru.ts')

test('the admin panel has no bookings tab', () => {
  assert.doesNotMatch(admin, /id: 'bookings'/)
  assert.doesNotMatch(admin, /adminBookingsTab/)
  assert.doesNotMatch(admin, /BookingsView/)
})

test('the panel no longer calls the per-request decision endpoints', () => {
  // The bot's DM is now the only place a request is acted on; the panel must
  // not offer a second, silently-diverging copy of the same buttons.
  assert.doesNotMatch(admin, /decideBooking|setBookingStatus/)
})

test('getAdminBookings and the decision calls are gone from the admin API client', () => {
  assert.doesNotMatch(api, /getAdminBookings|decideBooking|setBookingStatus/)
})

test('the dashboard still shows request counts -- a read-only number, not a workflow', () => {
  assert.match(admin, /statuses\.pending/)
})

test('house style: no leftover Russian bookings-tab strings', () => {
  assert.doesNotMatch(ru, /^\s*adminBookingsTab:/m)
})
