import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { addFavorite, createReview, getAuthState, getMovie, type MovieDetail } from '../api'
import Shell from '../components/Shell'
import { translate, useI18n } from '../i18n'
import { haptic } from '../lib/haptic'

export default function MoviePage() {
  const { language, t } = useI18n()
  const { id } = useParams()
  const [movie, setMovie] = useState<MovieDetail | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reviewRating, setReviewRating] = useState(5)
  const [reviewText, setReviewText] = useState('')
  const [reviewBusy, setReviewBusy] = useState(false)

  const loadMovie = useCallback(async () => {
    if (!id) return
    try {
      setMovie(await getMovie(Number(id), language))
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : translate('serverError'))
    }
  }, [id, language])

  useEffect(() => { void loadMovie() }, [loadMovie])

  const saveFavorite = async () => {
    if (!movie) return
    if (!getAuthState().authenticated) {
      setNotice(t('profileTelegramAuthError'))
      return
    }
    try {
      await addFavorite(movie.id)
      setNotice(t('favoriteAdded'))
      haptic.success()
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : t('serverError'))
      haptic.error()
    }
  }

  const submitReview = async () => {
    if (!movie || reviewText.trim().length < 3) return
    if (!getAuthState().authenticated) {
      setNotice(t('profileTelegramAuthError'))
      return
    }
    setReviewBusy(true)
    try {
      await createReview(movie.id, { rating: reviewRating, text: reviewText.trim() })
      setReviewText('')
      setNotice(t('reviewSent'))
      await loadMovie()
      haptic.success()
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : t('serverError'))
      haptic.error()
    } finally {
      setReviewBusy(false)
    }
  }

  if (error) return <Shell><Link className="back" to="/">← {t('back')}</Link><p className="error">{error}</p></Shell>
  if (!movie) return <Shell><div className="hall-skeleton" /></Shell>

  return (
    <Shell>
      <section className="movie-hero" style={{ backgroundImage: `linear-gradient(0deg,#0b0b0b,transparent),url(${movie.poster})` }}>
        <Link className="back" to="/">← {t('back')}</Link>
        <img src={movie.poster} alt={movie.title} />
        <div>
          <p>{movie.genre} · {movie.year} · {movie.country}</p>
          <h1>{movie.title}</h1>
          <div className="detail-stats">
            <span>IMDb ★ {movie.imdb}</span>
            <span>{t('kinopoiskShort')} ★ {movie.kinopoisk}</span>
            <span>Nova ★ {movie.user_rating ?? movie.rating}</span>
            <span>{movie.age}+</span>
            <span>{movie.duration} {t('minutes')}</span>
          </div>
          <Link className="book" to={`/booking/${movie.id}/date`} onClick={haptic.tap}>{t('bookTicket')}</Link>
          <button className="admin-ghost detail-favorite" onClick={() => { void saveFavorite() }}>{t('addToFavorites')}</button>
        </div>
      </section>
      <p className="description">{movie.description}</p>
      <section className="credits">
        <div><small>{t('director')}</small><b>{movie.director}</b></div>
        <div><small>{t('cast')}</small><b>{movie.cast.join(', ')}</b></div>
      </section>
      {movie.trailer_id ? (
        <div className="trailer">
          <iframe src={`https://www.youtube-nocookie.com/embed/${movie.trailer_id}`} title={t('trailer')} loading="lazy" allowFullScreen />
        </div>
      ) : <p className="empty">{t('trailerUnavailable')}</p>}
      {movie.gallery.length > 0 && <div className="gallery">{movie.gallery.map(image => <img key={image} src={image} alt={t('galleryFrame')} loading="lazy" />)}</div>}
      <section className="reviews">
        <h2>{t('reviews')}</h2>
        {movie.reviews.map(review => <article className="review" key={`${review.user_name}-${review.created_at}`}><div><b>{review.user_name}</b><span>★ {review.rating}/5</span></div><p>{review.text}</p><small>{new Date(review.created_at).toLocaleDateString()}</small></article>)}
        {!movie.reviews.length && <p className="empty">{t('noReviews')}</p>}
        <div className="review-form">
          <label>{t('reviewRating')}<select value={reviewRating} onChange={event => setReviewRating(Number(event.target.value))}>{[5, 4, 3, 2, 1].map(value => <option value={value} key={value}>{value}/5</option>)}</select></label>
          <textarea value={reviewText} onChange={event => setReviewText(event.target.value)} placeholder={t('reviewPlaceholder')} maxLength={1000} />
          <button className="book fit" onClick={() => { void submitReview() }} disabled={reviewBusy || reviewText.trim().length < 3}>{t('sendReview')}</button>
        </div>
      </section>
      {movie.similar_movies.length > 0 && <section className="similar"><h2>{t('similarMovies')}</h2><div>{movie.similar_movies.map(item => <Link to={`/movies/${item.id}`} key={item.id}><img src={item.poster} alt={item.title} loading="lazy" /><span>{item.title}</span></Link>)}</div></section>}
      {notice && <p className="toast">{notice}</p>}
    </Shell>
  )
}
