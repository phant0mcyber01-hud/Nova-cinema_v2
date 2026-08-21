import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import {
  decideBooking,
  getAdminBookings,
  getAdminMovies,
  getAdminSessions,
  getBasePrice,
  getDashboard,
  getNotifications,
  isAdmin,
  readNotification,
  setBasePrice,
  setBookingStatus,
  type AdminBooking,
  type AdminSession,
  type MovieDetail,
} from '../../api'
import MoviesView from './AdminMovies'
import SessionsView from './AdminSessions'
import { formatDateTime, formatMoney, translate, useI18n, type TranslationKey } from '../../i18n'

type Tab = 'dashboard' | 'bookings' | 'movies' | 'sessions' | 'notifications' | 'settings'
type DashboardData = Awaited<ReturnType<typeof getDashboard>>
type SortDir = 'asc' | 'desc'

const bookingStatuses = ['pending', 'confirmed', 'cancelled', 'completed']
const tabs: { id: Tab; labelKey: TranslationKey }[] = [
  { id: 'dashboard', labelKey: 'adminDashboard' },
  { id: 'bookings', labelKey: 'adminBookingsTab' },
  { id: 'movies', labelKey: 'adminMoviesTab' },
  { id: 'sessions', labelKey: 'adminSessionsTab' },
  { id: 'notifications', labelKey: 'adminNotificationsTab' },
  { id: 'settings', labelKey: 'adminSettingsTab' },
]
const statusTranslationKeys: Record<string, TranslationKey> = {
  pending: 'statusPending',
  confirmed: 'statusConfirmed',
  cancelled: 'statusCancelled',
  completed: 'statusCompleted',
}

const includes = (source: string, query: string) => source.toLowerCase().includes(query.trim().toLowerCase())
const statusLabel = (status: string, translate: (key: TranslationKey) => string) => (
  statusTranslationKeys[status] ? translate(statusTranslationKeys[status]) : status
)

export default function Admin() {
  const { language, t } = useI18n()
  const [tab, setTab] = useState<Tab>('dashboard')
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [bookings, setBookings] = useState<AdminBooking[]>([])
  const [movies, setMovies] = useState<MovieDetail[]>([])
  const [sessions, setSessions] = useState<AdminSession[]>([])
  const [notices, setNotices] = useState<Awaited<ReturnType<typeof getNotifications>>>([])
  const [basePrice, setBasePriceState] = useState(30000)
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const [dashboardData, bookingData, movieData, sessionData, notificationData, priceData] = await Promise.all([
        getDashboard(),
        getAdminBookings(),
        getAdminMovies(language),
        getAdminSessions(),
        getNotifications(),
        getBasePrice(),
      ])
      setDashboard(dashboardData)
      setBookings(bookingData)
      setMovies(movieData)
      setSessions(sessionData)
      setNotices(notificationData)
      setBasePriceState(priceData.base_ticket_price)
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : translate('adminLoadFailed'))
    } finally {
      setLoading(false)
    }
  }, [language])

  useEffect(() => {
    void load()
    const intervalId = window.setInterval(() => { void load() }, 30_000)
    return () => window.clearInterval(intervalId)
  }, [load])

  const refresh = useCallback(async (message: string) => {
    await load()
    setToast(message)
    window.setTimeout(() => setToast(''), 2500)
  }, [load])

  if (!isAdmin()) return <Navigate to="/" replace />

  return (
    <main className="app admin">
      <header className="topbar admin-topbar">
        <Link className="logo" to="/"><img src="/nova-logo.jpg" alt="Nova Cinema" /><span>NOVA <i>CINEMA</i></span></Link>
        <b>{t('admin')}</b>
      </header>
      <nav className="admin-nav">{tabs.map(item => <button className={tab === item.id ? 'active' : ''} onClick={() => setTab(item.id)} key={item.id}>{t(item.labelKey)}</button>)}</nav>
      {toast && <p className="toast">{toast}</p>}
      {error && <p className="error">{error}</p>}
      {loading && <div className="hall-skeleton" />}
      {!loading && tab === 'dashboard' && dashboard && <DashboardView data={dashboard} />}
      {!loading && tab === 'bookings' && <BookingsView bookings={bookings} onStatus={async (id, status) => { try { await setBookingStatus(id, status); await refresh(t('adminBookingStatusUpdated')) } catch (reason) { setError(reason instanceof Error ? reason.message : t('serverError')) } }} onDecision={async (id, payload) => { try { await decideBooking(id, payload); await refresh(t('adminBookingStatusUpdated')) } catch (reason) { setError(reason instanceof Error ? reason.message : t('serverError')) } }} />}
      {!loading && tab === 'movies' && <MoviesView movies={movies} onSaved={refresh} />}
      {!loading && tab === 'sessions' && <SessionsView movies={movies} sessions={sessions} onSaved={refresh} />}
      {!loading && tab === 'notifications' && <NotificationsView notices={notices} onRead={async id => { try { await readNotification(id); await refresh(t('adminNotificationReadToast')) } catch (reason) { setError(reason instanceof Error ? reason.message : t('serverError')) } }} />}
      {!loading && tab === 'settings' && <SettingsView basePrice={basePrice} onSaved={async price => { try { await setBasePrice(price); await refresh(t('adminBasePriceSaved')) } catch (reason) { setError(reason instanceof Error ? reason.message : t('serverError')) } }} />}
    </main>
  )
}

function DashboardView({ data }: { data: DashboardData }) {
  const { language, t } = useI18n()
  const cards = [
    [t('movies'), data.movies],
    [t('sessions'), data.active_sessions],
    [t('bookingRequests'), data.bookings],
    [t('statusPending'), data.statuses.pending],
    [t('statusConfirmed'), data.statuses.confirmed],
    [t('statusCancelled'), data.statuses.cancelled],
    [t('statusCompleted'), data.statuses.completed],
    [t('potentialIncome'), formatMoney(data.potential_income, language)],
  ]
  return (
    <section>
      <h1>{t('adminDashboard')}</h1>
      <div className="admin-cards">{cards.map(([name, value]) => <article key={String(name)}><small>{name}</small><b>{value}</b></article>)}</div>
      <h2>{t('latestBookings')}</h2>
      <div className="admin-table compact">
        {data.recent_bookings.map(item => <article key={item.id}><b>#{item.id} {item.name || t('client')}</b><span>{item.phone} · {statusLabel(item.status, t)} · {formatMoney(item.total, language)}</span></article>)}
        {!data.recent_bookings.length && <p className="empty">{t('noBookings')}</p>}
      </div>
      <h2>{t('latestNotifications')}</h2>
      <div className="admin-table compact">
        {data.notifications.map(item => <article key={item.id}><b>{item.is_read ? t('read') : t('newNotice')}</b><span>{item.message}</span></article>)}
        {!data.notifications.length && <p className="empty">{t('noNotifications')}</p>}
      </div>
    </section>
  )
}

function BookingsView({ bookings, onStatus, onDecision }: { bookings: AdminBooking[]; onStatus: (id: number, status: string) => Promise<void>; onDecision: (id: number, payload: { action: 'confirm' | 'decline' | 'propose'; reason?: string; proposed_session?: string }) => Promise<void> }) {
  const { language, t } = useI18n()
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState<keyof AdminBooking>('id')
  const [dir, setDir] = useState<SortDir>('desc')
  const [page, setPage] = useState(1)
  const rows = useMemo(() => {
    const filtered = bookings.filter(item => (!status || item.status === status) && includes(`${item.id} ${item.name} ${item.phone} ${item.movie} ${item.comment}`, query))
    return [...filtered].sort((a, b) => {
      const left = String(a[sort])
      const right = String(b[sort])
      return dir === 'asc' ? left.localeCompare(right, language) : right.localeCompare(left, language)
    })
  }, [bookings, dir, language, query, sort, status])
  const pageRows = rows.slice((page - 1) * 8, page * 8)
  const pages = Math.max(1, Math.ceil(rows.length / 8))
  const changeStatus = async (id: number, next: string) => {
    if (!window.confirm(`${t('changeBookingStatusConfirm')} #${id}: ${statusLabel(next, t)}?`)) return
    await onStatus(id, next)
  }
  const confirmBooking = async (id: number) => {
    if (!window.confirm(`${t('confirmBookingPrompt')} #${id}?`)) return
    await onDecision(id, { action: 'confirm' })
  }
  const declineBooking = async (id: number) => {
    const reason = window.prompt(t('declineReasonPrompt'))
    if (reason === null) return
    await onDecision(id, { action: 'decline', reason })
  }
  const proposeTime = async (id: number) => {
    const proposed_session = window.prompt(t('proposeTimePrompt'), '19:00')
    if (!proposed_session) return
    const reason = window.prompt(t('proposalCommentPrompt')) ?? ''
    await onDecision(id, { action: 'propose', proposed_session, reason })
  }
  return (
    <section>
      <h1>{t('bookingRequests')}</h1>
      <div className="admin-toolbar">
        <input className="admin-input" value={query} onChange={event => { setQuery(event.target.value); setPage(1) }} placeholder={t('bookingSearchPlaceholder')} />
        <select className="admin-input" value={status} onChange={event => { setStatus(event.target.value); setPage(1) }}><option value="">{t('allStatuses')}</option>{bookingStatuses.map(item => <option value={item} key={item}>{statusLabel(item, t)}</option>)}</select>
        <select className="admin-input" value={sort} onChange={event => setSort(event.target.value as keyof AdminBooking)}><option value="id">ID</option><option value="movie">{t('movies')}</option><option value="show_date">{t('date')}</option><option value="status">{t('statuses')}</option><option value="total">{t('amount')}</option></select>
        <button className="admin-ghost" onClick={() => setDir(dir === 'asc' ? 'desc' : 'asc')}>{dir === 'asc' ? '↑' : '↓'}</button>
      </div>
      <div className="admin-table">
        {pageRows.map(item => (
          <article className="admin-row booking-admin-card" key={item.id}>
            <img src={item.poster} alt={item.movie} loading="lazy" />
            <div className="booking-admin-meta">
              <b>#{item.id} · {item.movie}</b>
              <span>{item.name || t('client')} · {item.phone}</span>
              <span>{item.show_date} {item.session}</span>
              {item.proposed_session && <span>{t('proposedTime')}: {item.proposed_session}</span>}
              <span>{t('seats')} {item.seats} · {formatMoney(item.total, language)}</span>
              <span>Telegram: {item.telegram_username ? `@${item.telegram_username}` : t('notSet')}</span>
              <span>{t('comment')}: {item.comment || t('none')}</span>
              {item.admin_note && <span>{t('adminComment')}: {item.admin_note}</span>}
            </div>
            <div className="admin-actions booking-admin-actions">
              <select value={item.status} onChange={event => { void changeStatus(item.id, event.target.value) }}>{bookingStatuses.map(value => <option value={value} key={value}>{statusLabel(value, t)}</option>)}</select>
              <button className="admin-ghost" onClick={() => { void confirmBooking(item.id) }}>{t('confirmBooking')}</button>
              <button className="admin-ghost" onClick={() => { void proposeTime(item.id) }}>{t('proposeTime')}</button>
              <button className="admin-ghost danger" onClick={() => { void declineBooking(item.id) }}>{t('declineBooking')}</button>
              <a className="admin-ghost" href={`tel:${item.phone}`}>{t('call')}</a>
              {item.chat_url && <a className="admin-ghost" href={item.chat_url} target="_blank" rel="noreferrer">{t('openChat')}</a>}
            </div>
          </article>
        ))}
        {!pageRows.length && <p className="empty">{t('moviesNotFound')}</p>}
      </div>
      <div className="pagination"><button disabled={page <= 1} onClick={() => setPage(page - 1)}>{t('previousPage')}</button><span>{page} / {pages}</span><button disabled={page >= pages} onClick={() => setPage(page + 1)}>{t('nextPage')}</button></div>
    </section>
  )
}

function NotificationsView({ notices, onRead }: { notices: Awaited<ReturnType<typeof getNotifications>>; onRead: (id: number) => Promise<void> }) {
  const { language, t } = useI18n()
  const [filter, setFilter] = useState('')
  const rows = useMemo(() => notices.filter(item => !filter || (filter === 'read' ? item.is_read : !item.is_read)), [filter, notices])
  return <section><h1>{t('notifications')}</h1><select className="admin-input" value={filter} onChange={event => setFilter(event.target.value)}><option value="">{t('all')}</option><option value="new">{t('unread')}</option><option value="read">{t('read')}</option></select><div className="admin-table">{rows.map(item => <article key={item.id}><b>{item.is_read ? t('read') : t('bookingRequests')} · #{item.booking_id}</b><span>{item.message}</span><span>{formatDateTime(item.created_at, language)}</span>{!item.is_read && <button className="book fit" onClick={() => { void onRead(item.id) }}>{t('markRead')}</button>}</article>)}{!rows.length && <p className="empty">{t('notificationsNone')}</p>}</div></section>
}

function SettingsView({ basePrice, onSaved }: { basePrice: number; onSaved: (price: number) => Promise<void> }) {
  const { language, t } = useI18n()
  const [price, setPrice] = useState(String(basePrice))
  useEffect(() => setPrice(String(basePrice)), [basePrice])
  return <section><h1>{t('adminSettingsTab')}</h1><div className="admin-setting"><small>{t('currentBasePrice')}</small><b>{formatMoney(basePrice, language)}</b><input value={price} onChange={event => setPrice(event.target.value)} inputMode="numeric" /><button className="book fit" onClick={() => { void onSaved(Number(price)) }}>{t('savePrice')}</button></div></section>
}
