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
  is_new: boolean
  new_until: string
  is_hit: boolean
  sort_order: number
}

/** One day of the movie card schedule. */
export type ScheduleDay = { date: string; times: string[] }

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
  schedule: ScheduleDay[]
  /** t.me deep link, empty until the bot handle is set in the admin panel. */
  share_link: string
  /** Whether this viewer may leave a review right now (spec 14). */
  can_review: boolean
  has_reviewed: boolean
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
  is_new: boolean
  new_until: string
  is_hit: boolean
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
  hold_minutes: number
  /** Confirmed or already watched — final. */
  booked: string[]
  /** A request the admin has not decided yet, or somebody else's live hold. */
  awaiting: string[]
  /** Seats this viewer is currently holding. */
  mine: string[]
  /** Union of booked and awaiting: everything that cannot be picked. */
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
  promo_code: string
}

export type AdminBooking = {
  id: number
  status: string
  phone: string
  name: string
  comment: string
  promo_code: string
  /** Unit price frozen when the request was made. */
  ticket_price: number
  total: number
  seats: string | null
  seats_count: number | null
  party_size: number
  created_at: string
  telegram_id: number
  session: string
  show_date: string
  movie_id: number
  movie: string | null
  poster: string | null
  telegram_username: string
  chat_url: string | null
  proposed_session: string
  admin_note: string
}

export type AdminSession = {
  id: number
  show_date: string
  start_time: string
  /** Legacy mirror of start_time kept while the API accepts both. */
  session: string
  ticket_price: number | null
  resolved_price: number
  status: string
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
  seats: string | null
  party_size: number
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

export type PublicSettings = {
  name: string
  address: string
  phone: string
  /** The person a viewer calls about the film and the transfer. */
  admin_phone: string
  admin_telegram: string
  telegram_url: string
  instagram_url: string
  bot_username: string
  map_url: string
  latitude: number | null
  longitude: number | null
  work_hours: string
  about: string
  important?: string
  faq?: { question: string; answer: string }[]
  base_ticket_price: number
  currency: string
  hall_rows: number
  hall_cols: number
  hall_seats: number
  max_seats_per_booking: number
  booking_days_ahead: number
  booking_dates: string[]
}

export type Bonus = { id: number; title: string; text: string }
export type GalleryImage = { id: number; image_url: string; caption: string }

export type AdminSettings = {
  name: string
  name_uz: string
  address: string
  address_uz: string
  phone: string
  telegram_url: string
  instagram_url: string
  bot_username: string
  map_url: string
  latitude: number | null
  longitude: number | null
  work_hours: string
  work_hours_uz: string
  about: string
  about_uz: string
  important: string
  important_uz: string
  faq: { question_ru: string; answer_ru: string; question_uz: string; answer_uz: string }[]
  base_ticket_price: number
  currency: string
  hall_rows: number
  hall_cols: number
  hall_seats: number
  max_seats_per_booking: number
  hold_minutes: number
  booking_days_ahead: number
  /** Hours a request may wait for the admin; 0 turns automatic expiry off. */
  pending_expire_hours: number
  timezone_offset_minutes: number
  updated_at: string
}

/** hall_seats and updated_at are derived server-side and never submitted. */
export type AdminSettingsPayload = Omit<AdminSettings, 'hall_seats' | 'updated_at'>

export type AdminBonus = {
  id: number
  title: string
  title_uz: string
  text: string
  text_uz: string
  is_active: boolean
  sort_order: number
}

export type AdminBonusPayload = Omit<AdminBonus, 'id'>


export type AdminReview = {
  id: number
  movie_id: number | null
  movie: string | null
  poster: string | null
  user_name: string
  telegram_username: string
  rating: number
  text: string
  approved: boolean
  created_at: string
}

/** One of the cinema's fixed times. It belongs to the hall, not to a film. */
export type AdminSlot = {
  id: number
  start_time: string
  is_active: boolean
  sort_order: number
}

export type AdminSlotPayload = Omit<AdminSlot, 'id'>

/** What the schedule form submits. `session` is not sent — the API takes `start_time`. */
export type AdminSessionPayload = {
  show_date: string
  start_time: string
  ticket_price: number | null
  status: string
}

export type AdminGalleryImage = {
  id: number
  image_url: string
  caption: string
  caption_uz: string
  sort_order: number
}

export type AdminGalleryImagePayload = Omit<AdminGalleryImage, 'id'>
