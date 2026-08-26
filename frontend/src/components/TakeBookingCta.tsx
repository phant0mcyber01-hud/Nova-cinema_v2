import { Link } from 'react-router-dom'

import { useI18n } from '../i18n'
import { haptic } from '../lib/haptic'
import Icon from './Icon'

/**
 * A fast lane into the ticket flow from the poster screen, floating just
 * above the bottom tab bar. The Tickets tab already gets there -- this is
 * for the viewer who lands on the poster and wants to book without hunting
 * for the right tab first.
 */
export default function TakeBookingCta() {
  const { t } = useI18n()
  return (
    <Link className="take-booking-cta" to="/tickets" onClick={haptic.tap}>
      <Icon name="ticket" /> {t('takeBooking')}
    </Link>
  )
}
