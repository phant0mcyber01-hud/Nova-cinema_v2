import { Link, useParams } from 'react-router-dom'

import Shell from '../../components/Shell'
import { formatDateShort, useI18n } from '../../i18n'
import { bookingDates } from '../../lib/dates'
import { haptic } from '../../lib/haptic'

export default function DatePage() {
  const { language, t } = useI18n()
  const { id } = useParams()

  return (
    <Shell>
      <Link className="back" to="/">← {t('back')}</Link>
      <h1>{t('chooseDate')}</h1>
      <div className="choice-list">
        {bookingDates.map((date, index) => (
          <Link key={date} to={`/booking/${id}/date/${date}/time`} className="choice" onClick={haptic.select}>
            <b>{index === 0 ? t('today') : index === 1 ? t('tomorrow') : formatDateShort(date, language)}</b>
            <span>{t('chooseConvenientTime')}</span>
          </Link>
        ))}
      </div>
    </Shell>
  )
}
