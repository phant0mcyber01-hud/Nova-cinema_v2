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
const admin = frontend('src/pages/admin/Admin.tsx')
const styles = frontend('src/styles.css')

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

test('background refresh updates only the dashboard and cannot reset a form being edited', () => {
  assert.match(admin, /refreshDashboard/, 'there must be a lightweight refresh that does not reload settings')
  assert.match(admin, /setInterval\([\s\S]*refreshDashboard/, 'the timer must use the lightweight refresh')
  assert.doesNotMatch(admin, /setInterval\(\(\) => \{ void load\(\) \}/, 'polling every admin resource resets unsaved form fields')
})

test('FAQ and important text open in their own large editor dialog', () => {
  assert.match(view, /faq-editor-modal/)
  assert.match(view, /role="dialog"/)
  assert.match(view, /setFaqOpen\(true\)/)
  assert.match(view, /function FaqEditorModal/, 'typing should rerender only the editor, not the entire cinema settings page')
})

test('the FAQ editor uses the mini-app gradients and gives long text real room', () => {
  const modal = styles.match(/\.faq-editor-modal\s*\{(?<body>[^}]*)\}/)?.groups?.body ?? ''
  assert.match(modal, /width:min\(100%,9\d{2}px\)/, 'the editor should be wider than the existing 820px CMS dialog')
  assert.match(modal, /radial-gradient|linear-gradient/, 'the dialog should use the mini-app gradient language')
  assert.match(styles, /\.faq-editor-modal[^{]*textarea\s*\{[^}]*min-height:1[2-9]\dpx/, 'important/FAQ textareas need a comfortable editing height')
})

test('the FAQ dialog stays above the fixed bottom navigation', () => {
  const backdrop = styles.match(/\.faq-editor-backdrop\s*\{(?<body>[^}]*)\}/)?.groups?.body ?? ''
  assert.match(backdrop, /z-index:(?:[3-9]\d|\d{3,})/, 'the bottom navigation must not cover editor fields or actions')
})

test('the FAQ modal explicitly disables inherited backdrop blur', () => {
  const modal = styles.match(/\.faq-editor-modal\s*\{(?<body>[^}]*)\}/)?.groups?.body ?? ''
  assert.match(modal, /(?:^|;)backdrop-filter:none(?:;|$)/, 'the modal itself must override the global blur')
})

test('the FAQ header close control is disabled while a save is in flight', () => {
  const header = view.match(/<header className="faq-editor-head">(?<body>[\s\S]*?)<\/header>/)?.groups?.body ?? ''
  assert.match(header, /<button[^>]*className="admin-ghost cms-close"[^>]*disabled=\{busy\}[^>]*>/, 'the header close button must be disabled by busy')
})

test('the FAQ editable body disables all descendant controls while saving', () => {
  assert.match(view, /<fieldset className="faq-editor-body" disabled=\{busy\}>/, 'a disabled fieldset must lock inputs, textareas, and add/remove buttons')
  assert.doesNotMatch(view, /<div className="faq-editor-body">/, 'the editable body must not remain an enabled div')
})

test('the desktop FAQ dialog declares a legacy vh fallback before dvh', () => {
  const modal = styles.match(/\.faq-editor-modal\s*\{(?<body>[^}]*)\}/)?.groups?.body ?? ''
  assert.match(
    modal,
    /height:94vh;max-height:940px;height:min\(94dvh,940px\);max-height:94dvh(?:;|$)/,
    'legacy WebViews need usable vh/px sizing before dynamic viewport declarations',
  )
})

test('the mobile FAQ dialog declares 100vh fallbacks before 100dvh', () => {
  const modalRules = [...styles.matchAll(/\.faq-editor-modal\s*\{(?<body>[^}]*)\}/g)]
  const mobile = modalRules.at(-1)?.groups?.body ?? ''
  assert.match(
    mobile,
    /height:100vh;max-height:100vh;height:100dvh;max-height:100dvh(?:;|$)/,
    'legacy mobile WebViews need full-screen vh declarations before dvh',
  )
})
