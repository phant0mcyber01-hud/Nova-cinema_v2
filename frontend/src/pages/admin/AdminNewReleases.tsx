import { useMemo, useState } from 'react'

import { updateAdminMovie, type MovieDetail, type MoviePayload } from '../../api'
import { useI18n } from '../../i18n'
import { toMoviePayload } from './moviePayload'

type NewReleasesViewProps = {
  movies: MovieDetail[]
  onSaved: (message: string) => Promise<void>
}

const today = () => new Date().toISOString().slice(0, 10)

/** Spec 4.3: mark a movie as a new release, unmark it, or give the badge an end date. */
export default function NewReleasesView({ movies, onSaved }: NewReleasesViewProps) {
  const { t } = useI18n()
  const [query, setQuery] = useState('')
  const [onlyNew, setOnlyNew] = useState(false)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState('')

  const rows = useMemo(() => {
    const text = query.trim().toLowerCase()
    return movies.filter(movie => (
      (!onlyNew || movie.is_new) && (!text || `${movie.title} ${movie.genre}`.toLowerCase().includes(text))
    ))
  }, [movies, onlyNew, query])

  const patch = async (movie: MovieDetail, changes: Partial<MoviePayload>, message: string) => {
    setBusyId(movie.id)
    setError('')
    try {
      await updateAdminMovie(movie.id, { ...toMoviePayload(movie), ...changes })
      await onSaved(message)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('movieSaveFailed'))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section>
      <div className="admin-page-intro">
        <span className="admin-eyebrow">{t('adminNewTab')}</span>
        <h1>{t('newReleases')}</h1>
        <p className="admin-hint">{t('newReleasesHint')}</p>
      </div>

      <div className="admin-toolbar">
        <input
          className="admin-input"
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder={t('movieSearchAdminPlaceholder')}
        />
        <button className={onlyNew ? 'admin-ghost active' : 'admin-ghost'} onClick={() => setOnlyNew(!onlyNew)}>
          {t('newOnly')}
        </button>
      </div>
      {error && <p className="error">{error}</p>}

      <div className="admin-table">
        {rows.map(movie => {
          const expired = movie.is_new && !!movie.new_until && movie.new_until < today()
          return (
            <article className="admin-row" key={movie.id}>
              <img src={movie.poster} alt={movie.title} loading="lazy" />
              <div className="booking-admin-meta">
                <b>{movie.title}</b>
                <span>{movie.genre} · {movie.year}</span>
                <span>
                  {movie.is_new
                    ? <span className={expired ? 'status-chip muted' : 'status-chip live'}>
                        {expired ? t('newExpired') : t('newBadge')}
                      </span>
                    : <span className="status-chip muted">{t('disabled')}</span>}
                </span>
                {movie.is_new && (
                  <label className="admin-inline-field">
                    <small>{t('newUntil')}</small>
                    <input
                      type="date"
                      value={movie.new_until}
                      disabled={busyId === movie.id}
                      onChange={event => {
                        void patch(movie, { new_until: event.target.value }, t('newReleaseUpdated'))
                      }}
                    />
                    <small>{t('newUntilHint')}</small>
                  </label>
                )}
              </div>
              <div className="admin-actions">
                <button
                  className={movie.is_new ? 'admin-ghost danger' : 'admin-ghost'}
                  disabled={busyId === movie.id}
                  onClick={() => {
                    void patch(
                      movie,
                      movie.is_new ? { is_new: false, new_until: '' } : { is_new: true },
                      t('newReleaseUpdated'),
                    )
                  }}
                >
                  {movie.is_new ? t('unmarkNew') : t('markAsNew')}
                </button>
              </div>
            </article>
          )
        })}
        {!rows.length && <p className="empty">{onlyNew ? t('noNewReleases') : t('moviesNotFound')}</p>}
      </div>
    </section>
  )
}
