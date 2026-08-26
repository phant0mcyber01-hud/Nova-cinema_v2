/** Shown only until GET /api/settings answers with the admin-configured window. */
export const fallbackBookingDates = Array.from({ length: 7 }, (_, index) => {
  const value = new Date()
  value.setDate(value.getDate() + index)
  return value.toISOString().slice(0, 10)
})
