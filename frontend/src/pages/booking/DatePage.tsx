import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getPublicSettings } from '../../api'
import Shell from '../../components/Shell'
import { formatDateShort, useI18n } from '../../i18n'
import { fallbackBookingDates } from '../../lib/dates'
import { haptic } from '../../lib/haptic'

/** The booking window length is an admin setting, not a constant in the code. */
export default function DatePage() {
  const { language, t } = useI18n()
  const { id } = useParams()
  const [dates, setDates] = useState<string[]>(fallbackBookingDates)

  useEffect(() => {
    let active = true
    void getPublicSettings(language)
      .then(settings => {
        if (active && settings.booking_dates.length) setDates(settings.booking_dates)
      })
      .catch(() => undefined)
    return () => { active = false }
  }, [language])

  return (
    <Shell>
      <Link className="back" to="/">← {t('back')}</Link>
      <h1>{t('chooseDate')}</h1>
      <div className="choice-list">
        {dates.map((date, index) => (
          <Link key={date} to={`/booking/${id}/date/${date}/time`} className="choice" onClick={haptic.select}>
            <b>{index === 0 ? t('today') : index === 1 ? t('tomorrow') : formatDateShort(date, language)}</b>
            <span>{t('chooseSession')}</span>
          </Link>
        ))}
      </div>
    </Shell>
  )
}
