import { call } from './client'
import type { Movie, MovieDetail, Review } from './types'

export type CatalogFilters = {
  /** Only movies actually screening that day. */
  date?: string
  /** Free text over title, genre, description, country, director, cast and year. */
  q?: string
  onlyNew?: boolean
}

export const getMovies = (lang = 'ru', filters: CatalogFilters = {}) => {
  const query = new URLSearchParams({ lang })
  if (filters.date) query.set('date', filters.date)
  if (filters.q?.trim()) query.set('q', filters.q.trim())
  if (filters.onlyNew) query.set('only_new', 'true')
  return call<Movie[]>(`/movies?${query.toString()}`)
}

export const getMovie = (id: number, lang = 'ru') =>
  call<MovieDetail>(`/movies/${id}?lang=${encodeURIComponent(lang)}`)

export const createReview = (movieId: number, payload: Pick<Review, 'rating' | 'text'>) =>
  call<{ status: string }>(`/movies/${movieId}/reviews`, { method: 'POST', body: JSON.stringify(payload) })
