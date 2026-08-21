import { call } from './client'
import type { Hall, Movie, MovieDetail, Review } from './types'

export const getMovies = (lang = 'ru') => call<Movie[]>(`/movies?lang=${encodeURIComponent(lang)}`)

export const getMovie = (id: number, lang = 'ru') =>
  call<MovieDetail>(`/movies/${id}?lang=${encodeURIComponent(lang)}`)

export const getSessions = (id: number, date: string) =>
  call<{ sessions: string[] }>(`/movies/${id}/sessions?show_date=${encodeURIComponent(date)}`)

export const getHall = (id: number, date: string, time: string) =>
  call<Hall>(`/sessions/${id}/seats?show_date=${encodeURIComponent(date)}&session_time=${encodeURIComponent(time)}`)

export const createReview = (movieId: number, payload: Pick<Review, 'rating' | 'text'>) =>
  call<{ status: string }>(`/movies/${movieId}/reviews`, { method: 'POST', body: JSON.stringify(payload) })
