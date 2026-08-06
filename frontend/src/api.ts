import { translate } from './i18n'

export type Movie = {
  id: number
  title: string
  genre: string
  duration: number
  age: number
  imdb: number
  kinopoisk: number
  rating: number
  poster: string
  description: string
  sessions: string[]
  internal_rating: number | null
  ticket_price: number | null
  is_published: boolean
  sort_order: number
}

export type MovieDetail = Movie & {
  country: string
  year: number
  director: string
  cast: string[]
  trailer_id: string
  gallery: string[]
  user_rating: number | null
  similar_movies: Movie[]
  reviews: Review[]
}

export type MoviePayload = {
  title: string
  genre: string
  description: string
  poster: string
  trailer_id: string
  duration: number
  age: number
  year: number
  country: string
  director: string
  cast: string[]
  gallery: string[]
  imdb: number
  kinopoisk: number
  internal_rating: number | null
  ticket_price: number | null
  is_published: boolean
  sort_order: number
}

export type Review = { user_name: string; rating: number; text: string; created_at: string }
export type Hall = { rows: number; cols: number; seats_count: number; price: number; taken: string[] }
export type AdminBooking = {
  id: number
  status: string
  phone: string
  name: string
  comment: string
  total: number
  seats: string
  session: string
  show_date: string
  movie_id: number
  movie: string
  poster: string
  telegram_username: string
  chat_url: string | null
  proposed_session: string
  admin_note: string
}
export type AdminSession = {
  id: number
  movie_id: number
  movie: string
  show_date: string
  session: string
  ticket_price: number | null
  resolved_price: number
  seats_count: number
  status: string
}
export type AdminNotification = { id: number; booking_id: number; message: string; is_read: boolean; created_at: string }

const authStorageKey = 'nova-cinema-auth-v1'

type StoredAuth = {
  accessToken: string
  role: string
}

const readStoredAuth = (): StoredAuth | null => {
  try {
    const value = window.localStorage.getItem(authStorageKey) ?? window.sessionStorage.getItem(authStorageKey)
    if (!value) return null
    const parsed = JSON.parse(value) as Partial<StoredAuth>
    if (typeof parsed.accessToken !== 'string' || !parsed.accessToken) return null
    return { accessToken: parsed.accessToken, role: typeof parsed.role === 'string' ? parsed.role : '' }
  } catch {
    return null
  }
}

let accessToken: string | null = null
let role = ''
let authReady = true
let authPromise: Promise<void> = Promise.resolve()

const applyAuth = (data: StoredAuth) => {
  accessToken = data.accessToken
  role = data.role
}

const saveAuth = (data: StoredAuth) => {
  applyAuth(data)
  try {
    window.localStorage.setItem(authStorageKey, JSON.stringify(data))
    window.sessionStorage.setItem(authStorageKey, JSON.stringify(data))
  } catch {
    window.sessionStorage.setItem(authStorageKey, JSON.stringify(data))
  }
}

const clearAuth = () => {
  accessToken = null
  role = ''
  try {
    window.localStorage.removeItem(authStorageKey)
    window.sessionStorage.removeItem(authStorageKey)
  } catch {
    window.sessionStorage.removeItem(authStorageKey)
  }
}

const storedAuth = readStoredAuth()
if (storedAuth) applyAuth(storedAuth)

export type AuthState = {
  ready: boolean
  authenticated: boolean
  role: string
  isAdmin: boolean
}

const call = async <T>(path: string, options: RequestInit = {}): Promise<T> => {
  const isFormData = options.body instanceof FormData
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
      ...(accessToken && path !== '/auth/telegram' ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...options.headers,
    },
  })
  const text = await response.text()
  let data: unknown = {}
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = { detail: text }
    }
  }
  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/telegram') clearAuth()
    const detail = typeof data === 'object' && data !== null && 'detail' in data ? String(data.detail) : translate('serverError')
    throw new Error(detail)
  }
  return data as T
}

export async function authenticateTelegram(initData: string): Promise<void> {
  authReady = false
  authPromise = (async () => {
    const cached = readStoredAuth()
    if (cached) applyAuth(cached)
    if (!initData) {
      return
    }
    clearAuth()
    const data = await call<{ access_token: string; user: { role: string } }>('/auth/telegram', { method: 'POST', body: JSON.stringify({ init_data: initData }) })
    saveAuth({ accessToken: data.access_token, role: data.user.role })
  })().finally(() => {
    authReady = true
  })
  return authPromise
}

export const isAdmin = () => role === 'admin'
export const getAuthState = (): AuthState => ({ ready: authReady, authenticated: Boolean(accessToken), role, isAdmin: role === 'admin' })
export const waitForAuth = () => authPromise
export const getMovies = (lang = 'ru') => call<Movie[]>(`/movies?lang=${encodeURIComponent(lang)}`)
export const getMovie = (id: number, lang = 'ru') => call<MovieDetail>(`/movies/${id}?lang=${encodeURIComponent(lang)}`)
export const getSessions = (id: number, date: string) => call<{ sessions: string[] }>(`/movies/${id}/sessions?show_date=${date}`)
export const getHall = (id: number, date: string, time: string) => call<Hall>(`/sessions/${id}/seats?show_date=${date}&session_time=${encodeURIComponent(time)}`)
export const holdSeats = (payload: { movie_id: number; show_date: string; session: string; seats: string[] }) => call<{ total: number }>('/holds', { method: 'POST', body: JSON.stringify(payload) })
export type BookingPayload = { movie_id: number; show_date: string; session: string; seats: string[]; first_name: string; last_name: string; phone: string; telegram_username: string; comment: string }
export const confirmBooking = (payload: BookingPayload) => call<{ ticket_code: string; total: number; message: string }>('/bookings/confirm', { method: 'POST', body: JSON.stringify(payload) })
export const createReview = (movieId: number, payload: Pick<Review, 'rating' | 'text'>) => call<{ status: string }>(`/movies/${movieId}/reviews`, { method: 'POST', body: JSON.stringify(payload) })

export const getDashboard = () => call<{ movies: number; active_sessions: number; bookings: number; potential_income: number; statuses: Record<string, number>; recent_bookings: Pick<AdminBooking, 'id' | 'name' | 'phone' | 'status' | 'total'>[]; notifications: AdminNotification[] }>('/admin/dashboard')
export const getAdminBookings = () => call<AdminBooking[]>('/admin/bookings')
export const setBookingStatus = (id: number, status: string) => call<{ status: string }>(`/admin/bookings/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })
export const decideBooking = (id: number, payload: { action: 'confirm' | 'decline' | 'propose'; reason?: string; proposed_session?: string }) => call<{ status: string; proposed_session: string; admin_note: string }>(`/admin/bookings/${id}/decision`, { method: 'PATCH', body: JSON.stringify(payload) })
export const getNotifications = () => call<AdminNotification[]>('/admin/notifications')
export const readNotification = (id: number) => call<{ is_read: boolean }>(`/admin/notifications/${id}/read`, { method: 'PATCH' })
export const getBasePrice = () => call<{ base_ticket_price: number }>('/admin/settings/base-price')
export const setBasePrice = (base_ticket_price: number) => call<{ base_ticket_price: number }>('/admin/settings/base-price', { method: 'PATCH', body: JSON.stringify({ base_ticket_price }) })
export const getAdminMovies = (lang = 'ru') => call<MovieDetail[]>(`/admin/movies?lang=${encodeURIComponent(lang)}`)
export const lookupAdminMovie = (title: string) => call<MoviePayload>('/admin/movies/lookup', { method: 'POST', body: JSON.stringify({ title }) })
export const createAdminMovie = (payload: MoviePayload) => call<{ id: number; translation_warning?: boolean }>('/admin/movies', { method: 'POST', body: JSON.stringify(payload) })
export const updateAdminMovie = (id: number, payload: MoviePayload) => call<{ status: string; translation_warning?: boolean }>(`/admin/movies/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
export const deleteAdminMovie = (id: number) => call<{ status: string }>(`/admin/movies/${id}`, { method: 'DELETE' })
export const getAdminSessions = () => call<AdminSession[]>('/admin/sessions')
export const createAdminSession = (payload: Omit<AdminSession, 'id' | 'movie' | 'resolved_price'>) => call<{ id: number }>('/admin/sessions', { method: 'POST', body: JSON.stringify(payload) })
export const updateAdminSession = (id: number, payload: Omit<AdminSession, 'id' | 'movie' | 'resolved_price'>) => call<{ status: string }>(`/admin/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
export const deleteAdminSession = (id: number) => call<{ status: string }>(`/admin/sessions/${id}`, { method: 'DELETE' })
export const uploadAdminImage = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return call<{ url: string }>('/admin/uploads', { method: 'POST', body: form })
}

export type Profile = { first_name: string; last_name: string; phone: string; telegram_id: number; created_at: string; bookings: number }
export type ProfileBooking = { id: number; uuid: string; qr_token: string; qr_valid: boolean; movie: string; poster: string; description: string; trailer_id: string; show_date: string; session: string; seats: string; total: number; status: string; phone: string; telegram_username: string; comment: string; proposed_session: string; admin_note: string }
export const getProfile = () => call<Profile>('/profile')
export const updateProfile = (payload: Pick<Profile, 'first_name' | 'last_name' | 'phone'>) => call<{ status: string }>('/profile', { method: 'PATCH', body: JSON.stringify(payload) })
export const getProfileBookings = (lang = 'ru') => call<ProfileBooking[]>(`/profile/bookings?lang=${encodeURIComponent(lang)}`)
export const getProfileBooking = (id: string, lang = 'ru') => call<ProfileBooking>(`/profile/bookings/${id}?lang=${encodeURIComponent(lang)}`)
export const answerBookingProposal = (id: number, action: 'accept' | 'decline') => call<{ status: string; session: string }>(`/profile/bookings/${id}/proposal`, { method: 'PATCH', body: JSON.stringify({ action }) })
export const getFavorites = (lang = 'ru') => call<Movie[]>(`/profile/favorites?lang=${encodeURIComponent(lang)}`)
export const addFavorite = (id: number) => call<{ status: string }>(`/profile/favorites/${id}`, { method: 'POST' })
export const removeFavorite = (id: number) => call<{ status: string }>(`/profile/favorites/${id}`, { method: 'DELETE' })
export const getProfileNotifications = () => call<{ id: number; title: string; message: string; type: string; is_read: boolean; created_at: string }[]>('/profile/notifications')
export const readProfileNotification = (id: number) => call<{ is_read: boolean }>(`/profile/notifications/${id}/read`, { method: 'PATCH' })
