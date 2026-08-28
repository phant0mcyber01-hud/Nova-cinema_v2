import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { URL } from 'node:url'

const frontend = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const api = frontend('src/api/profile.ts')
const profile = frontend('src/pages/profile/Profile.tsx')
const ru = frontend('src/i18n/ru.ts')
const uz = frontend('src/i18n/uz.ts')
const styles = frontend('src/styles.css')

test('the profile API exposes a scoped cancellation action instead of deleting history', () => {
  assert.match(api, /cancelProfileBooking/)
  assert.match(api, /`\/profile\/bookings\/\$\{id\}\/cancel`/)
  assert.match(api, /method:\s*'PATCH'/)
  assert.doesNotMatch(api, /bookings\/\$\{id\}[^\n]*method:\s*'DELETE'/, 'the booking record must remain as cancelled history')
})

test('an active booking detail offers an explicit in-app cancellation confirmation', () => {
  assert.match(profile, /activeStatuses\.has\(booking\.status\)/)
  assert.match(profile, /cancelConfirm/)
  assert.match(profile, /cancelProfileBooking\(booking\.id\)/)
  assert.doesNotMatch(profile, /window\.confirm\(/, 'native prompts are unreliable inside Telegram WebViews')
})

test('the detail reloads after cancellation so status and QR become current', () => {
  assert.match(profile, /cancelProfileBooking\(booking\.id\)[\s\S]*getProfileBooking\(String\(booking\.id\), language\)/)
})

test('a successful PATCH is recorded before a best-effort detail refresh', () => {
  assert.match(profile, /const cancelled = await cancelProfileBooking\(booking\.id\)[\s\S]*setBooking\(current =>[\s\S]*status: cancelled\.status[\s\S]*qr_valid: false/)
  assert.match(profile, /setMessage\(t\('bookingCancelledByYou'\)\)[\s\S]*try \{[\s\S]*getProfileBooking\(String\(booking\.id\), language\)[\s\S]*catch \{/)
})

test('cancellation copy exists in both languages and has a designed card', () => {
  for (const dictionary of [ru, uz]) {
    assert.match(dictionary, /cancelBooking:/)
    assert.match(dictionary, /cancelBookingConfirm:/)
    assert.match(dictionary, /keepBooking:/)
    assert.match(dictionary, /bookingCancelledByYou:/)
  }
  assert.match(styles, /\.booking-cancel-card\s*\{/)
})
