import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { getMovies, type Movie } from '../api'
import Shell from '../components/Shell'
import { translate, useI18n } from '../i18n'
import { haptic } from '../lib/haptic'

export default function Home() {
  const { language, t } = useI18n()
  const [movies, setMovies] = useState<Movie[]>([])
  const [query, setQuery] = useState('')
  const [genre, setGenre] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void getMovies(language)
      .then(data => {
        if (active) setMovies(data)
      })
      .catch(reason => {
        if (active) setError(reason instanceof Error ? reason.message : translate('serverError'))
      })
    return () => { active = false }
  }, [language])

  const genres = useMemo(
    () => Array.from(new Set(movies.map(movie => movie.genre))).sort((left, right) => left.localeCompare(right, language)),
    [language, movies],
  )
  const visible = useMemo(
    () => movies.filter(movie => movie.title.toLowerCase().includes(query.toLowerCase()) && (!genre || movie.genre === genre)),
    [genre, movies, query],
  )

  return (
    <Shell>
      <section className="hero-home">
        <p>NOVA CINEMA</p>
        <h1>{t('homeTitleLine1')}<br />{t('homeTitleLine2')}</h1>
      </section>
      <div className="search">
        <span>⌕</span>
        <input value={query} onChange={event => setQuery(event.target.value)} placeholder={t('movieSearch')} />
      </div>
      <div className="filters genres">
        <button className={!genre ? 'active' : ''} onClick={() => setGenre('')}>{t('allGenres')}</button>
        {genres.map(item => (
          <button className={genre === item ? 'active' : ''} onClick={() => setGenre(item)} key={item}>{item}</button>
        ))}
      </div>
      <section className="catalog">
        {movies.length ? visible.map(movie => (
          <article className="movie" key={movie.id}>
            <Link className="movie-link" to={`/movies/${movie.id}`}>
              <img src={movie.poster} alt={movie.title} loading="lazy" />
              <div className="movie-shade" />
              <div className="movie-body">
                <span className="rating-chip">IMDb {movie.imdb} · {t('kinopoiskShort')} {movie.kinopoisk}</span>
                <h2>{movie.title}</h2>
                <p>{movie.genre} · {movie.age}+ · {movie.duration} {t('minutes')}</p>
              </div>
            </Link>
            <Link className="book movie-book" to={`/booking/${movie.id}/date`} onClick={haptic.tap}>{t('bookTicket')}</Link>
          </article>
        )) : !error && [1, 2, 3, 4].map(item => <div className="skeleton-card" key={item}><div /><span /></div>)}
        {movies.length > 0 && !visible.length && <p className="empty">{t('moviesNotFound')}</p>}
        {error && <p className="error">{error}</p>}
      </section>
    </Shell>
  )
}
