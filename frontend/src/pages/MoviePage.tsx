import WebApp from '@twa-dev/sdk'
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError, addFavorite, createReview, getAuthState, getMovie, type MovieDetail } from '../api'
import Icon from '../components/Icon'
import Shell from '../components/Shell'
import { useI18n } from '../i18n'
import { apiMessage } from '../lib/apiMessage'
import { haptic } from '../lib/haptic'

export default function MoviePage() {
  const { language, t } = useI18n()
  const { id } = useParams()
  const [movie, setMovie] = useState<MovieDetail | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reviewRating, setReviewRating] = useState(8)
  const [reviewText, setReviewText] = useState('')
  const [reviewBusy, setReviewBusy] = useState(false)
  const [missing, setMissing] = useState(false)

  const loadMovie = useCallback(async () => {
    if (!id) return
    try {
      setMovie(await getMovie(Number(id), language))
      setError('')
      setMissing(false)
    } catch (reason) {
      // A deleted or unpublished movie, or a stale share link, all arrive as 404.
      if (reason instanceof ApiError && reason.status === 404) {
        setMissing(true)
        return
      }
      setError(apiMessage(reason, 'serverError'))
    }
  }, [id, language])

  useEffect(() => { void loadMovie() }, [loadMovie])

  const share = async () => {
    if (!movie) return
    // Built server-side so the payload format lives in exactly one place.
    const link = movie.share_link
    if (!link) {
      setNotice(t('shareUnavailable'))
      return
    }
    const text = `${movie.title} — ${t('shareText')}`
    haptic.tap()
    if (WebApp.initData) {
      WebApp.openTelegramLink(
        `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`,
      )
      return
    }
    try {
      await navigator.clipboard.writeText(link)
      setNotice(t('linkCopied'))
    } catch {
      setNotice(link)
    }
  }

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
      setNotice(apiMessage(reason, 'serverError'))
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
      setNotice(apiMessage(reason, 'serverError'))
      haptic.error()
    } finally {
      setReviewBusy(false)
    }
  }

  if (missing) {
    return (
      <Shell>
        <section className="unavailable">
          <span aria-hidden="true"><Icon name="film" /></span>
          <h1>{t('movieUnavailable')}</h1>
          <p>{t('movieUnavailableHint')}</p>
          <Link className="book fit" to="/">{t('toCatalog')}</Link>
        </section>
      </Shell>
    )
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
            {!!movie.imdb && <span>IMDb <Icon name="star" /> {movie.imdb}</span>}
            {!!movie.kinopoisk && <span>{t('kinopoiskShort')} <Icon name="star" /> {movie.kinopoisk}</span>}
            {/* Nobody has rated it yet: a Nova score of zero reads as a bad score, not as silence. */}
            {!!(movie.user_rating ?? movie.rating) && (
              <span>Nova <Icon name="star" /> {movie.user_rating ?? movie.rating}</span>
            )}
            <span>{movie.age}+</span>
            <span>{movie.duration} {t('minutes')}</span>
          </div>
          <button className="admin-ghost detail-favorite" onClick={() => { void saveFavorite() }}>{t('addToFavorites')}</button>
          <button className="admin-ghost detail-favorite" onClick={() => { void share() }}><Icon name="share" /> {t('share')}</button>
        </div>
      </section>
      <p className="description">{movie.description}</p>
      <section className="credits">
        {!!movie.director && <div><small>{t('director')}</small><b>{movie.director}</b></div>}
        {!!movie.cast.length && <div><small>{t('cast')}</small><b>{movie.cast.join(', ')}</b></div>}
      </section>
      {movie.trailer_id ? (
        <div className="trailer">
          <iframe src={`https://www.youtube-nocookie.com/embed/${movie.trailer_id}`} title={t('trailer')} loading="lazy" allowFullScreen />
        </div>
      ) : <p className="empty">{t('trailerUnavailable')}</p>}
      {movie.gallery.length > 0 && <div className="gallery">{movie.gallery.map(image => <img key={image} src={image} alt={t('galleryFrame')} loading="lazy" />)}</div>}
      <section className="reviews">
        <h2>{t('reviews')}</h2>
        {movie.reviews.map(review => <article className="review" key={`${review.user_name}-${review.created_at}`}><div><b>{review.user_name}</b><span><Icon name="star" /> {review.rating}/10</span></div><p>{review.text}</p><small>{new Date(review.created_at).toLocaleDateString()}</small></article>)}
        {!movie.reviews.length && <p className="empty">{t('noReviews')}</p>}
        {movie.has_reviewed && <p className="empty">{t('reviewAlreadyLeft')}</p>}
        {!movie.has_reviewed && !movie.can_review && <p className="empty">{t('reviewSignInFirst')}</p>}
        {movie.can_review && !movie.has_reviewed && (
          <div className="review-form">
            <div className="review-rating-label">
              <div className="review-rating-head"><span>{t('reviewRating')}</span><output>{reviewRating}/10</output></div>
              <div className="review-rating-scale" role="group" aria-label={t('reviewRating')}>
                {Array.from({ length: 10 }, (_, index) => index + 1).map(value => (
                  <button
                    type="button"
                    key={value}
                    className={`${value <= reviewRating ? 'filled' : ''}${value === reviewRating ? ' selected' : ''}`.trim()}
                    onClick={() => setReviewRating(value)}
                    aria-label={`${value}/10`}
                    aria-pressed={value === reviewRating}
                    title={`${value}/10`}
                  >
                    <Icon name="star" />
                  </button>
                ))}
              </div>
            </div>
            <textarea value={reviewText} onChange={event => setReviewText(event.target.value)} placeholder={t('reviewPlaceholder')} maxLength={1000} />
            <button className="book fit" onClick={() => { void submitReview() }} disabled={reviewBusy || reviewText.trim().length < 3}><Icon name="star" /> {t('sendReview')}</button>
          </div>
        )}
      </section>
      {movie.similar_movies.length > 0 && <section className="similar"><h2>{t('similarMovies')}</h2><div>{movie.similar_movies.map(item => <Link to={`/movies/${item.id}`} key={item.id}><img src={item.poster} alt={item.title} loading="lazy" /><span>{item.title}</span></Link>)}</div></section>}
      {notice && <p className="toast">{notice}</p>}
    </Shell>
  )
}
