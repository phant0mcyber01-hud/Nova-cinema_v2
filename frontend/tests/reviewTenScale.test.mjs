/**
 * Reviews use a 1-10 scale everywhere the client can see or set a rating --
 * not the 1-5 stars the movie page used to render.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { URL } from 'node:url'

const frontend = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const moviePage = frontend('src/pages/MoviePage.tsx')
const adminReviews = frontend('src/pages/admin/AdminReviews.tsx')
const styles = frontend('src/styles.css')

test('the review form offers 1 through 10, not 1 through 5', () => {
  assert.match(moviePage, /\[10, ?9, ?8, ?7, ?6, ?5, ?4, ?3, ?2, ?1\]|Array\.from\(\{ ?length: ?10/)
  assert.doesNotMatch(moviePage, /\[5, ?4, ?3, ?2, ?1\]/, 'still offering the old 1-5 range')
})

test('a posted review is displayed out of 10, not out of 5', () => {
  assert.match(moviePage, /\/10/)
  assert.doesNotMatch(moviePage, /review\.rating\}\/5/, 'still labelling a rating out of 5')
})

test('the admin moderation list also reads the rating out of 10', () => {
  assert.match(adminReviews, /\/10/)
  assert.doesNotMatch(adminReviews, /review\.rating\}\/5/)
})

test('the viewer picks a rating with ten small SVG stars in one row, not digit buttons', () => {
  const scale = moviePage.match(/<div className="review-rating-scale"(?<body>[\s\S]*?)<\/div>/)?.groups?.body ?? ''
  assert.match(scale, /<Icon name="star"/i, 'the rating buttons must render the shared SVG star')
  assert.doesNotMatch(scale, />\s*\{value\}\s*<\/button>/, 'the old numeric button labels must be gone')
  assert.match(scale, /value <= reviewRating/, 'all stars up to the chosen score should be filled')
  const css = styles.match(/\.review-rating-scale\s*\{(?<body>[^}]*)\}/)?.groups?.body ?? ''
  assert.match(css, /grid-template-columns:\s*repeat\(10,minmax\(0,1fr\)\)/, 'all ten stars must stay in one compact row')
  assert.doesNotMatch(css, /flex-wrap:wrap/, 'the scale must not wrap into a second row')
})
