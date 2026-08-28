import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { getMovies, getPublicSettings, type Movie } from '../api'
import MovieCard from '../components/MovieCard'
import Icon from '../components/Icon'
import Shell from '../components/Shell'
import TakeBookingCta from '../components/TakeBookingCta'
import { setCurrency, useI18n } from '../i18n'
import { apiMessage } from '../lib/apiMessage'
import { haptic } from '../lib/haptic'

const SEARCH_DEBOUNCE_MS = 300
const PRIORITY_GENRES = ['Ужасы', "Qo'rqinchli", 'Мультфильм', 'Multfilm']

/**
 * A film carries its genres in one field, comma-separated ("Фантастика,
 * Боевик"), so each one has to be read out separately. Treating the field as
 * a single label made a filter nobody clicks and left the real "Боевик"
 * section without the film.
 */
const canonicalGenre = (value: string) => {
  const trimmed = value.trim()
  return trimmed ? `${trimmed.charAt(0).toLocaleUpperCase()}${trimmed.slice(1)}` : ''
}

const splitGenres = (value: string) =>
  (value ?? '').split(',').map(canonicalGenre).filter(Boolean)

export default function Home() {
  const { language, t } = useI18n()
  const [movies, setMovies] = useState<Movie[]>([])
  const [query, setQuery] = useState('')
  const [appliedQuery, setAppliedQuery] = useState('')
  const [onlyNew, setOnlyNew] = useState(false)
  const [genre, setGenre] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // The currency is an admin setting, so it is fetched.
  useEffect(() => {
    let active = true
    void getPublicSettings(language)
      .then(settings => {
        if (!active) return
        setCurrency(settings.currency)
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
    void getMovies(language, { q: appliedQuery, onlyNew })
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
  }, [appliedQuery, language, onlyNew])

  const genres = useMemo(() => {
    const unique = Array.from(new Set(movies.flatMap(movie => splitGenres(movie.genre))))
    const priority = PRIORITY_GENRES.filter(item => unique.includes(item))
    const rest = unique
      .filter(item => !PRIORITY_GENRES.includes(item))
      .sort((left, right) => left.localeCompare(right, language))
    return [...priority, ...rest]
  }, [language, movies])
  // Genre stays a client-side facet over whatever the server returned.
  const visible = useMemo(
    () => movies.filter(movie => !genre || splitGenres(movie.genre).includes(genre)),
    [genre, movies],
  )
  const newReleases = useMemo(() => movies.filter(movie => movie.is_new), [movies])
  const hits = useMemo(() => movies.filter(movie => movie.is_hit), [movies])
  const filtered = Boolean(appliedQuery.trim() || onlyNew || genre)
  const reset = () => {
    haptic.tap()
    setQuery('')
    setAppliedQuery('')
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
        <span><Icon name="search" /></span>
        <input
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder={t('searchWidePlaceholder')}
        />
        {query && <button className="search-clear" onClick={() => setQuery('')} aria-label={t('resetFilters')}>×</button>}
      </div>

      <div className="filters genres">
        <button
          className={onlyNew ? 'active' : ''}
          onClick={() => { haptic.select(); setOnlyNew(!onlyNew) }}
        >
          <Icon name="new" /> {t('newSection')}
        </button>
        <button className={!genre ? 'active' : ''} onClick={() => setGenre('')}>{t('allGenres')}</button>
        {genres.map(item => (
          <button className={genre === item ? 'active' : ''} onClick={() => setGenre(item)} key={item}>{item}</button>
        ))}
      </div>

      <section>
        <div className="strip-head"><h2>{t('allGenres')}</h2></div>
        <div className="catalog">
          {loading && [1, 2, 3, 4].map(item => <div className="skeleton-card" key={item}><div /><span /></div>)}
          {!loading && visible.map(movie => <MovieCard movie={movie} key={movie.id} />)}
          {!loading && !visible.length && !error && <p className="empty">{filtered ? t('nothingFound') : t('moviesNotFound')}{filtered && <button className="admin-ghost reset-filters" onClick={reset}>{t('resetFilters')}</button>}</p>}
          {error && <p className="error">{error}</p>}
        </div>
      </section>

      {!onlyNew && !appliedQuery.trim() && newReleases.length > 0 && (
        <section className="new-strip">
          <div className="strip-head">
            <h2><Icon name="new" /> {t('newSection')}</h2>
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

      {!onlyNew && !appliedQuery.trim() && hits.length > 0 && (
        <section className="new-strip hits-strip">
          <div className="strip-head">
            <h2><Icon name="flame" /> {t('hitsSection')}</h2>
            <p>{t('hitsSectionHint')}</p>
          </div>
          <div className="new-rail">
            {hits.map(movie => (
              <Link className="new-card" to={`/movies/${movie.id}`} key={movie.id} onClick={haptic.tap}>
                <img src={movie.poster} alt={movie.title} loading="lazy" />
                <b>{movie.title}</b>
                <span>{movie.genre} · {movie.age}+</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {!filtered && genres.map(item => <section key={item} className="genre-section"><div className="strip-head"><h2>{item}</h2></div><div className="catalog">{movies.filter(movie => splitGenres(movie.genre).includes(item)).map(movie => <MovieCard movie={movie} key={movie.id} />)}</div></section>)}

      <TakeBookingCta />
    </Shell>
  )
}
