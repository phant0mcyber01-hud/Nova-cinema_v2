import WebApp from '@twa-dev/sdk'

/**
 * Telegram theme integration.
 *
 * Nova Cinema keeps its own dark, cinematic palette — repainting a cinema app
 * white because the phone is in light mode would fight the brand. What must
 * follow Telegram is the *chrome*: the header and the background behind the
 * Mini App, which otherwise clash with the page, and the accent colours the
 * client hands us.
 *
 * `data-color-scheme` is written to <html> so a light palette can be dropped
 * in later without touching a single component.
 */

/** Our own surface colour, kept in sync with `body` in styles.css. */
const APP_BACKGROUND = '#0b090a'

type ThemeKey = keyof typeof WebApp.themeParams

const CSS_VARIABLES: Record<string, ThemeKey> = {
  '--tg-theme-bg-color': 'bg_color',
  '--tg-theme-secondary-bg-color': 'secondary_bg_color',
  '--tg-theme-text-color': 'text_color',
  '--tg-theme-hint-color': 'hint_color',
  '--tg-theme-link-color': 'link_color',
  '--tg-theme-button-color': 'button_color',
  '--tg-theme-button-text-color': 'button_text_color',
}

/** Older clients throw on calls they do not know; a theme is never worth a crash. */
const attempt = (action: () => void) => {
  try {
    action()
  } catch {
    /* the Mini App still works without it */
  }
}

const applyThemeParams = () => {
  const root = document.documentElement
  root.dataset.colorScheme = WebApp.colorScheme ?? 'dark'
  for (const [variable, key] of Object.entries(CSS_VARIABLES)) {
    const value = WebApp.themeParams?.[key]
    if (value) root.style.setProperty(variable, value)
  }
}

const paintTelegramChrome = () => {
  // Hex colours need Bot API 6.9; older clients take a named slot instead.
  attempt(() => {
    if (WebApp.isVersionAtLeast?.('6.9')) WebApp.setHeaderColor(APP_BACKGROUND)
    else WebApp.setHeaderColor('bg_color')
  })
  attempt(() => WebApp.setBackgroundColor(APP_BACKGROUND))
}

/** Apply once at startup and follow the user changing their theme afterwards. */
export const initTelegramTheme = () => {
  applyThemeParams()
  paintTelegramChrome()
  attempt(() => WebApp.onEvent('themeChanged', () => {
    applyThemeParams()
    paintTelegramChrome()
  }))
}

/**
 * Ask Telegram to confirm before closing.
 *
 * Used while seats are held: closing the app then would silently give them up.
 */
export const setClosingConfirmation = (enabled: boolean) => {
  attempt(() => {
    if (enabled) WebApp.enableClosingConfirmation()
    else WebApp.disableClosingConfirmation()
  })
}
