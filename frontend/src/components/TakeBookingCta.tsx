import { Link } from 'react-router-dom'

import { useI18n } from '../i18n'
import { haptic } from '../lib/haptic'
import Icon from './Icon'

/**
 * Compact shortcut into the ticket flow, docked in the header next to the
 * language switch instead of floating over the catalog and bottom nav.
 */
export default function TakeBookingCta() {
  const { t } = useI18n()
  return (
    <Link className="take-booking-cta" to="/tickets" onClick={haptic.tap}>
      <Icon name="ticket" /> {t('takeBooking')}
    </Link>
  )
}
