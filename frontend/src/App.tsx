import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import DeepLinkHandler from './components/DeepLinkHandler'
import TelegramRouteControls from './components/TelegramRouteControls'
import { getPublicSettings } from './api'
import { LanguageProvider, setCurrency } from './i18n'
import { AudioProvider } from './lib/audioPlayer'

const NotFound = lazy(() => import('./components/NotFound'))
const ProtectedAdminRoute = lazy(() => import('./components/ProtectedAdminRoute'))
const About = lazy(() => import('./pages/About'))
const Home = lazy(() => import('./pages/Home'))
const MoviePage = lazy(() => import('./pages/MoviePage'))
const DatePage = lazy(() => import('./pages/booking/DatePage'))
const HallPage = lazy(() => import('./pages/booking/HallPage'))
const Success = lazy(() => import('./pages/booking/Success'))
const TimePage = lazy(() => import('./pages/booking/TimePage'))
const ProfileRoutes = lazy(() => import('./pages/profile/Profile'))

/**
 * The currency is an admin setting, so it has to be loaded once for the whole
 * app — not per screen. Doing it per screen meant a direct link to the ticket
 * list showed the dictionary fallback while the hall showed the real value.
 */
function useCinemaCurrency() {
  useEffect(() => {
    let active = true
    void getPublicSettings()
      .then(settings => { if (active) setCurrency(settings.currency) })
      .catch(() => undefined)
    return () => { active = false }
  }, [])
}

function RouteFallback() {
  return (
    <main className="app" aria-busy="true">
      <div className="hall-skeleton compact" />
    </main>
  )
}

export default function App() {
  useCinemaCurrency()
  return (
    <LanguageProvider>
      {/* Above the router on purpose: navigation must not restart the melody. */}
      <AudioProvider>
        <BrowserRouter>
          <DeepLinkHandler />
          <TelegramRouteControls />
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/movies/:id" element={<MoviePage />} />
              <Route path="/about" element={<About />} />
              <Route path="/admin" element={<ProtectedAdminRoute />} />
              <Route path="/profile/*" element={<ProfileRoutes />} />
              <Route path="/booking/:id/date" element={<DatePage />} />
              <Route path="/booking/:id/date/:date/time" element={<TimePage />} />
              <Route path="/booking/:id/date/:date/time/:time/hall" element={<HallPage />} />
              <Route path="/booking/success/:code" element={<Success />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AudioProvider>
    </LanguageProvider>
  )
}
