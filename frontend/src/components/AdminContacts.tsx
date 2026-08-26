import { useAdminContacts } from '../lib/useAdminContacts'

/**
 * One line: a callable number and a tappable Telegram handle.
 *
 * Both are admin settings — the administrator is the person a viewer talks to
 * about the film and the transfer, and that contact has to be changeable
 * without rebuilding the app.
 */
export default function AdminContacts({ className = 'ticket-contact' }: { className?: string }) {
  const { phone, telegram } = useAdminContacts()
  if (!phone && !telegram) return null

  return (
    <p className={className}>
      {phone && <a href={`tel:${phone.replace(/[^\d+]/g, '')}`}>{phone}</a>}
      {phone && telegram && ' · '}
      {telegram && <a href={`https://t.me/${telegram}`}>@{telegram}</a>}
    </p>
  )
}
