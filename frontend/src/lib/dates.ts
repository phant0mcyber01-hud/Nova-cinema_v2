/** The booking window offered in the Mini App: today plus the next six days. */
export const bookingDates = Array.from({ length: 7 }, (_, index) => {
  const value = new Date()
  value.setDate(value.getDate() + index)
  return value.toISOString().slice(0, 10)
})
