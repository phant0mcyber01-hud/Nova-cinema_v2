import { BrowserRouter, Route, Routes } from 'react-router-dom'

import DeepLinkHandler from './components/DeepLinkHandler'
import ProtectedAdminRoute from './components/ProtectedAdminRoute'
import TelegramRouteControls from './components/TelegramRouteControls'
import { LanguageProvider } from './i18n'
import Home from './pages/Home'
import MoviePage from './pages/MoviePage'
import DatePage from './pages/booking/DatePage'
import HallPage from './pages/booking/HallPage'
import Success from './pages/booking/Success'
import TimePage from './pages/booking/TimePage'
import ProfileRoutes from './pages/profile/Profile'

export default function App() {
  return (
    <LanguageProvider>
      <BrowserRouter>
        <DeepLinkHandler />
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
