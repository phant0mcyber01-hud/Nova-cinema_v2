import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { URL } from 'node:url'

const frontend = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const profileApi = frontend('src/api/profile.ts')
const adminApi = frontend('src/api/admin.ts')
const profile = frontend('src/pages/profile/Profile.tsx')
const admin = frontend('src/pages/admin/Admin.tsx')
const ru = frontend('src/i18n/ru.ts')
const uz = frontend('src/i18n/uz.ts')
const css = frontend('src/styles.css')

test('API exposes scoped clear actions for history and both notification inboxes', () => {
  assert.match(profileApi, /clearProfileBookingHistory[\s\S]*\/profile\/history\/bookings[\s\S]*method: 'DELETE'/)
  assert.match(profileApi, /clearProfileNotifications[\s\S]*\/profile\/notifications[\s\S]*method: 'DELETE'/)
  assert.match(adminApi, /clearAdminNotifications[\s\S]*\/admin\/notifications[\s\S]*method: 'DELETE'/)
})

test('client UI clears terminal history without touching active tickets', () => {
  assert.match(profile, /clearProfileBookingHistory\(\)/)
  assert.match(profile, /setList\(current => current\.filter\(item => activeStatuses\.has\(item\.status\)\)\)/)
  assert.match(profile, /clearHistoryConfirm/)
})

test('client and admin notification UIs have designed confirmation controls', () => {
  assert.match(profile, /clearProfileNotifications\(\)/)
  assert.match(admin, /clearAdminNotifications\(\)/)
  assert.doesNotMatch(profile, /window\.confirm\(/)
  assert.doesNotMatch(admin.replace(/\/\*[\s\S]*?\*\//g, ''), /window\.confirm\(/)
  assert.match(css, /\.cleanup-card\s*\{/)
})

test('cleanup wording exists in Russian and Uzbek', () => {
  for (const dictionary of [ru, uz]) {
    assert.match(dictionary, /clearHistory:/)
    assert.match(dictionary, /clearNotifications:/)
    assert.match(dictionary, /clearAllConfirm:/)
    assert.match(dictionary, /cleanupRetentionHint:/)
  }
})
