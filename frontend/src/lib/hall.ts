/** Seat labelling for the Nova Cinema auditorium: rows are letters, columns are numbers. */
export const rowLabel = (rowIndex: number) => (
  rowIndex < 26 ? String.fromCharCode(65 + rowIndex) : String(rowIndex + 1)
)

export function seatLabel(seat: string) {
  const [row, column] = seat.split('-').map(Number)
  return `${rowLabel(row - 1)}${column}`
}
