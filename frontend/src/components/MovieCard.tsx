import { Link } from 'react-router-dom'

import type { Movie } from '../api'
import { useI18n } from '../i18n'

/** Catalog tile shared by the poster grid and any filtered list. */
export default function MovieCard({ movie }: { movie: Movie }) {
  const { t } = useI18n()

  return (
    <article className="movie">
      <Link className="movie-link" to={`/movies/${movie.id}`}>
        <img src={movie.poster} alt={movie.title} loading="lazy" />
        <div className="movie-shade" />
        {movie.is_new && <span className="new-badge">{t('newBadge')}</span>}
        <div className="movie-body">
          <span className="rating-chip">IMDb {movie.imdb} · {t('kinopoiskShort')} {movie.kinopoisk}</span>
          <h2>{movie.title}</h2>
          <p>{movie.genre} · {movie.age}+ · {movie.duration} {t('minutes')}</p>
        </div>
      </Link>
    </article>
  )
}
