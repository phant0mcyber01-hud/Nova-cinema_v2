import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { URL } from 'node:url'

const source = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('tickets are the only generic booking entry and hold by selection', () => {
  const app = source('src/App.tsx')
  const nav = source('src/components/BottomNav.tsx')
  const api = source('src/api/booking.ts')
  const card = source('src/components/MovieCard.tsx')
  const movie = source('src/pages/MoviePage.tsx')

  assert.match(app, /path="\/tickets"/)
  assert.doesNotMatch(app, /\/booking\/:id/)
  assert.match(nav, /to: '\/tickets'/)
  assert.doesNotMatch(card, /bookTicket|\/booking\//)
  assert.doesNotMatch(movie, /bookTicket|schedule-block|availableSessions/)
  assert.match(api, /party_size/)
  assert.doesNotMatch(api, /movie_id|seats/)
})

test('music runtime, UI, API and tests are absent', () => {
  const app = source('src/App.tsx')
  const admin = source('src/api/admin.ts')
  assert.doesNotMatch(app, /AudioProvider|audioPlayer|melody/i)
  assert.doesNotMatch(admin, /melod|audio/i)
})

test('generic flow renders a non-interactive 3 by 4 availability grid', () => {
  const tickets = source('src/pages/booking/TicketsPage.tsx')
  assert.match(tickets, /party_size/)
  assert.match(tickets, /Array\.from\(\{ length: 12 \}/)
  assert.doesNotMatch(tickets, /seatLabel|toggleSeat|aria-label=.*seat/i)
})
