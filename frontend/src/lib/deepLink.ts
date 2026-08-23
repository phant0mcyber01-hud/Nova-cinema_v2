import WebApp from '@twa-dev/sdk'

/** Payload produced by the share button: `movie_<id>`. */
const MOVIE_PARAM = /^movie_(\d{1,9})$/

type TelegramWindow = Window & {
  Telegram?: { WebApp?: { initDataUnsafe?: { start_param?: string } } }
}

/** The SDK strips tgWebApp* from the URL once it has read them, stashing them here. */
const readFromTelegramSession = (): string => {
  try {
    const raw = window.sessionStorage.getItem('__telegram__initParams') ?? '{}'
    const params = JSON.parse(raw) as { tgWebAppStartParam?: string }
    return typeof params.tgWebAppStartParam === 'string' ? params.tgWebAppStartParam : ''
  } catch {
    return ''
  }
}

/**
 * Start parameter of the current launch.
 *
 * Four sources because the hash is short-lived: the SDK rewrites the URL as soon
 * as it boots, which can happen before React mounts.
 */
export const readStartParam = (): string => {
  const fromSdk = WebApp.initDataUnsafe?.start_param
  if (fromSdk) return fromSdk
  const fromWindow = (window as TelegramWindow).Telegram?.WebApp?.initDataUnsafe?.start_param
  if (fromWindow) return fromWindow
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  return hash.get('tgWebAppStartParam') || readFromTelegramSession()
}

/**
 * Route for a start parameter, or null when it is missing or malformed.
 *
 * A wrong or truncated link must not break the launch — the app simply opens
 * the catalog instead.
 */
export const movieRouteFromStartParam = (value: string): string | null => {
  const match = MOVIE_PARAM.exec(value.trim())
  if (!match) return null
  const id = Number(match[1])
  return id > 0 ? `/movies/${id}` : null
}
