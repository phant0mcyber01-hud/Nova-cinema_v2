import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

import { movieRouteFromStartParam, readStartParam } from '../lib/deepLink'

/**
 * Opens the shared movie card when the Mini App is launched from a deep link.
 *
 * Runs once per launch and replaces the history entry, so the Telegram back
 * button still leads to the catalog rather than to an empty start route.
 */
export default function DeepLinkHandler() {
  const navigate = useNavigate()
  const handled = useRef(false)

  useEffect(() => {
    if (handled.current) return
    handled.current = true
    const route = movieRouteFromStartParam(readStartParam())
    if (route) navigate(route, { replace: true })
  }, [navigate])

  return null
}
