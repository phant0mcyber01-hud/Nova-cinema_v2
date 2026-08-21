import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getMovie, type ScheduleDay } from '../../api'
import Shell from '../../components/Shell'
import { formatDateShort, formatSessionCount, translate, useI18n } from '../../i18n'
import { haptic } from '../../lib/haptic'

const today = () => new Date().toISOString().slice(0, 10)
const tomorrow = () => new Date(Date.now() + 86_400_000).toISOString().slice(0, 10)

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
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    let active = true
    setSchedule(null)
    void getMovie(Number(id), language)
      .then(movie => {
        if (active) setSchedule(movie.schedule)
      })
      .catch(reason => {
        if (active) setError(reason instanceof Error ? reason.message : translate('serverError'))
      })
    return () => { active = false }
  }, [id, language])

  const label = (date: string) => {
    if (date === today()) return t('today')
    if (date === tomorrow()) return t('tomorrow')
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
