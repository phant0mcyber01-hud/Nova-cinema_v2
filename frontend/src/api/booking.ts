import { call } from './client'
import type { BookingPayload } from './types'

export const holdSeats = (payload: { movie_id: number; show_date: string; session: string; seats: string[] }) =>
  call<{ total: number }>('/holds', { method: 'POST', body: JSON.stringify(payload) })

export const confirmBooking = (payload: BookingPayload) =>
  call<{ ticket_code: string; total: number; message: string }>('/bookings/confirm', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
