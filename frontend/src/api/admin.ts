import { call } from './client'
import { invalidateMelodies } from './settings'
import { audioChunkRanges, createAudioUploadId } from '../lib/audioUpload'
import type {
  AdminBonus,
  AdminBonusPayload,
  AdminGalleryImage,
  AdminGalleryImagePayload,
  AdminBooking,
  AdminMelody,
  AdminNotification,
  AdminReview,
  AdminSession,
  AdminSessionPayload,
  AdminSettings,
  AdminSettingsPayload,
  MovieDetail,
  MoviePayload,
} from './types'

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
  payload: { action: 'contact' | 'confirm' | 'decline' | 'propose'; reason?: string; proposed_session?: string },
) =>
  call<{ status: string; proposed_session: string; admin_note: string }>(`/admin/bookings/${id}/decision`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })

export const getNotifications = () => call<AdminNotification[]>('/admin/notifications')

export const readNotification = (id: number) =>
  call<{ is_read: boolean }>(`/admin/notifications/${id}/read`, { method: 'PATCH' })

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

export const createAdminSession = (payload: AdminSessionPayload) =>
  call<{ id: number }>('/admin/sessions', { method: 'POST', body: JSON.stringify(payload) })

export const updateAdminSession = (id: number, payload: AdminSessionPayload) =>
  call<{ status: string }>(`/admin/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })

export const deleteAdminSession = (id: number) =>
  call<{ status: string }>(`/admin/sessions/${id}`, { method: 'DELETE' })

export const uploadAdminImage = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return call<{ url: string }>('/admin/uploads', { method: 'POST', body: form })
}

// --- cinema settings ---------------------------------------------------------

export const getAdminSettings = () => call<AdminSettings>('/admin/settings')

export const updateAdminSettings = (payload: AdminSettingsPayload) =>
  call<AdminSettings>('/admin/settings', { method: 'PUT', body: JSON.stringify(payload) })

// --- schedule ----------------------------------------------------------------

export const createAdminSessionsBulk = (payload: {
  movie_id: number
  date_from: string
  date_to: string
  times: string[]
  ticket_price: number | null
}) => call<{ created: number }>('/admin/sessions/bulk', { method: 'POST', body: JSON.stringify(payload) })

// --- bonuses -----------------------------------------------------------------

export const getAdminBonuses = () => call<AdminBonus[]>('/admin/bonuses')

export const createAdminBonus = (payload: AdminBonusPayload) =>
  call<{ id: number }>('/admin/bonuses', { method: 'POST', body: JSON.stringify(payload) })

export const updateAdminBonus = (id: number, payload: AdminBonusPayload) =>
  call<{ status: string }>(`/admin/bonuses/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })

export const deleteAdminBonus = (id: number) =>
  call<{ status: string }>(`/admin/bonuses/${id}`, { method: 'DELETE' })

// --- melodies ----------------------------------------------------------------

export const getAdminMelodies = () => call<AdminMelody[]>('/admin/melodies')

const melodyMutation = async <T>(request: Promise<T>): Promise<T> => {
  const result = await request
  invalidateMelodies()
  return result
}

export const createAdminMelody = (payload: { title: string; file_url: string; sort_order: number }) =>
  melodyMutation(call<{ id: number }>('/admin/melodies', { method: 'POST', body: JSON.stringify(payload) }))

export const updateAdminMelody = (id: number, payload: { title?: string; file_url?: string; sort_order?: number }) =>
  melodyMutation(call<{ status: string }>(`/admin/melodies/${id}`, {
    method: 'PATCH', body: JSON.stringify(payload),
  }))

export const deleteAdminMelody = (id: number) =>
  melodyMutation(call<{ status: string }>(`/admin/melodies/${id}`, { method: 'DELETE' }))

export const uploadMelodyFile = async (file: File, onProgress?: (percent: number) => void) => {
  const ranges = audioChunkRanges(file.size)
  const uploadId = createAudioUploadId()
  let finalUrl = ''

  for (const [index, range] of ranges.entries()) {
    const form = new FormData()
    form.append('upload_id', uploadId)
    form.append('chunk_index', String(index))
    form.append('total_chunks', String(ranges.length))
    form.append('total_size', String(file.size))
    form.append('filename', file.name)
    form.append('file', file.slice(range.start, range.end), `chunk-${index}.bin`)
    const result = await call<{ complete: boolean; url?: string }>('/admin/melodies/upload/chunk', {
      method: 'POST', body: form,
    })
    if (result.complete) finalUrl = result.url ?? ''
    onProgress?.(Math.round(((index + 1) / ranges.length) * 100))
  }

  if (!finalUrl) throw new Error('Audio upload did not complete')
  return { url: finalUrl }
}

// --- review moderation -------------------------------------------------------

export const getAdminReviews = () => call<AdminReview[]>('/admin/reviews')

export const moderateReview = (id: number, approved: boolean) =>
  call<{ id: number; approved: boolean }>(`/admin/reviews/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ approved }),
  })

export const deleteAdminReview = (id: number) =>
  call<{ status: string }>(`/admin/reviews/${id}`, { method: 'DELETE' })

// --- cinema gallery ----------------------------------------------------------

export const getAdminGallery = () => call<AdminGalleryImage[]>('/admin/gallery')

export const createAdminImage = (payload: AdminGalleryImagePayload) =>
  call<{ id: number }>('/admin/gallery', { method: 'POST', body: JSON.stringify(payload) })

export const updateAdminImage = (id: number, payload: AdminGalleryImagePayload) =>
  call<{ status: string }>(`/admin/gallery/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })

export const deleteAdminImage = (id: number) =>
  call<{ status: string }>(`/admin/gallery/${id}`, { method: 'DELETE' })
