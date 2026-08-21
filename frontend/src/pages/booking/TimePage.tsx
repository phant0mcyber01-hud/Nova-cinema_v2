import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getSessions } from '../../api'
import Shell from '../../components/Shell'
import { useI18n } from '../../i18n'
import { apiMessage } from '../../lib/apiMessage'
import { haptic } from '../../lib/haptic'

/** Screenings come from the admin-managed schedule; there is no free-text time. */
export default function TimePage() {
  const { t } = useI18n()
  const { id, date } = useParams()
  const [sessions, setSessions] = useState<string[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id || !date) return
    let active = true
    setSessions(null)
    setError('')
    void getSessions(Number(id), date)
      .then(data => {
        if (active) setSessions(data.sessions)
      })
      .catch(reason => {
        if (active) setError(apiMessage(reason, 'serverError'))
      })
    return () => { active = false }
  }, [date, id])

  return (
    <Shell>
      <Link className="back" to={`/booking/${id}/date`}>← {t('date')}</Link>
      <h1>{t('chooseSession')}</h1>
      {error && <p className="error">{error}</p>}
      {!error && sessions === null && <p className="empty">{t('loadingSessions')}</p>}
      {!error && sessions?.length === 0 && (
        <div className="manual-time-card">
          <p className="empty">{t('noSessionsForDate')}</p>
          <Link className="book" to={`/booking/${id}/date`} onClick={haptic.tap}>{t('chooseDate')}</Link>
        </div>
      )}
      {!!sessions?.length && (
        <div className="choice-list">
          {sessions.map(time => (
            <Link
              key={time}
              className="choice"
              to={`/booking/${id}/date/${date}/time/${time}/hall`}
              onClick={haptic.select}
            >
              <b>{time}</b>
              <span>{t('chooseSeats')}</span>
            </Link>
          ))}
        </div>
      )}
    </Shell>
  )
}
