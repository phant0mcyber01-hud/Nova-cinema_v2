import { call } from './client'
import type { Movie, Profile, ProfileBooking, ProfileNotification } from './types'

export const getProfile = () => call<Profile>('/profile')

export const updateProfile = (payload: Pick<Profile, 'first_name' | 'last_name' | 'phone'>) =>
  call<{ status: string }>('/profile', { method: 'PATCH', body: JSON.stringify(payload) })

export const getProfileBookings = (lang = 'ru') =>
  call<ProfileBooking[]>(`/profile/bookings?lang=${encodeURIComponent(lang)}`)

export const clearProfileBookingHistory = () =>
  call<{ cleared: number }>('/profile/history/bookings', { method: 'DELETE' })

export const getProfileBooking = (id: string, lang = 'ru') =>
  call<ProfileBooking>(`/profile/bookings/${id}?lang=${encodeURIComponent(lang)}`)

export const cancelProfileBooking = (id: number) =>
  call<{ status: string }>(`/profile/bookings/${id}/cancel`, { method: 'PATCH' })

export const answerBookingProposal = (id: number, action: 'accept' | 'decline') =>
  call<{ status: string; session: string }>(`/profile/bookings/${id}/proposal`, {
    method: 'PATCH',
    body: JSON.stringify({ action }),
  })

export const getFavorites = (lang = 'ru') => call<Movie[]>(`/profile/favorites?lang=${encodeURIComponent(lang)}`)

export const addFavorite = (id: number) => call<{ status: string }>(`/profile/favorites/${id}`, { method: 'POST' })

export const removeFavorite = (id: number) =>
  call<{ status: string }>(`/profile/favorites/${id}`, { method: 'DELETE' })

export const getProfileNotifications = () => call<ProfileNotification[]>('/profile/notifications')

export const clearProfileNotifications = () =>
  call<{ cleared: number }>('/profile/notifications', { method: 'DELETE' })

export const readProfileNotification = (id: number) =>
  call<{ is_read: boolean }>(`/profile/notifications/${id}/read`, { method: 'PATCH' })
