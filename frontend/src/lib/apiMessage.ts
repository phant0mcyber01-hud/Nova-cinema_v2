import { ApiError } from '../api'
import { translate, type TranslationKey } from '../i18n'

/**
 * Server errors, said in the viewer's language.
 *
 * The API answers in English — "Seat is temporarily held", "Hold expired" —
 * and those strings were being printed straight onto a Russian or Uzbek
 * screen. The set is small and closed, so it is mapped here rather than
 * translated on the server: the API keeps one stable vocabulary for its
 * clients, and the interface stays the only place that speaks to people.
 */
const EXACT: Record<string, TranslationKey> = {
  'Authentication required': 'profileTelegramAuthError',
  'Invalid access token': 'profileTelegramAuthError',
  'Invalid Telegram signature': 'profileTelegramAuthError',
  'Telegram initData expired': 'profileTelegramAuthError',
  'User not found': 'profileTelegramAuthError',
  'Movie not found': 'movieUnavailable',
  'Session not found': 'noSessionsForDate',
  'Session already started': 'sessionAlreadyStarted',
  'Seat is temporarily held': 'seatTakenMeanwhile',
  'Seat is already booked': 'seatTakenMeanwhile',
  'Hold expired': 'holdExpired',
  'Invalid seats': 'invalidSeats',
  'Invalid phone number': 'invalidPhoneNumber',
  'Review is available after viewing': 'reviewAfterViewing',
  'You have already reviewed this movie': 'alreadyReviewedThisMovie',
  'Booking not found': 'bookingNotFound',
}

/** Details that carry data, matched by their stable beginning. */
const PREFIXED: [string, TranslationKey][] = [
  ['Seats already taken', 'seatTakenMeanwhile'],
  ['Maximum', 'tooManySeats'],
]

export const apiMessage = (reason: unknown, fallback: TranslationKey): string => {
  const detail = reason instanceof ApiError ? reason.message : ''
  if (detail) {
    const exact = EXACT[detail]
    if (exact) return translate(exact)
    const prefixed = PREFIXED.find(([start]) => detail.startsWith(start))
    if (prefixed) return translate(prefixed[1])
  }
  // A message we did not write is not worth showing: it is either English or
  // a stack of internals.
  return translate(fallback)
}
