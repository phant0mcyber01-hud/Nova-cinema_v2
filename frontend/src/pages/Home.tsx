import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { getMovies, getPublicSettings, type Movie } from '../api'
import MovieCard from '../components/MovieCard'
import Shell from '../components/Shell'
import { formatDateShort, setCurrency, useI18n } from '../i18n'
import { apiMessage } from '../lib/apiMessage'
import { fallbackBookingDates } from '../lib/dates'
import { haptic } from '../lib/haptic'

const SEARCH_DEBOUNCE_MS = 300

export default function Home() {
  const { language, t } = useI18n()
  const [movies, setMovies] = useState<Movie[]>([])
  const [dates, setDates] = useState<string[]>(fallbackBookingDates)
  const [date, setDate] = useState('')
  const [query, setQuery] = useState('')
  const [appliedQuery, setAppliedQuery] = useState('')
  const [onlyNew, setOnlyNew] = useState(false)
  const [genre, setGenre] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // The booking window and the currency are admin settings, so they are fetched.
  useEffect(() => {
    let active = true
    void getPublicSettings(language)
      .then(settings => {
        if (!active) return
        setCurrency(settings.currency)
        if (settings.booking_dates.length) setDates(settings.booking_dates)
      })
      .catch(() => undefined)
    return () => { active = false }
  }, [language])

  // Typing should not fire a request per keystroke.
  useEffect(() => {
    const timer = window.setTimeout(() => setAppliedQuery(query), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [query])

  useEffect(() => {
    let active = true
    setLoading(true)
    void getMovies(language, { date: date || undefined, q: appliedQuery, onlyNew })
      .then(data => {
        if (!active) return
        setMovies(data)
        setError('')
      })
      .catch(reason => {
        if (active) setError(apiMessage(reason, 'serverError'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [appliedQuery, date, language, onlyNew])

  const genres = useMemo(
    () => Array.from(new Set(movies.map(movie => movie.genre)))
      .sort((left, right) => left.localeCompare(right, language)),
    [language, movies],
  )
  // Genre stays a client-side facet over whatever the server returned.
  const visible = useMemo(
    () => movies.filter(movie => !genre || movie.genre === genre),
    [genre, movies],
  )
  const newReleases = useMemo(() => movies.filter(movie => movie.is_new), [movies])
  const filtered = Boolean(appliedQuery.trim() || date || onlyNew || genre)
  const dateLabel = (value: string, index: number) => (
    index === 0 ? t('today') : index === 1 ? t('tomorrow') : formatDateShort(value, language)
  )
  const reset = () => {
    haptic.tap()
    setQuery('')
    setAppliedQuery('')
    setDate('')
    setOnlyNew(false)
    setGenre('')
  }

  return (
    <Shell>
      <section className="hero-home">
        <p>NOVA CINEMA</p>
        <h1>{t('homeTitleLine1')}<br />{t('homeTitleLine2')}</h1>
      </section>

      <div className="search">
        <span>⌕</span>
        <input
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder={t('searchWidePlaceholder')}
        />
        {query && <button className="search-clear" onClick={() => setQuery('')} aria-label={t('resetFilters')}>×</button>}
      </div>

      <section className="date-strip" aria-label={t('availableDates')}>
        <h2 className="strip-title">{t('availableDates')}</h2>
        <div className="filters dates">
          <button className={!date ? 'active' : ''} onClick={() => { haptic.select(); setDate('') }}>
            {t('allDates')}
          </button>
          {dates.map((value, index) => (
            <button
              key={value}
              className={date === value ? 'active' : ''}
              onClick={() => { haptic.select(); setDate(date === value ? '' : value) }}
            >
              {dateLabel(value, index)}
            </button>
          ))}
        </div>
      </section>

      <div className="filters genres">
        <button
          className={onlyNew ? 'active' : ''}
          onClick={() => { haptic.select(); setOnlyNew(!onlyNew) }}
        >
          🆕 {t('newSection')}
        </button>
        <button className={!genre ? 'active' : ''} onClick={() => setGenre('')}>{t('allGenres')}</button>
        {genres.map(item => (
          <button className={genre === item ? 'active' : ''} onClick={() => setGenre(item)} key={item}>{item}</button>
        ))}
      </div>

      {!date && !onlyNew && !appliedQuery.trim() && newReleases.length > 0 && (
        <section className="new-strip">
          <div className="strip-head">
            <h2>🆕 {t('newSection')}</h2>
            <p>{t('newSectionHint')}</p>
          </div>
          <div className="new-rail">
            {newReleases.map(movie => (
              <Link className="new-card" to={`/movies/${movie.id}`} key={movie.id} onClick={haptic.tap}>
                <img src={movie.poster} alt={movie.title} loading="lazy" />
                <b>{movie.title}</b>
                <span>{movie.genre} · {movie.age}+</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="catalog">
        {loading && [1, 2, 3, 4].map(item => <div className="skeleton-card" key={item}><div /><span /></div>)}
        {!loading && visible.map(movie => <MovieCard movie={movie} key={movie.id} />)}
        {!loading && !visible.length && !error && (
          <p className="empty">
            {filtered ? t('nothingFound') : t('moviesNotFound')}
            {filtered && <button className="admin-ghost reset-filters" onClick={reset}>{t('resetFilters')}</button>}
          </p>
        )}
        {error && <p className="error">{error}</p>}
      </section>
    </Shell>
  )
}
