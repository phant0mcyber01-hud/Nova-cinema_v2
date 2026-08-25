/**
 * The admin panel must drive the generic inventory, not the legacy one.
 *
 * The times the booking flow reads live in `slot_templates` and are served by
 * `/admin/slots`. The old `/admin/sessions` endpoints schedule a *film* and
 * reject any payload without a `movie_id`, so an admin screen pointed at them
 * cannot save anything at all. These assertions pin which contract the panel
 * speaks, and that the dashboard only shows numbers that mean something.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { URL } from 'node:url'

const frontend = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const backend = path => readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

const adminApi = frontend('src/api/admin.ts')
const sessionsView = frontend('src/pages/admin/AdminSessions.tsx')
const adminPanel = frontend('src/pages/admin/Admin.tsx')
const adminRoutes = backend('backend/api/routers/admin_catalog.py')
const dashboard = backend('backend/api/routers/admin.py')

test('the schedule screen manages fixed times, not screenings of a film', () => {
  assert.match(adminApi, /'\/admin\/slots'/, 'the generic times are served by /admin/slots')
  assert.doesNotMatch(
    sessionsView,
    /createAdminSession\b|updateAdminSession\b|deleteAdminSession\b/,
    '/admin/sessions requires a movie_id and rejects a generic time',
  )
  assert.doesNotMatch(sessionsView, /movie/i, 'a time belongs to the hall, not to a film')
})

test('the slot payload matches the schema the backend validates', () => {
  const schema = backend('backend/schemas/booking.py')
    .match(/class SlotTemplateIn\(BaseModel\):(?<body>[\s\S]*?)\r?\n\r?\n\r?\nclass /).groups.body
  const fields = [...schema.matchAll(/^\s{4}(?<name>\w+):/gm)].map(match => match.groups.name)
  const slotType = frontend('src/api/types.ts')
    .match(/export type AdminSlot = \{(?<body>[^}]*)\}/).groups.body

  assert.ok(fields.includes('start_time') && fields.includes('is_active'), fields.join(','))
  for (const field of fields) {
    assert.match(slotType, new RegExp(`\\b${field}\\b`), `the client models no slot.${field}`)
  }
  // A price per slot is not part of the agreed model: the total is the base
  // ticket price times the number of people.
  assert.doesNotMatch(sessionsView, /ticket_price/, 'the slot carries no price of its own')
})

test('every generic slot route the backend serves has a client function', () => {
  const served = [...adminRoutes.matchAll(/@router\.(?<verb>get|post|patch|delete)\("(?<path>\/slots[^"]*)"\)/g)]
  assert.equal(served.length, 4, 'list, create, edit and delete')
  for (const { groups } of served) {
    const path = groups.path.replace(/\{[^}]*\}/, '')
    assert.ok(
      adminApi.includes(`/admin${path}`),
      `no client call for ${groups.verb.toUpperCase()} /admin${groups.path}`,
    )
  }
})

test('the dashboard shows no counter the generic flow leaves permanently at zero', () => {
  // `active_sessions` counts rows in the legacy movie-bound `shows` table, which
  // the mini app no longer writes to.
  assert.doesNotMatch(dashboard, /"active_sessions"/, 'a metric that is always 0 is misinformation')
  assert.doesNotMatch(adminPanel, /active_sessions/)
  assert.doesNotMatch(adminPanel, /potential_income|potentialIncome/, 'nothing is paid inside the app')
})

test('the mini app no longer renders a per-request bookings screen at all', () => {
  // Every request is now worked entirely through the bot's own DM buttons
  // (backend/services/bot_actions.py); a second, weaker copy of the same
  // workflow inside the Mini App would just give the administrator two
  // places that can silently disagree.
  assert.doesNotMatch(adminPanel, /item\.seats\b/, 'a generic request holds places, not chairs')
  assert.doesNotMatch(adminPanel, /getAdminBookings|decideBooking|setBookingStatus/)
})
