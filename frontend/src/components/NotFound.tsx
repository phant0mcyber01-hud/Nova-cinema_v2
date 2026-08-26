import { Link } from 'react-router-dom'

import Shell from './Shell'
import Icon from './Icon'
import { useI18n } from '../i18n'

/**
 * Where an unknown address lands.
 *
 * Without it a stale deep link — or a typo — rendered an empty screen with no
 * navigation at all, and the only way out of a Mini App was to close it.
 */
export default function NotFound() {
  const { t } = useI18n()
  return (
    <Shell>
      <section className="unavailable">
        <span aria-hidden="true"><Icon name="film" /></span>
        <h1>{t('pageNotFound')}</h1>
        <p>{t('pageNotFoundHint')}</p>
        <Link className="book fit" to="/">{t('toCatalog')}</Link>
      </section>
    </Shell>
  )
}
