/**
 * The FAQ editor manages a real list, not just index [0].
 *
 * The old markup wired every input to `draft.faq[0]`, so a second question
 * silently overwrote the first the moment anybody typed in it -- the admin
 * could never actually save more than one FAQ entry through the form.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { URL } from 'node:url'

const frontend = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const view = frontend('src/pages/admin/AdminCinemaSettings.tsx')

test('the editor can add another FAQ entry', () => {
  assert.match(view, /addFaqItem|faq\.push|setFaq\(.*\[\.\.\..*,/s, 'no way to append a new question found')
})

test('the editor can remove one FAQ entry by its own index', () => {
  assert.match(view, /removeFaqItem|faq\.filter\(/, 'no way to remove a single question found')
})

test('every FAQ input is keyed to its own index, not hardcoded to [0]', () => {
  // The old bug: every handler read/wrote draft.faq[0] no matter which
  // question was being edited.
  assert.doesNotMatch(view, /draft\.faq\[0\]/, 'still hardcoded to the first FAQ item')
})

test('the FAQ section renders one block per question, mapped over the list', () => {
  assert.match(view, /draft\.faq\.map\(/)
})
