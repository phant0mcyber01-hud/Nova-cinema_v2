import WebApp from '@twa-dev/sdk'
import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { haptic } from '../lib/haptic'

/** Keeps the Telegram BackButton in sync with the router. */
export default function TelegramRouteControls() {
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
