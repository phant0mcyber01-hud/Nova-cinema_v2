import { useEffect } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import DeepLinkHandler from './components/DeepLinkHandler'
import NotFound from './components/NotFound'
import ProtectedAdminRoute from './components/ProtectedAdminRoute'
import TelegramRouteControls from './components/TelegramRouteControls'
import { getPublicSettings } from './api'
import { LanguageProvider, setCurrency } from './i18n'
import About from './pages/About'
import Home from './pages/Home'
import MoviePage from './pages/MoviePage'
import DatePage from './pages/booking/DatePage'
import HallPage from './pages/booking/HallPage'
import Success from './pages/booking/Success'
import TimePage from './pages/booking/TimePage'
import ProfileRoutes from './pages/profile/Profile'

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

export default function App() {
  useCinemaCurrency()
  return (
    <LanguageProvider>
      <BrowserRouter>
        <DeepLinkHandler />
        <TelegramRouteControls />
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
      </BrowserRouter>
    </LanguageProvider>
  )
}
