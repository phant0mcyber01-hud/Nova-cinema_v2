import { call } from './client'
import type { AdminBooking, AdminNotification, AdminSession, MovieDetail, MoviePayload } from './types'

export const getDashboard = () =>
  call<{
    movies: number
    active_sessions: number
    bookings: number
    potential_income: number
    statuses: Record<string, number>
    recent_bookings: Pick<AdminBooking, 'id' | 'name' | 'phone' | 'status' | 'total'>[]
    notifications: AdminNotification[]
  }>('/admin/dashboard')

export const getAdminBookings = () => call<AdminBooking[]>('/admin/bookings')

export const setBookingStatus = (id: number, status: string) =>
  call<{ status: string }>(`/admin/bookings/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })

export const decideBooking = (
  id: number,
  payload: { action: 'confirm' | 'decline' | 'propose'; reason?: string; proposed_session?: string },
) =>
  call<{ status: string; proposed_session: string; admin_note: string }>(`/admin/bookings/${id}/decision`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })

export const getNotifications = () => call<AdminNotification[]>('/admin/notifications')

export const readNotification = (id: number) =>
  call<{ is_read: boolean }>(`/admin/notifications/${id}/read`, { method: 'PATCH' })

export const getBasePrice = () => call<{ base_ticket_price: number }>('/admin/settings/base-price')

export const setBasePrice = (base_ticket_price: number) =>
  call<{ base_ticket_price: number }>('/admin/settings/base-price', {
    method: 'PATCH',
    body: JSON.stringify({ base_ticket_price }),
  })

export const getAdminMovies = (lang = 'ru') =>
  call<MovieDetail[]>(`/admin/movies?lang=${encodeURIComponent(lang)}`)

export const lookupAdminMovie = (title: string) =>
  call<MoviePayload>('/admin/movies/lookup', { method: 'POST', body: JSON.stringify({ title }) })

export const createAdminMovie = (payload: MoviePayload) =>
  call<{ id: number; translation_warning?: boolean }>('/admin/movies', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const updateAdminMovie = (id: number, payload: MoviePayload) =>
  call<{ status: string; translation_warning?: boolean }>(`/admin/movies/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })

export const deleteAdminMovie = (id: number) => call<{ status: string }>(`/admin/movies/${id}`, { method: 'DELETE' })

export const getAdminSessions = () => call<AdminSession[]>('/admin/sessions')

export const createAdminSession = (payload: Omit<AdminSession, 'id' | 'movie' | 'resolved_price'>) =>
  call<{ id: number }>('/admin/sessions', { method: 'POST', body: JSON.stringify(payload) })

export const updateAdminSession = (id: number, payload: Omit<AdminSession, 'id' | 'movie' | 'resolved_price'>) =>
  call<{ status: string }>(`/admin/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })

export const deleteAdminSession = (id: number) =>
  call<{ status: string }>(`/admin/sessions/${id}`, { method: 'DELETE' })

export const uploadAdminImage = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return call<{ url: string }>('/admin/uploads', { method: 'POST', body: form })
}
