import { Link, useParams } from 'react-router-dom'

import Icon from '../../components/Icon'
import Shell from '../../components/Shell'
import AdminContacts from '../../components/AdminContacts'
import { useI18n } from '../../i18n'

export default function Success() {
  const { t } = useI18n()
  const { code } = useParams()

  return (
    <Shell>
      <section className="success">
        <span><Icon name="check" /></span>
        <h1>{t('requestCreated')}</h1>
        <p>{t('requestSentThanks')}</p>
        <AdminContacts className="success-contact" />
        <b>{t('ticketCode')}: {code}</b>
        <Link className="book" to="/">{t('home')}</Link>
      </section>
    </Shell>
  )
}
