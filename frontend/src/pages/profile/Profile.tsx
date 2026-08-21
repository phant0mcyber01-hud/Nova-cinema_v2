import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, Route, Routes, useParams } from 'react-router-dom'
import {
  getAuthState,
  getFavorites,
  getProfile,
  getProfileBooking,
  getProfileBookings,
  getProfileNotifications,
  answerBookingProposal,
  isAdmin,
  readProfileNotification,
  removeFavorite,
  updateProfile,
  waitForAuth,
  type Movie,
  type Profile,
  type ProfileBooking,
} from '../../api'
import { formatDateTime, formatMoney, translate, useI18n, type TranslationKey } from '../../i18n'
import LanguageSwitcher from '../../components/LanguageSwitcher'

const statuses = ['pending', 'confirmed', 'cancelled', 'completed']

const statusTranslationKeys: Record<string, TranslationKey> = {
  pending: 'statusPending',
  confirmed: 'statusConfirmed',
  cancelled: 'statusCancelled',
  completed: 'statusCompleted',
}

const statusLabel = (status: string, translate: (key: TranslationKey) => string) => (
  statusTranslationKeys[status] ? translate(statusTranslationKeys[status]) : status
)

const resolveProfileError = (reason: unknown) => {
  if (reason instanceof Error && reason.message) return reason.message
  return getAuthState().authenticated ? translate('failedLoadProfile') : translate('profileTelegramAuthError')
}

function Box({ children }: { children: ReactNode }) {
  const { t } = useI18n()

  return (
    <main className="app profile">
      <header className="topbar">
        <Link className="logo" to="/">
          <img src="/nova-logo.jpg" alt="Nova Cinema" />
          <span>NOVA <i>CINEMA</i></span>
        </Link>
        <div className="header-actions">
          <LanguageSwitcher />
          <Link className="admin-ghost" to="/">{t('movies')}</Link>
        </div>
      </header>
      {children}
    </main>
  )
}

export default function ProfileRoutes() {
  return (
    <Routes>
      <Route path="/" element={<ProfileHome />} />
      <Route path="/bookings" element={<Bookings />} />
      <Route path="/bookings/:id" element={<BookingDetail />} />
      <Route path="/favorites" element={<Favorites />} />
      <Route path="/notifications" element={<Notifications />} />
    </Routes>
  )
}

function ProfileHome() {
  const { t } = useI18n()
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let active = true
    void waitForAuth()
      .then(getProfile)
      .then(data => {
        if (active) setProfile(data)
      })
      .catch(reason => {
        if (active) setError(resolveProfileError(reason))
      })
    return () => { active = false }
  }, [])

  const save = async () => {
    if (!profile) return
    try {
      await updateProfile(profile)
      setMessage(t('profileSaved'))
      window.setTimeout(() => setMessage(''), 2500)
    } catch (reason) {
      setError(resolveProfileError(reason))
    }
  }

  if (error) return <Box><p className="error">{error}</p></Box>
  if (!profile) return <Box><div className="hall-skeleton compact" /></Box>

  return (
    <Box>
      <section className="profile-hero compact-profile">
        <div>
          <p>{t('personalAccount')}</p>
          <h1>{profile.first_name || t('guest')} {profile.last_name}</h1>
          <span>{t('telegramId')}: {profile.telegram_id}</span>
        </div>
        <b>{profile.bookings}</b>
        <small>{t('bookingsCount')}</small>
      </section>

      <div className="profile-grid">
        <section className="profile-card">
          <h2>{t('contacts')}</h2>
          <div className="compact-form">
            <input value={profile.first_name} onChange={event => setProfile({ ...profile, first_name: event.target.value })} placeholder={t('firstName')} />
            <input value={profile.last_name} onChange={event => setProfile({ ...profile, last_name: event.target.value })} placeholder={t('lastName')} />
            <input value={profile.phone} onChange={event => setProfile({ ...profile, phone: event.target.value })} placeholder={t('phone')} inputMode="tel" />
            <button className="book" onClick={() => { void save() }}>{t('save')}</button>
          </div>
          {message && <p className="toast">{message}</p>}
        </section>

        <nav className="profile-menu">
          <Link className="choice" to="/profile/bookings"><b>{t('bookings')}</b><span>{profile.bookings}</span></Link>
          <Link className="choice" to="/profile/favorites"><b>{t('favorites')}</b><span>{t('movies')}</span></Link>
          <Link className="choice" to="/profile/notifications"><b>{t('notifications')}</b><span>{t('statuses')}</span></Link>
          {isAdmin() && (
            <Link className="choice admin-management-card" to="/admin">
              <span className="admin-menu-icon">⚙</span>
              <div><b>{t('adminPanel')}</b><span>{t('adminPanelHint')}</span></div>
              <strong>→</strong>
            </Link>
          )}
        </nav>
      </div>
    </Box>
  )
}

function Bookings() {
  const { language, t } = useI18n()
  const [list, setList] = useState<ProfileBooking[]>([])
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState<'date' | 'movie' | 'status'>('date')
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void waitForAuth()
      .then(() => getProfileBookings(language))
      .then(data => {
        if (active) setList(data)
      })
      .catch(reason => {
        if (active) setError(resolveProfileError(reason))
      })
    return () => { active = false }
  }, [language])

  const rows = useMemo(() => {
    const filtered = list.filter(item => item.movie.toLowerCase().includes(query.toLowerCase()) && (!status || item.status === status))
    return [...filtered].sort((left, right) => {
      if (sort === 'movie') return left.movie.localeCompare(right.movie, language)
      if (sort === 'status') return left.status.localeCompare(right.status, language)
      return `${right.show_date} ${right.session}`.localeCompare(`${left.show_date} ${left.session}`)
    })
  }, [language, list, query, sort, status])

  return (
    <Box>
      <Link className="back" to="/profile">← {t('profile')}</Link>
      <h1>{t('bookingsHistory')}</h1>
      <div className="profile-filters">
        <input className="admin-input" value={query} onChange={event => setQuery(event.target.value)} placeholder={t('searchByMovie')} />
        <select className="admin-input" value={status} onChange={event => setStatus(event.target.value)}>
          <option value="">{t('allStatuses')}</option>
          {statuses.map(item => <option value={item} key={item}>{statusLabel(item, t)}</option>)}
        </select>
        <select className="admin-input" value={sort} onChange={event => setSort(event.target.value as typeof sort)}>
          <option value="date">{t('sortByDate')}</option>
          <option value="movie">{t('sortByMovie')}</option>
          <option value="status">{t('sortByStatus')}</option>
        </select>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="admin-table">
        {rows.map(item => (
          <Link className="booking-card" to={`/profile/bookings/${item.id}`} key={item.id}>
            <img src={item.poster} alt="" loading="lazy" />
            <div>
              <b>{item.movie}</b>
              <span>{item.show_date} · {item.session} · {item.seats}</span>
              <span>{formatMoney(item.total, language)} · {statusLabel(item.status, t)}</span>
              {item.comment && <span>{item.comment}</span>}
            </div>
          </Link>
        ))}
        {!rows.length && !error && <p className="empty">{t('noBookings')}</p>}
      </div>
    </Box>
  )
}

function BookingDetail() {
  const { language, t } = useI18n()
  const { id } = useParams()
  const [booking, setBooking] = useState<ProfileBooking | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let active = true
    if (!id) return () => { active = false }
    void waitForAuth()
      .then(() => getProfileBooking(id, language))
      .then(data => {
        if (active) setBooking(data)
      })
      .catch(reason => {
        if (active) setError(resolveProfileError(reason))
      })
    return () => { active = false }
  }, [id, language])

  const answerProposal = async (action: 'accept' | 'decline') => {
    if (!booking) return
    try {
      await answerBookingProposal(booking.id, action)
      setBooking(await getProfileBooking(String(booking.id), language))
      setMessage(action === 'accept' ? t('proposalAccepted') : t('proposalDeclined'))
    } catch (reason) {
      setError(resolveProfileError(reason))
    }
  }

  if (error) return <Box><p className="error">{error}</p></Box>
  if (!booking) return <Box><div className="hall-skeleton compact" /></Box>

  return (
    <Box>
      <Link className="back" to="/profile/bookings">← {t('bookings')}</Link>
      <img className="detail-poster" src={booking.poster} alt={booking.movie} loading="lazy" />
      <h1>{booking.movie}</h1>
      <p>{booking.description}</p>
      <div className="detail-stats">
        <span>{booking.show_date} · {booking.session}</span>
        {booking.proposed_session && <span>{t('proposedTime')}: {booking.proposed_session}</span>}
        <span>{t('seats')} {booking.seats}</span>
        <span>{formatMoney(booking.total, language)}</span>
        <span>{statusLabel(booking.status, t)}</span>
      </div>
      {booking.proposed_session && (
        <div className="proposal-card">
          <b>{t('newTimeProposal')}</b>
          <span>{booking.proposed_session}</span>
          {booking.admin_note && <p>{booking.admin_note}</p>}
          <div>
            <button className="book fit" onClick={() => { void answerProposal('accept') }}>{t('acceptProposal')}</button>
            <button className="admin-ghost danger" onClick={() => { void answerProposal('decline') }}>{t('declineProposal')}</button>
          </div>
        </div>
      )}
      {message && <p className="toast">{message}</p>}
      <div className={`qr ${booking.qr_valid ? 'valid' : 'invalid'}`}>
        <b>{booking.qr_valid ? t('bookingQrValid') : t('bookingQrInvalid')}</b>
        <code>{booking.qr_token}</code>
      </div>
      <p>
        {t('phone')}: {booking.phone}<br />
        {t('telegram')}: {booking.telegram_username ? `@${booking.telegram_username}` : t('notSet')}<br />
        {t('comment')}: {booking.comment || t('none')}
      </p>
      <div className="trailer"><iframe src={`https://www.youtube-nocookie.com/embed/${booking.trailer_id}`} title={t('trailer')} loading="lazy" /></div>
    </Box>
  )
}

function Favorites() {
  const { language, t } = useI18n()
  const [list, setList] = useState<Movie[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void waitForAuth()
      .then(() => getFavorites(language))
      .then(data => {
        if (active) setList(data)
      })
      .catch(reason => {
        if (active) setError(resolveProfileError(reason))
      })
    return () => { active = false }
  }, [language])

  const onRemove = useCallback(async (movieId: number) => {
    try {
      await removeFavorite(movieId)
      setList(current => current.filter(movie => movie.id !== movieId))
    } catch (reason) {
      setError(resolveProfileError(reason))
    }
  }, [])

  return (
    <Box>
      <Link className="back" to="/profile">← {t('profile')}</Link>
      <h1>{t('favorites')}</h1>
      {error && <p className="error">{error}</p>}
      <div className="catalog">
        {list.map(item => (
          <article className="movie" key={item.id}>
            <Link className="movie-link" to={`/movies/${item.id}`}>
              <img src={item.poster} alt={item.title} loading="lazy" />
              <div className="movie-body"><h2>{item.title}</h2></div>
            </Link>
            <button className="book movie-book" onClick={() => { void onRemove(item.id) }}>{t('remove')}</button>
          </article>
        ))}
        {!list.length && !error && <p className="empty">{t('noFavorites')}</p>}
      </div>
    </Box>
  )
}

function Notifications() {
  const { language, t } = useI18n()
  const [list, setList] = useState<Awaited<ReturnType<typeof getProfileNotifications>>>([])
  const [filter, setFilter] = useState<'all' | 'unread'>('all')
  const [error, setError] = useState('')

  const load = useCallback(() => {
    void waitForAuth()
      .then(getProfileNotifications)
      .then(setList)
      .catch(reason => setError(resolveProfileError(reason)))
  }, [])

  useEffect(() => {
    load()
    const intervalId = window.setInterval(load, 30_000)
    return () => window.clearInterval(intervalId)
  }, [load])

  const rows = useMemo(() => list.filter(item => filter === 'all' || !item.is_read), [filter, list])

  return (
    <Box>
      <Link className="back" to="/profile">← {t('profile')}</Link>
      <h1>{t('notifications')}</h1>
      <div className="profile-filters">
        <button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>{t('all')}</button>
        <button className={filter === 'unread' ? 'active' : ''} onClick={() => setFilter('unread')}>{t('unread')}</button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="admin-table">
        {rows.map(item => (
          <article className={item.is_read ? 'notice read' : 'notice'} key={item.id}>
            <b>{item.title}</b>
            <span>{item.message}</span>
            <small>{formatDateTime(item.created_at, language)}</small>
            {!item.is_read && <button className="book fit" onClick={() => { void readProfileNotification(item.id).then(load).catch(reason => setError(resolveProfileError(reason))) }}>{t('read')}</button>}
          </article>
        ))}
        {!rows.length && !error && <p className="empty">{t('noNotifications')}</p>}
      </div>
    </Box>
  )
}
