import { call } from './client'
import type { BookingPayload } from './types'

export const holdSeats = (payload: { movie_id: number; show_date: string; session: string; seats: string[] }) =>
  call<{ expires_at: string; seats: string[]; ticket_price: number; total: number }>('/holds', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const confirmBooking = (payload: BookingPayload) =>
  call<{ ticket_code: string; total: number; message: string }>('/bookings/confirm', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const releaseSeats = (movie_id: number, show_date: string, session_time: string) => {
  const query = new URLSearchParams({ movie_id: String(movie_id), show_date, session_time })
  return call<{ status: string }>(`/holds?${query.toString()}`, { method: 'DELETE' })
}
