import { Link, useParams } from 'react-router-dom'

import Shell from '../../components/Shell'
import { useI18n } from '../../i18n'

export default function Success() {
  const { t } = useI18n()
  const { code } = useParams()

  return (
    <Shell>
      <section className="success">
        <span>✓</span>
        <h1>{t('requestCreated')}</h1>
        <p>{t('requestSentThanks')}</p>
        <b>{t('ticketCode')}: {code}</b>
        <Link className="book" to="/">{t('home')}</Link>
      </section>
    </Shell>
  )
}
