import { call } from './client'

/**
 * The generic booking flow: a date, one of the administrator's fixed times and
 * how many people are coming. No film and no seat appears anywhere in it —
 * both are agreed with the administrator afterwards.
 */

/** Pricing and capacity are admin settings, so every response repeats them. */
export type BookingCommon = {
  capacity: number
  rows: number
  cols: number
  price: number
  currency: string
  hold_minutes: number
  max_party_size: number
}

/** One day in the booking window, with how full it already is. */
export type BookingDate = { date: string; slots: number; available: number }

/** One fixed time on a date. `mine` is what this viewer is already holding. */
export type BookingSlot = {
  time: string
  capacity: number
  available: number
  taken: number
  mine: number
  price: number
}

/** A short-lived claim on places. The server allocates them; nothing is named. */
export type BookingHold = {
  date: string
  time: string
  party_size: number
  expires_in_minutes: number
  ticket_price: number
  total: number
  capacity: number
  available: number
}

export type BookingContacts = {
  first_name: string
  last_name: string
  phone: string
  telegram_username: string
  comment: string
}

export type BookingRequest = {
  id: number
  status: string
  ticket_code: string
  date: string
  time: string
  party_size: number
  ticket_price: number
  total: number
  message: string
}

export type BookingSelection = { date: string; time: string; party_size: number }

export const getBookingDates = () =>
  call<BookingCommon & { dates: BookingDate[] }>('/booking/dates')

export const getBookingSlots = (date: string) =>
  call<BookingCommon & { date: string; slots: BookingSlot[] }>(
    `/booking/slots?date=${encodeURIComponent(date)}`,
  )

export const holdBooking = (payload: BookingSelection) =>
  call<BookingHold>('/booking/holds', { method: 'POST', body: JSON.stringify(payload) })

/** Hand the places back when the viewer walks away from the form. */
export const releaseBookingHold = (date: string, time: string) =>
  call<{ status: string }>(
    `/booking/holds?date=${encodeURIComponent(date)}&time=${encodeURIComponent(time)}`,
    { method: 'DELETE' },
  )

/**
 * File the request. The backend re-reads the caller's live hold from the same
 * date, time and party size, so the selection is sent again rather than a token.
 */
export const confirmBooking = (payload: BookingSelection & BookingContacts) =>
  call<BookingRequest>('/booking/requests', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
