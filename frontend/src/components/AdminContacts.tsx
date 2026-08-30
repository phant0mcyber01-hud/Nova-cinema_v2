import { useI18n } from '../i18n'
import { useAdminContacts } from '../lib/useAdminContacts'
import { haptic } from '../lib/haptic'
import Icon from './Icon'

/**
 * A single "get in touch" link during checkout. The administrator settles
 * the film and the manual transfer by phone or Telegram, but showing the raw
 * number on the booking screen reads as noise while filling in a form -- so
 * this renders one compact call-to-action instead, icon and label side by
 * side, preferring Telegram when both channels are configured.
 */
export default function AdminContacts({ className = 'ticket-contact' }: { className?: string }) {
  const { t } = useI18n()
  const { phone, telegram } = useAdminContacts()
  if (!phone && !telegram) return null

  const href = telegram ? `https://t.me/${telegram}` : `tel:${phone.replace(/[^\d+]/g, '')}`

  return (
    <a className={className} href={href} onClick={haptic.tap}>
      <Icon name={telegram ? 'send' : 'phone'} /> {t('contactUs')}
    </a>
  )
}
