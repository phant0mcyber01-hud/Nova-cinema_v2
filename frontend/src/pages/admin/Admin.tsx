import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'

import {
  decideBooking,
  getAdminBonuses,
  getAdminBookings,
  getAdminGallery,
  getAdminMovies,
  getAdminReviews,
  getAdminSlots,
  getAdminSettings,
  getDashboard,
  isAdmin,
  setBasePrice,
  setBookingStatus,
  type AdminBonus,
  type AdminBooking,
  type AdminGalleryImage,
  type AdminReview,
  type AdminSlot,
  type AdminSettings,
  type MovieDetail,
} from '../../api'
import BottomNav from '../../components/BottomNav'
import { formatDateTime, formatMoney, translate, useI18n, type TranslationKey } from '../../i18n'
import BonusesView from './AdminBonuses'
import CinemaSettingsView from './AdminCinemaSettings'
import GalleryView from './AdminGallery'
import MoviesView from './AdminMovies'
import NewReleasesView from './AdminNewReleases'
import PriceView from './AdminPrice'
import ReviewsView from './AdminReviews'
import SlotsView from './AdminSessions'

type Tab =
  | 'dashboard' | 'bookings' | 'movies' | 'new' | 'sessions'
  | 'price' | 'bonuses' | 'gallery' | 'cinema' | 'reviews'
type DashboardData = Awaited<ReturnType<typeof getDashboard>>
type SortDir = 'asc' | 'desc'
type DecisionPayload = {
  action: 'contact' | 'confirm' | 'decline' | 'propose'
  reason?: string
  proposed_session?: string
}
const PAGE_SIZE = 8
const REFRESH_INTERVAL_MS = 30_000

const bookingStatuses = ['pending', 'contacting', 'confirmed', 'cancelled', 'watched']
const tabs: { id: Tab; labelKey: TranslationKey }[] = [
  { id: 'dashboard', labelKey: 'adminDashboard' },
  { id: 'bookings', labelKey: 'adminBookingsTab' },
  { id: 'movies', labelKey: 'adminMoviesTab' },
  { id: 'new', labelKey: 'adminNewTab' },
  { id: 'sessions', labelKey: 'adminSessionsTab' },
  { id: 'price', labelKey: 'adminPriceTab' },
  { id: 'bonuses', labelKey: 'adminBonusesTab' },
  { id: 'gallery', labelKey: 'adminGalleryTab' },
  { id: 'cinema', labelKey: 'adminCinemaTab' },
  { id: 'reviews', labelKey: 'adminReviewsTab' },
]
const statusTranslationKeys: Record<string, TranslationKey> = {
  pending: 'statusPending',
  contacting: 'statusContacting',
  confirmed: 'statusConfirmed',
  cancelled: 'statusCancelled',
  watched: 'statusWatched',
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
  const [slots, setSlots] = useState<AdminSlot[]>([])
  const [settings, setSettings] = useState<AdminSettings | null>(null)
  const [bonuses, setBonuses] = useState<AdminBonus[]>([])
  const [images, setImages] = useState<AdminGalleryImage[]>([])
  const [reviews, setReviews] = useState<AdminReview[]>([])
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const [
        dashboardData, bookingData, movieData, slotData,
        settingsData, bonusData, reviewData, galleryData,
      ] = await Promise.all([
        getDashboard(),
        getAdminBookings(),
        getAdminMovies(language),
        getAdminSlots(),
        getAdminSettings(),
        getAdminBonuses(),
        getAdminReviews(),
        getAdminGallery(),
      ])
      setDashboard(dashboardData)
      setBookings(bookingData)
      setMovies(movieData)
      setSlots(slotData)
      setSettings(settingsData)
      setBonuses(bonusData)
      setReviews(reviewData)
      setImages(galleryData)
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : translate('adminLoadFailed'))
    } finally {
      setLoading(false)
    }
  }, [language])

  useEffect(() => {
    void load()
    const intervalId = window.setInterval(() => { void load() }, REFRESH_INTERVAL_MS)
    return () => window.clearInterval(intervalId)
  }, [load])

  const refresh = useCallback(async (message: string) => {
    await load()
    setToast(message)
    window.setTimeout(() => setToast(''), 2500)
  }, [load])

  const guard = useCallback(async (action: () => Promise<unknown>, message: string) => {
    try {
      await action()
      await refresh(message)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : translate('serverError'))
    }
  }, [refresh])

  if (!isAdmin()) return <Navigate to="/" replace />

  return (
    <main className="app admin">
      <header className="topbar admin-topbar">
        <Link className="logo" to="/">
          <img src="/nova-logo.jpg" alt="Nova Cinema" />
          <span>NOVA <i>CINEMA</i></span>
        </Link>
        <b>{t('admin')}</b>
      </header>
      <nav className="admin-nav">
        {tabs.map(item => (
          <button className={tab === item.id ? 'active' : ''} onClick={() => setTab(item.id)} key={item.id}>
            {t(item.labelKey)}
          </button>
        ))}
      </nav>
      {toast && <p className="toast">{toast}</p>}
      {error && <p className="error">{error}</p>}
      {loading && <div className="hall-skeleton" />}

      {!loading && tab === 'dashboard' && dashboard && <DashboardView data={dashboard} />}
      {!loading && tab === 'bookings' && (
        <BookingsView
          bookings={bookings}
          onStatus={(id, status) => guard(() => setBookingStatus(id, status), t('adminBookingStatusUpdated'))}
          onDecision={(id, payload) => guard(() => decideBooking(id, payload), t('adminBookingStatusUpdated'))}
        />
      )}
      {!loading && tab === 'movies' && <MoviesView movies={movies} onSaved={refresh} />}
      {!loading && tab === 'new' && <NewReleasesView movies={movies} onSaved={refresh} />}
      {!loading && tab === 'sessions' && <SlotsView slots={slots} onSaved={refresh} />}
      {!loading && tab === 'price' && settings && (
        <PriceView
          settings={settings}
          onSave={price => guard(() => setBasePrice(price), t('adminBasePriceSaved'))}
        />
      )}
      {!loading && tab === 'bonuses' && <BonusesView bonuses={bonuses} onSaved={refresh} />}
      {!loading && tab === 'gallery' && <GalleryView images={images} onSaved={refresh} />}
      {!loading && tab === 'cinema' && settings && <CinemaSettingsView settings={settings} onSaved={refresh} />}
      {!loading && tab === 'reviews' && <ReviewsView reviews={reviews} onSaved={refresh} />}
      {/* The panel builds its own frame instead of using <Shell>, so it has to
          render the app-wide tab bar itself — without it the viewer tabs
          disappeared on entering the admin panel. The `admin-nav` above is a
          different thing: it switches sections inside the panel. */}
      <BottomNav />
    </main>
  )
}

function DashboardView({ data }: { data: DashboardData }) {
  const { language, t } = useI18n()
  const cards: [string, string | number][] = [
    [t('newRequests'), data.statuses.pending ?? 0],
    [t('statusPending'), data.statuses.pending ?? 0],
    [t('statusContacting'), data.statuses.contacting ?? 0],
    [t('statusConfirmed'), data.statuses.confirmed ?? 0],
    [t('statusCancelled'), data.statuses.cancelled ?? 0],
    [t('statusWatched'), data.statuses.watched ?? 0],
    [t('movies'), data.movies],

    [t('bookingRequests'), data.bookings],
  ]
  return (
    <section>
      <h1>{t('adminDashboard')}</h1>
      <div className="admin-cards">
        {cards.map(([name, value]) => <article key={name}><small>{name}</small><b>{value}</b></article>)}
      </div>
      <h2>{t('latestBookings')}</h2>
      <div className="admin-table compact">
        {data.recent_bookings.map(item => (
          <article key={item.id}>
            <b>#{item.id} {item.name || t('client')}</b>
            <span>{item.phone} · {statusLabel(item.status, t)} · {formatMoney(item.total, language)}</span>
          </article>
        ))}
        {!data.recent_bookings.length && <p className="empty">{t('noBookings')}</p>}
      </div>
    </section>
  )
}
type BookingsViewProps = {
  bookings: AdminBooking[]
  onStatus: (id: number, status: string) => Promise<void>
  onDecision: (id: number, payload: DecisionPayload) => Promise<void>
}

function BookingsView({ bookings, onStatus, onDecision }: BookingsViewProps) {
  const { language, t } = useI18n()
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState<keyof AdminBooking>('id')
  const [dir, setDir] = useState<SortDir>('desc')
  const [page, setPage] = useState(1)

  const rows = useMemo(() => {
    const filtered = bookings.filter(item => (
      (!status || item.status === status)
      && includes(`${item.id} ${item.name} ${item.phone} ${item.movie} ${item.comment} ${item.telegram_username}`, query)
    ))
    return [...filtered].sort((a, b) => {
      const left = String(a[sort])
      const right = String(b[sort])
      return dir === 'asc' ? left.localeCompare(right, language) : right.localeCompare(left, language)
    })
  }, [bookings, dir, language, query, sort, status])

  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))

  const changeStatus = async (id: number, next: string) => {
    if (!window.confirm(`${t('changeBookingStatusConfirm')} #${id}: ${statusLabel(next, t)}?`)) return
    await onStatus(id, next)
  }
  const startProcessing = async (id: number) => {
    if (!window.confirm(`${t('startProcessingPrompt')} #${id}?`)) return
    await onDecision(id, { action: 'contact' })
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
        <input
          className="admin-input"
          value={query}
          onChange={event => { setQuery(event.target.value); setPage(1) }}
          placeholder={t('bookingSearchPlaceholder')}
        />
        <select
          className="admin-input"
          value={status}
          onChange={event => { setStatus(event.target.value); setPage(1) }}
        >
          <option value="">{t('allStatuses')}</option>
          {bookingStatuses.map(item => <option value={item} key={item}>{statusLabel(item, t)}</option>)}
        </select>
        <select className="admin-input" value={sort} onChange={event => setSort(event.target.value as keyof AdminBooking)}>
          <option value="id">ID</option>
          <option value="created_at">{t('createdAt')}</option>
          <option value="movie">{t('movies')}</option>
          <option value="show_date">{t('date')}</option>
          <option value="status">{t('statuses')}</option>
          <option value="total">{t('amount')}</option>
        </select>
        <button className="admin-ghost" onClick={() => setDir(dir === 'asc' ? 'desc' : 'asc')}>
          {dir === 'asc' ? '↑' : '↓'}
        </button>
      </div>
      <div className="admin-table">
        {pageRows.map(item => (
          <article className="admin-row booking-admin-card" key={item.id}>
            {item.poster && <img src={item.poster} alt={item.movie ?? ''} loading="lazy" />}
            <div className="booking-admin-meta">
              <b>#{item.id}{item.movie ? ` · ${item.movie}` : ''}</b>
              <span className={`status-chip ${item.status === 'cancelled' ? 'muted' : 'live'}`}>
                {statusLabel(item.status, t)}
              </span>
              <span>{item.name || t('client')} · {item.phone}</span>
              <span>{item.show_date} {item.session}</span>
              {item.proposed_session && <span>{t('proposedTime')}: {item.proposed_session}</span>}
              <span>{language === 'ru' ? 'Гостей' : 'Mehmonlar'}: {item.party_size ?? item.seats_count ?? 0} · {formatMoney(item.total, language)}</span>
              <span>{t('currentBasePrice')}: {formatMoney(item.ticket_price, language)}</span>
              <span>Telegram: {item.telegram_username ? `@${item.telegram_username}` : t('notSet')}</span>
              <span>{t('telegramId')}: {item.telegram_id}</span>
              <span>{t('createdAt')}: {formatDateTime(item.created_at, language)}</span>
              <span>{t('comment')}: {item.comment || t('none')}</span>
              {item.promo_code && <span>{t('promoCode')}: {item.promo_code}</span>}
              {item.admin_note && <span>{t('adminComment')}: {item.admin_note}</span>}
            </div>
            <div className="admin-actions booking-admin-actions">
              <select value={item.status} onChange={event => { void changeStatus(item.id, event.target.value) }}>
                {bookingStatuses.map(value => <option value={value} key={value}>{statusLabel(value, t)}</option>)}
              </select>
              {item.status === 'pending' && (
                <button className="admin-ghost" onClick={() => { void startProcessing(item.id) }}>
                  {t('startProcessing')}
                </button>
              )}
              <button className="admin-ghost" onClick={() => { void confirmBooking(item.id) }}>{t('confirmBooking')}</button>
              <button className="admin-ghost" onClick={() => { void proposeTime(item.id) }}>{t('proposeTime')}</button>
              <button className="admin-ghost danger" onClick={() => { void declineBooking(item.id) }}>
                {t('declineBooking')}
              </button>
              <a className="admin-ghost" href={`tel:${item.phone}`}>{t('call')}</a>
              {item.chat_url && (
                <a className="admin-ghost" href={item.chat_url} target="_blank" rel="noreferrer">{t('openChat')}</a>
              )}
            </div>
          </article>
        ))}
        {!pageRows.length && <p className="empty">{t('noBookings')}</p>}
      </div>
      <div className="pagination">
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}>{t('previousPage')}</button>
        <span>{page} / {pages}</span>
        <button disabled={page >= pages} onClick={() => setPage(page + 1)}>{t('nextPage')}</button>
      </div>
    </section>
  )
}
