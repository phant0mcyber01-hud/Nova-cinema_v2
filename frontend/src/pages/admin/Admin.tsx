import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'

import {
  clearAdminNotifications,
  getAdminBonuses,
  getAdminGallery,
  getAdminMovies,
  getAdminReviews,
  getAdminSlots,
  getAdminSettings,
  getDashboard,
  isAdmin,
  setBasePrice,
  type AdminBonus,
  type AdminGalleryImage,
  type AdminReview,
  type AdminSlot,
  type AdminSettings,
  type MovieDetail,
} from '../../api'
import BottomNav from '../../components/BottomNav'
import { formatMoney, translate, useI18n, type TranslationKey } from '../../i18n'
import BonusesView from './AdminBonuses'
import CinemaSettingsView from './AdminCinemaSettings'
import GalleryView from './AdminGallery'
import MoviesView from './AdminMovies'
import NewReleasesView from './AdminNewReleases'
import PriceView from './AdminPrice'
import ReviewsView from './AdminReviews'
import SlotsView from './AdminSessions'

/**
 * There used to be a "Requests" tab here that duplicated the bot's own
 * workflow with window.prompt()/window.confirm() dialogs -- a second, weaker
 * copy of the exact same contact/confirm/propose/decline actions the bot's DM
 * now offers with real buttons. Every request now moves entirely through
 * Telegram: `bk:...` buttons on the admin's own notification
 * (backend/services/bot_actions.py). The dashboard below keeps the read-only
 * counts -- a number the administrator glances at, not a place to act on one.
 */

type Tab =
  | 'dashboard' | 'movies' | 'new' | 'sessions'
  | 'price' | 'bonuses' | 'gallery' | 'cinema' | 'reviews'
type DashboardData = Awaited<ReturnType<typeof getDashboard>>
const REFRESH_INTERVAL_MS = 30_000

const tabs: { id: Tab; labelKey: TranslationKey }[] = [
  { id: 'dashboard', labelKey: 'adminDashboard' },
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

const statusLabel = (status: string, translate: (key: TranslationKey) => string) => (
  statusTranslationKeys[status] ? translate(statusTranslationKeys[status]) : status
)

export default function Admin() {
  const { language, t } = useI18n()
  const [tab, setTab] = useState<Tab>('dashboard')
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
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
        dashboardData, movieData, slotData,
        settingsData, bonusData, reviewData, galleryData,
      ] = await Promise.all([
        getDashboard(),
        getAdminMovies(language),
        getAdminSlots(),
        getAdminSettings(),
        getAdminBonuses(),
        getAdminReviews(),
        getAdminGallery(),
      ])
      setDashboard(dashboardData)
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

  const refreshDashboard = useCallback(async () => {
    try {
      setDashboard(await getDashboard())
    } catch {
      // A background counter refresh must never interrupt an admin who is typing.
    }
  }, [])

  useEffect(() => {
    void load()
    const intervalId = window.setInterval(() => { void refreshDashboard() }, REFRESH_INTERVAL_MS)
    return () => window.clearInterval(intervalId)
  }, [load, refreshDashboard])

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

      {!loading && tab === 'dashboard' && dashboard && (
        <DashboardView
          data={dashboard}
          onClearNotifications={() => guard(() => clearAdminNotifications(), t('cleanupDone'))}
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

function DashboardView({ data, onClearNotifications }: {
  data: DashboardData
  onClearNotifications: () => Promise<void>
}) {
  const { language, t } = useI18n()
  const [clearConfirm, setClearConfirm] = useState(false)
  const [clearBusy, setClearBusy] = useState(false)
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
      <h2>{t('latestNotifications')}</h2>
      {data.notifications.length > 0 && (
        <section className="cleanup-card">
          {!clearConfirm ? (
            <button className="admin-ghost danger" onClick={() => setClearConfirm(true)}>{t('clearNotifications')}</button>
          ) : (
            <div>
              <b>{t('clearAllConfirm')}</b>
              <button className="admin-ghost danger" disabled={clearBusy} onClick={() => {
                setClearBusy(true)
                void onClearNotifications().finally(() => { setClearBusy(false); setClearConfirm(false) })
              }}>{t('clearNotifications')}</button>
              <button className="admin-ghost" disabled={clearBusy} onClick={() => setClearConfirm(false)}>{t('cancel')}</button>
            </div>
          )}
        </section>
      )}
      <div className="admin-table compact">
        {data.notifications.map(item => (
          <article className={item.is_read ? 'notice read' : 'notice'} key={item.id}>
            <b>#{item.booking_id}</b><span>{item.message}</span>
          </article>
        ))}
        {!data.notifications.length && <p className="empty">{t('notificationsNone')}</p>}
      </div>
    </section>
  )
}
