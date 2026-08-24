import React from 'react'
import ReactDOM from 'react-dom/client'
import WebApp from '@twa-dev/sdk'
import App from './App'
import { authenticateTelegram, preloadMelodies } from './api'
import { initTelegramTheme } from './lib/telegramTheme'
import './styles.css'

type TelegramWindow = Window & {
  Telegram?: {
    WebApp?: {
      initData?: string
      ready?: () => void
      expand?: () => void
      disableVerticalSwipes?: () => void
    }
  }
}

const readInitDataFromHash = () => {
  const hash = window.location.hash.replace(/^#/, '')
  return new URLSearchParams(hash).get('tgWebAppData') ?? ''
}

const readInitDataFromTelegramSession = () => {
  try {
    const params = JSON.parse(window.sessionStorage.getItem('__telegram__initParams') ?? '{}') as { tgWebAppData?: string }
    return typeof params.tgWebAppData === 'string' ? params.tgWebAppData : ''
  } catch {
    return ''
  }
}

const readTelegramInitData = () => {
  const telegramWebApp = (window as TelegramWindow).Telegram?.WebApp
  return readInitDataFromHash() || WebApp.initData || telegramWebApp?.initData || readInitDataFromTelegramSession()
}

const waitForTelegramInitData = async () => {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const initData = readTelegramInitData()
    if (initData) return initData
    await new Promise(resolve => window.setTimeout(resolve, 50))
  }
  return ''
}

const bootstrapTelegram = async () => {
  // Start auth first: it synchronously deactivates any previous user's token.
  const authentication = authenticateTelegram(waitForTelegramInitData())
  const telegramWebApp = (window as TelegramWindow).Telegram?.WebApp
  telegramWebApp?.ready?.()
  telegramWebApp?.expand?.()
  telegramWebApp?.disableVerticalSwipes?.()
  WebApp.ready()
  WebApp.expand()
  WebApp.disableVerticalSwipes()
  initTelegramTheme()
  await authentication
}

// Resolve the primary track and Telegram identity in parallel with first paint.
// Protected routes observe authReady=false and wait; public routes render now.
void preloadMelodies().catch(() => undefined)
void bootstrapTelegram().catch(() => undefined)
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
