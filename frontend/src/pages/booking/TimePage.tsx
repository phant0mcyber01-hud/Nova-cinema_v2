import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { getPublicSettings, getSessions } from '../../api'
import Shell from '../../components/Shell'
import { useI18n } from '../../i18n'
import { apiMessage } from '../../lib/apiMessage'
import { haptic } from '../../lib/haptic'

/** Same rule the server applies to a freeform time. */
const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/
const HOURS = Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, '0'))
const MINUTES = ['00', '05', '10', '15', '20', '25', '30', '35', '40', '45', '50', '55']

/**
 * The viewer names the hour.
 *
 * The admin schedule still decides which dates a movie plays on, and the times
 * configured for that date are offered as one tap, but any well-formed HH:MM
 * may be requested: the seat is then held for exactly the time that was asked
 * for, and nobody else can take that seat at that time.
 */
export default function TimePage() {
  const { language, t } = useI18n()
  const { id, date } = useParams()
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<string[] | null>(null)
  const [hour, setHour] = useState('')
  const [minute, setMinute] = useState('')
  const chosenTime = hour && minute ? `${hour}:${minute}` : ''
  const [workHours, setWorkHours] = useState('')
  const [error, setError] = useState('')
  const [timeError, setTimeError] = useState('')

  // Opening hours are free text the admin types, not a rule the server enforces,
  // so they are shown as guidance next to the input and never block a request.
  useEffect(() => {
    let active = true
    void getPublicSettings(language)
      .then(settings => {
        if (active) setWorkHours(settings.work_hours)
      })
      .catch(() => undefined)
    return () => { active = false }
  }, [language])

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

  // An empty or half-typed value never reaches the hall: the server would only
  // answer 404 for it, and the viewer would be left guessing why.
  const continueToHall = () => {
    if (!TIME_PATTERN.test(chosenTime)) {
      setTimeError(t('invalidTime'))
      haptic.error()
      return
    }
    setTimeError('')
    haptic.select()
    navigate(`/booking/${id}/date/${date}/time/${chosenTime}/hall`)
  }

  return (
    <Shell>
      <Link className="back" to={`/booking/${id}/date`}>← {t('date')}</Link>
      <h1>{t('chooseSession')}</h1>
      {error && <p className="error">{error}</p>}

      <div className="manual-time-card">
        <label>
          <span>{t('anyTime')}</span>
          <div className="time-select-row">
            <select
              value={hour}
              onChange={event => { setHour(event.target.value); setTimeError('') }}
              aria-label={t('timeHour')}
            >
              <option value="" disabled>{t('timeHour')}</option>
              {HOURS.map(value => <option key={value} value={value}>{value}</option>)}
            </select>
            <span className="time-select-colon">:</span>
            <select
              value={minute}
              onChange={event => { setMinute(event.target.value); setTimeError('') }}
              aria-label={t('timeMinute')}
            >
              <option value="" disabled>{t('timeMinute')}</option>
              {MINUTES.map(value => <option key={value} value={value}>{value}</option>)}
            </select>
          </div>
        </label>
        <p className="empty">{t('anyTimeHint')}</p>
        {workHours && <p className="empty">{t('workHours')}: {workHours}</p>}
        {timeError && <p className="error">{timeError}</p>}
        <button className="book" onClick={continueToHall} disabled={!chosenTime}>
          {t('chooseSeats')}
        </button>
      </div>

      {!error && sessions === null && <p className="empty">{t('loadingSessions')}</p>}
      {!error && sessions?.length === 0 && <p className="empty">{t('noSessionsForDate')}</p>}
      {!!sessions?.length && (
        <>
          <p className="empty">{t('suggestedTimes')}</p>
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
        </>
      )}
    </Shell>
  )
}
