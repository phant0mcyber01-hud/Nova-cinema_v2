import { useEffect, useMemo, useState } from 'react'

import {
  createAdminSession,
  createAdminSessionsBulk,
  deleteAdminSession,
  updateAdminSession,
  type AdminSession,
  type MovieDetail,
} from '../../api'
import { formatDateShort, formatMoney, useI18n, type TranslationKey } from '../../i18n'

type SessionPayload = {
  movie_id: number
  show_date: string
  start_time: string
  ticket_price: number | null
  status: string
}
type SessionsViewProps = {
  movies: MovieDetail[]
  sessions: AdminSession[]
  onSaved: (message: string) => Promise<void>
}

const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/
const today = () => new Date().toISOString().slice(0, 10)

const sessionStatuses: { value: string; labelKey: TranslationKey }[] = [
  { value: 'active', labelKey: 'active' },
  { value: 'inactive', labelKey: 'inactive' },
  { value: 'cancelled', labelKey: 'statusCancelled' },
]
const emptySession = (movieId: number): SessionPayload => ({
  movie_id: movieId,
  show_date: today(),
  start_time: '19:00',
  ticket_price: null,
  status: 'active',
})
const statusLabel = (status: string, translate: (key: TranslationKey) => string) => {
  const option = sessionStatuses.find(item => item.value === status)
  return option ? translate(option.labelKey) : status
}

export default function SessionsView({ movies, sessions, onSaved }: SessionsViewProps) {
  const { language, t } = useI18n()
  const firstMovie = movies[0]?.id ?? 0
  const [draft, setDraft] = useState<SessionPayload>(() => emptySession(firstMovie))
  const [times, setTimes] = useState(['19:00'])
  const [nextTime, setNextTime] = useState('')
  const [rangeMode, setRangeMode] = useState(false)
  const [dateTo, setDateTo] = useState(today())
  const [editingId, setEditingId] = useState<number | null>(null)
  const [movieQuery, setMovieQuery] = useState('')
  const [listQuery, setListQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (draft.movie_id === 0 && firstMovie) setDraft(current => ({ ...current, movie_id: firstMovie }))
  }, [draft.movie_id, firstMovie])

  const movieOptions = useMemo(() => {
    const query = movieQuery.trim().toLowerCase()
    return movies.filter(movie => !query || `${movie.title} ${movie.genre}`.toLowerCase().includes(query))
  }, [movieQuery, movies])
  const visibleSessions = useMemo(() => {
    const query = listQuery.trim().toLowerCase()
    return sessions.filter(item => (
      !query || `${item.movie} ${item.show_date} ${item.start_time}`.toLowerCase().includes(query)
    ))
  }, [listQuery, sessions])

  const addTime = () => {
    if (!TIME_PATTERN.test(nextTime)) {
      setError(t('invalidTime'))
      return
    }
    if (!times.includes(nextTime)) setTimes(current => [...current, nextTime].sort())
    setNextTime('')
    setError('')
  }
  const reset = () => {
    setDraft(emptySession(firstMovie))
    setTimes(['19:00'])
    setRangeMode(false)
    setDateTo(today())
    setEditingId(null)
    setError('')
  }

  const save = async () => {
    if (!draft.movie_id || !draft.show_date || !times.length) {
      setError(t('sessionRequired'))
      return
    }
    if (rangeMode && dateTo < draft.show_date) {
      setError(t('sessionRequired'))
      return
    }
    if (!rangeMode) {
      const duplicates = times.filter(time => sessions.some(item => (
        item.id !== editingId
        && item.movie_id === draft.movie_id
        && item.show_date === draft.show_date
        && item.start_time === time
      )))
      if (duplicates.length) {
        setError(`${t('sessions')} ${duplicates.join(', ')} ${t('sessionDuplicate')}`)
        return
      }
    }
    setBusy(true)
    setError('')
    try {
      let message: string
      if (editingId !== null) {
        await updateAdminSession(editingId, { ...draft, start_time: times[0] })
        message = t('sessionSaved')
      } else if (rangeMode) {
        // The bulk endpoint skips slots that already exist, so a repeat is safe.
        const result = await createAdminSessionsBulk({
          movie_id: draft.movie_id,
          date_from: draft.show_date,
          date_to: dateTo,
          times,
          ticket_price: draft.ticket_price,
        })
        message = `${t('bulkCreated')}: ${result.created}`
      } else {
        await Promise.all(times.map(time => createAdminSession({ ...draft, start_time: time })))
        message = times.length > 1 ? `${t('sessionsCreatedToast')}: ${times.length}` : t('sessionCreated')
      }
      reset()
      await onSaved(message)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('sessionSaveFailed'))
    } finally {
      setBusy(false)
    }
  }

  const edit = (item: AdminSession) => {
    setEditingId(item.id)
    setRangeMode(false)
    setDraft({
      movie_id: item.movie_id,
      show_date: item.show_date,
      start_time: item.start_time,
      ticket_price: item.ticket_price,
      status: item.status,
    })
    setTimes([item.start_time])
    setMovieQuery('')
    setError('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  const remove = async (item: AdminSession) => {
    if (!window.confirm(`${t('deleteSessionConfirmPrefix')} "${item.movie}" ${item.show_date} ${item.start_time}?`)) return
    try {
      await deleteAdminSession(item.id)
      await onSaved(t('sessionDeleted'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('sessionSaveFailed'))
    }
  }

  return (
    <section>
      <div className="admin-page-intro">
        <span className="admin-eyebrow">{t('schedule')}</span>
        <h1>{t('sessionsManagement')}</h1>
        <p className="admin-hint">{t('sessionsManagementHint')}</p>
      </div>

      <section className="session-builder">
        <header>
          <span>{editingId === null ? t('newSession') : t('editSession')}</span>
          <b>{editingId === null ? t('createSchedule') : `${t('sessions')} #${editingId}`}</b>
        </header>

        <div className="session-step">
          <span className="session-step-number">1</span>
          <div className="session-step-body">
            <label><b>{t('movies')}</b><small>{t('moviePickHint')}</small></label>
            <input value={movieQuery} onChange={event => setMovieQuery(event.target.value)} placeholder={t('movieSearch')} />
            <select value={draft.movie_id} onChange={event => setDraft({ ...draft, movie_id: Number(event.target.value) })}>
              {!movieOptions.length && <option value="">{t('noResults')}</option>}
              {movieOptions.map(movie => <option value={movie.id} key={movie.id}>{movie.title} · {movie.genre}</option>)}
            </select>
          </div>
        </div>

        <div className="session-step">
          <span className="session-step-number">2</span>
          <div className="session-step-body">
            <label><b>{t('date')}</b><small>{rangeMode ? t('bulkScheduleHint') : t('dateHint')}</small></label>
            {editingId === null && (
              <div className="admin-toolbar">
                <button className={rangeMode ? 'admin-ghost' : 'admin-ghost active'} onClick={() => setRangeMode(false)}>
                  {t('singleDateMode')}
                </button>
                <button className={rangeMode ? 'admin-ghost active' : 'admin-ghost'} onClick={() => setRangeMode(true)}>
                  {t('bulkSchedule')}
                </button>
              </div>
            )}
            <div className="session-options">
              <label>
                <b>{rangeMode ? t('dateFrom') : t('date')}</b>
                <input
                  type="date"
                  value={draft.show_date}
                  onChange={event => setDraft({ ...draft, show_date: event.target.value })}
                />
              </label>
              {rangeMode && (
                <label>
                  <b>{t('dateTo')}</b>
                  <input type="date" value={dateTo} min={draft.show_date} onChange={event => setDateTo(event.target.value)} />
                </label>
              )}
            </div>
          </div>
        </div>

        <div className="session-step">
          <span className="session-step-number">3</span>
          <div className="session-step-body">
            <label><b>{t('timeShow')}</b><small>{editingId === null ? t('timeManyHint') : t('timeSingleHint')}</small></label>
            <div className="time-chips">
              {times.map(time => (
                <button key={time} onClick={() => setTimes(current => current.filter(item => item !== time))}>
                  {time}<span>×</span>
                </button>
              ))}
            </div>
            <div className="time-add">
              <input type="time" value={nextTime} onChange={event => setNextTime(event.target.value)} />
              <button className="admin-ghost" onClick={addTime} disabled={editingId !== null && times.length >= 1}>
                ＋ {t('addTime')}
              </button>
            </div>
          </div>
        </div>

        <div className="session-step">
          <span className="session-step-number">4</span>
          <div className="session-step-body session-options">
            <label>
              <b>{t('sessionPrice')}</b><small>{t('sessionPriceHint')}</small>
              <div className="input-with-suffix">
                <input
                  type="number"
                  min="1"
                  value={draft.ticket_price ?? ''}
                  onChange={event => setDraft({ ...draft, ticket_price: event.target.value ? Number(event.target.value) : null })}
                  placeholder={t('automatic')}
                />
                <span>{t('currency')}</span>
              </div>
            </label>
            <label><b>{t('hall')}</b><small>{t('hallHint')}</small><input value={t('mainHall')} disabled /></label>
            <label>
              <b>{t('sessionStatus')}</b><small>{t('sessionStatusHint')}</small>
              <select value={draft.status} onChange={event => setDraft({ ...draft, status: event.target.value })}>
                {sessionStatuses.map(item => <option value={item.value} key={item.value}>{t(item.labelKey)}</option>)}
              </select>
            </label>
          </div>
        </div>

        {error && <p className="error">{error}</p>}
        <footer className="session-builder-actions">
          {editingId !== null && <button className="admin-ghost" onClick={reset} disabled={busy}>{t('cancel')}</button>}
          <button className="book" onClick={() => { void save() }} disabled={busy}>
            {busy ? t('saving') : editingId === null ? t('createSession') : t('saveChanges')}
          </button>
        </footer>
      </section>

      <div className="section-head session-list-head">
        <div>
          <h2>{t('createdSessions')}</h2>
          <p className="admin-hint">{sessions.length} {t('inSchedule')}</p>
        </div>
        <input
          className="admin-input"
          value={listQuery}
          onChange={event => setListQuery(event.target.value)}
          placeholder={t('sessionSearchPlaceholder')}
        />
      </div>
      <div className="session-card-list">
        {visibleSessions.map(item => (
          <article className="session-card" key={item.id}>
            <div className="session-date"><b>{item.start_time}</b><span>{formatDateShort(item.show_date, language)}</span></div>
            <div className="session-card-body">
              <span className={`status-chip ${item.status === 'active' ? 'live' : 'muted'}`}>
                {statusLabel(item.status, t)}
              </span>
              <h3>{item.movie}</h3>
              <p>
                {item.ticket_price
                  ? formatMoney(item.ticket_price, language)
                  : `${t('calculatedPrice')} ${formatMoney(item.resolved_price, language)}`}
              </p>
            </div>
            <div className="admin-actions">
              <button className="admin-ghost" onClick={() => edit(item)}>{t('edit')}</button>
              <button className="admin-ghost danger" onClick={() => { void remove(item) }}>{t('remove')}</button>
            </div>
          </article>
        ))}
        {!visibleSessions.length && <p className="empty">{t('sessionsNotFound')}</p>}
      </div>
    </section>
  )
}
