import WebApp from '@twa-dev/sdk'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import Admin from './Admin'
import {
  addFavorite,
  confirmBooking,
  createReview,
  getAuthState,
  getHall,
  getMovie,
  getMovies,
  holdSeats,
  waitForAuth,
  type AuthState,
  type Hall,
  type Movie,
  type MovieDetail,
} from './api'
import { formatDateShort, formatMoney, LanguageProvider, translate, useI18n } from './i18n'
import LanguageSwitcher from './LanguageSwitcher'
import ProfileRoutes from './Profile'

const dates = Array.from({ length: 7 }, (_, index) => {
  const value = new Date()
  value.setDate(value.getDate() + index)
  return value.toISOString().slice(0, 10)
})

const haptic = {
  tap: () => WebApp.HapticFeedback.impactOccurred('light'),
  select: () => WebApp.HapticFeedback.selectionChanged(),
  success: () => WebApp.HapticFeedback.notificationOccurred('success'),
  error: () => WebApp.HapticFeedback.notificationOccurred('error'),
}

const rowLabel = (rowIndex: number) => (
  rowIndex < 26 ? String.fromCharCode(65 + rowIndex) : String(rowIndex + 1)
)

function Shell({ children }: { children: ReactNode }) {
  const { t } = useI18n()

  return (
    <main className="app">
      <header className="topbar">
        <Link className="logo" to="/"><img src="/nova-logo.jpg" alt="Nova Cinema" /><span>NOVA <i>CINEMA</i></span></Link>
        <div className="header-actions">
          <LanguageSwitcher />
          <Link className="admin-ghost" to="/profile">{t('profile')}</Link>
        </div>
      </header>
      {children}
    </main>
  )
}

function TelegramRouteControls() {
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    const onBack = () => { haptic.tap(); navigate(-1) }
    if (location.pathname === '/') WebApp.BackButton.hide()
    else {
      WebApp.BackButton.show()
      WebApp.BackButton.onClick(onBack)
    }
    return () => { WebApp.BackButton.offClick(onBack) }
  }, [location.pathname, navigate])

  return null
}

function ProtectedAdminRoute() {
  const [auth, setAuth] = useState<AuthState>(getAuthState)

  useEffect(() => {
    let active = true
    void waitForAuth().finally(() => {
      if (active) setAuth(getAuthState())
    })
    return () => { active = false }
  }, [])

  if (!auth.ready) return <Shell><div className="hall-skeleton" /></Shell>
  if (!auth.authenticated || !auth.isAdmin) return <Navigate to="/" replace />
  return <Admin />
}

function Home() {
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

function MoviePage() {
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

function DatePage() {
  const { language, t } = useI18n()
  const { id } = useParams()

  return (
    <Shell>
      <Link className="back" to="/">← {t('back')}</Link>
      <h1>{t('chooseDate')}</h1>
      <div className="choice-list">
        {dates.map(date => {
          const index = dates.indexOf(date)
          return <Link key={date} to={`/booking/${id}/date/${date}/time`} className="choice" onClick={haptic.select}>
            <b>{index === 0 ? t('today') : index === 1 ? t('tomorrow') : formatDateShort(date, language)}</b>
            <span>{t('chooseConvenientTime')}</span>
          </Link>
        })}
      </div>
    </Shell>
  )
}

function TimePage() {
  const { t } = useI18n()
  const { id, date } = useParams()
  const [time, setTime] = useState('19:00')
  const valid = /^([01]\d|2[0-3]):[0-5]\d$/.test(time)

  return (
    <Shell>
      <Link className="back" to={`/booking/${id}/date`}>← {t('date')}</Link>
      <h1>{t('chooseConvenientTime')}</h1>
      <div className="manual-time-card">
        <label>
          <span>{t('preferredTime')}</span>
          <input type="time" value={time} onChange={event => setTime(event.target.value)} />
        </label>
        {!valid && <p className="error">{t('invalidTime')}</p>}
        <Link className={`book${valid ? '' : ' disabled-link'}`} to={valid ? `/booking/${id}/date/${date}/time/${time}/hall` : '#'} onClick={event => { if (!valid) event.preventDefault(); else haptic.select() }}>
          {t('continue')}
        </Link>
      </div>
    </Shell>
  )
}

function seatLabel(seat: string) {
  const [row, column] = seat.split('-').map(Number)
  return `${rowLabel(row - 1)}${column}`
}

function HallPage() {
  const { language, t } = useI18n()
  const { id, date, time } = useParams()
  const navigate = useNavigate()
  const [hall, setHall] = useState<Hall | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [contact, setContact] = useState({ first_name: '', last_name: '', phone: '', telegram_username: WebApp.initDataUnsafe.user?.username ?? '', comment: '' })

  const loadHall = useCallback(async () => {
    if (!id || !date || !time) return
    try {
      const nextHall = await getHall(Number(id), date, time)
      setHall(nextHall)
      setSelected(current => current.filter(seat => !nextHall.taken.includes(seat)))
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : translate('failedRefreshHall'))
    }
  }, [date, id, time])

  useEffect(() => {
    void loadHall()
    const intervalId = window.setInterval(() => { void loadHall() }, 15_000)
    return () => window.clearInterval(intervalId)
  }, [loadHall])

  const toggleSeat = (seat: string) => {
    if (hall?.taken.includes(seat)) return
    haptic.select()
    setSelected(current => current.includes(seat) ? current.filter(item => item !== seat) : current.length < 6 ? [...current, seat] : current)
  }

  const reserve = useCallback(async () => {
    if (!id || !date || !time || !selected.length) return
    if (!contact.first_name.trim() || !contact.last_name.trim() || !contact.phone.trim()) {
      setError(t('userInfoRequired'))
      haptic.error()
      return
    }
    setBusy(true)
    setError('')
    try {
      const payload = { movie_id: Number(id), show_date: date, session: time, seats: selected }
      await holdSeats(payload)
      const result = await confirmBooking({ ...payload, ...contact })
      haptic.success()
      navigate(`/booking/success/${result.ticket_code}`)
    } catch (reason) {
      haptic.error()
      setError(reason instanceof Error ? reason.message : t('failedBooking'))
      void loadHall()
    } finally {
      setBusy(false)
    }
  }, [contact, date, id, loadHall, navigate, selected, t, time])

  useEffect(() => {
    if (!hall || !selected.length || busy) {
      WebApp.MainButton.hide()
      return
    }
    WebApp.MainButton.setText(`${t('continue')} · ${formatMoney(selected.length * hall.price, language)}`)
    WebApp.MainButton.show()
    WebApp.MainButton.onClick(reserve)
    return () => {
      WebApp.MainButton.offClick(reserve)
      WebApp.MainButton.hide()
    }
  }, [busy, hall, language, reserve, selected.length, t])

  return (
    <Shell>
      <Link className="back" to={`/booking/${id}/date/${date}/time`}>← {t('sessions')}</Link>
      <section className="hall-page">
        <div className="hall-head">
          <p>NOVA HALL</p>
          <h1>{t('chooseSeats')}</h1>
        </div>
        <div className="legend">
          <span><i /> {t('free')}</span>
          <span><i className="taken" /> {t('taken')}</span>
          <span><i className="selected" /> {t('selected')}</span>
        </div>
        {hall ? (
          <>
            <div className="cinema-screen">
              <span>🎬 {t('screen')}</span>
              <i aria-hidden="true" />
            </div>
            <div className="hall" style={{ ['--seat-count' as string]: String(hall.cols) }}>
              <div className="hall-numbers" aria-hidden="true">
                <span />
                {Array.from({ length: hall.cols }, (_, columnIndex) => (
                  <b key={columnIndex + 1}>{columnIndex + 1}</b>
                ))}
              </div>
              {Array.from({ length: hall.rows }, (_, rowIndex) => (
                <div className="hall-row" key={rowLabel(rowIndex)}>
                  <span className="row-label">{rowLabel(rowIndex)}</span>
                  {Array.from({ length: hall.cols }, (_, columnIndex) => {
                    const seat = `${rowIndex + 1}-${columnIndex + 1}`
                    const taken = hall.taken.includes(seat)
                    const selectedSeat = selected.includes(seat)
                    return (
                      <button
                        key={seat}
                        disabled={taken}
                        onClick={() => toggleSeat(seat)}
                        className={`seat ${taken ? 'taken' : selectedSeat ? 'selected' : ''}`}
                        aria-label={`${t('seats')} ${seatLabel(seat)}`}
                      >
                        {columnIndex + 1}
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
            <div className="contact-form booking-form">
              <input value={contact.first_name} onChange={event => setContact({ ...contact, first_name: event.target.value })} placeholder={t('firstName')} />
              <input value={contact.last_name} onChange={event => setContact({ ...contact, last_name: event.target.value })} placeholder={t('lastName')} />
              <input value={contact.phone} onChange={event => setContact({ ...contact, phone: event.target.value })} placeholder={t('phone')} inputMode="tel" />
              <input value={contact.telegram_username} onChange={event => setContact({ ...contact, telegram_username: event.target.value })} placeholder={t('telegramUsername')} />
              <textarea value={contact.comment} onChange={event => setContact({ ...contact, comment: event.target.value })} placeholder={t('commentOptional')} />
            </div>
            <div className="summary">
              <div>
                <small>{t('selectedSeats')}</small>
                <b>{selected.length ? selected.map(seatLabel).join(', ') : t('noSeatsSelected')}</b>
              </div>
              <strong>{formatMoney(selected.length * hall.price, language)}</strong>
              <button className="book" disabled={!selected.length || busy} onClick={() => void reserve()}>{busy ? t('sendingRequest') : t('continue')}</button>
            </div>
          </>
        ) : <div className="hall-skeleton" />}
        {error && <p className="error">{error}</p>}
      </section>
    </Shell>
  )
}

function Success() {
  const { t } = useI18n()
  const { code } = useParams()
  return (
    <Shell>
      <section className="success">
        <span>✓</span>
        <h1>{t('requestCreated')}</h1>
        <p>{t('requestSentThanks')}</p>
        <b>{t('ticketCode')}: {code}</b>
        <Link className="book" to="/">{t('home')}</Link>
      </section>
    </Shell>
  )
}

export default function App() {
  return (
    <LanguageProvider>
      <BrowserRouter>
        <TelegramRouteControls />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/movies/:id" element={<MoviePage />} />
          <Route path="/admin" element={<ProtectedAdminRoute />} />
          <Route path="/profile/*" element={<ProfileRoutes />} />
          <Route path="/booking/:id/date" element={<DatePage />} />
          <Route path="/booking/:id/date/:date/time" element={<TimePage />} />
          <Route path="/booking/:id/date/:date/time/:time/hall" element={<HallPage />} />
          <Route path="/booking/success/:code" element={<Success />} />
        </Routes>
      </BrowserRouter>
    </LanguageProvider>
  )
}
