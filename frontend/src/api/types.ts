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

export type Hall = {
  rows: number
  cols: number
  seats_count: number
  max_seats: number
  price: number
  currency: string
  taken: string[]
}

export type BookingPayload = {
  movie_id: number
  show_date: string
  session: string
  seats: string[]
  first_name: string
  last_name: string
  phone: string
  telegram_username: string
  comment: string
}

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
  status: string
}

export type AdminNotification = {
  id: number
  booking_id: number
  message: string
  is_read: boolean
  created_at: string
}

export type Profile = {
  first_name: string
  last_name: string
  phone: string
  telegram_id: number
  created_at: string
  bookings: number
}

export type ProfileBooking = {
  id: number
  uuid: string
  qr_token: string
  qr_valid: boolean
  movie: string
  poster: string
  description: string
  trailer_id: string
  show_date: string
  session: string
  seats: string
  total: number
  status: string
  phone: string
  telegram_username: string
  comment: string
  proposed_session: string
  admin_note: string
}

export type ProfileNotification = {
  id: number
  title: string
  message: string
  type: string
  is_read: boolean
  created_at: string
}

export type AuthState = {
  ready: boolean
  authenticated: boolean
  role: string
  isAdmin: boolean
}
