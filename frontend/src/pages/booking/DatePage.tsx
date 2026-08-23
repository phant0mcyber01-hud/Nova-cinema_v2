import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getMovie, getPublicSettings, type ScheduleDay } from '../../api'
import Shell from '../../components/Shell'
import { formatDateShort, formatSessionCount, useI18n } from '../../i18n'
import { apiMessage } from '../../lib/apiMessage'
import { haptic } from '../../lib/haptic'

/**
 * Only dates this movie actually plays on.
 *
 * The schedule already respects the admin-configured booking window, so there
 * is no separate settings call — and no date that leads to an empty session
 * list.
 */
export default function DatePage() {
  const { language, t } = useI18n()
  const { id } = useParams()
  const [schedule, setSchedule] = useState<ScheduleDay[] | null>(null)
  // The cinema's own dates. Naming a day from the phone's clock is wrong for
  // anyone whose device is in another time zone — the server knows better.
  const [cinemaDates, setCinemaDates] = useState<string[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    let active = true
    setSchedule(null)
    void Promise.all([getMovie(Number(id), language), getPublicSettings(language)])
      .then(([movie, settings]) => {
        if (!active) return
        setSchedule(movie.schedule)
        setCinemaDates(settings.booking_dates)
      })
      .catch(reason => {
        if (active) setError(apiMessage(reason, 'serverError'))
      })
    return () => { active = false }
  }, [id, language])

  const label = (date: string) => {
    if (date === cinemaDates[0]) return t('today')
    if (date === cinemaDates[1]) return t('tomorrow')
    return formatDateShort(date, language)
  }

  return (
    <Shell>
      <Link className="back" to={`/movies/${id}`}>← {t('back')}</Link>
      <h1>{t('chooseDate')}</h1>
      {error && <p className="error">{error}</p>}
      {!error && schedule === null && <p className="empty">{t('loadingSessions')}</p>}
      {schedule?.length === 0 && <p className="empty">{t('noSessionsYet')}</p>}
      {!!schedule?.length && (
        <div className="choice-list">
          {schedule.map(day => (
            <Link
              key={day.date}
              to={`/booking/${id}/date/${day.date}/time`}
              className="choice"
              onClick={haptic.select}
            >
              <b>{label(day.date)}</b>
              <span>{formatSessionCount(day.times.length, language)} · {day.times.slice(0, 3).join(', ')}</span>
            </Link>
          ))}
        </div>
      )}
    </Shell>
  )
}
