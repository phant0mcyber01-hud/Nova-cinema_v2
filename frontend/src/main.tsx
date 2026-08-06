import React from 'react'
import ReactDOM from 'react-dom/client'
import WebApp from '@twa-dev/sdk'
import App from './App'
import { authenticateTelegram } from './api'
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
  const telegramWebApp = (window as TelegramWindow).Telegram?.WebApp
  telegramWebApp?.ready?.()
  telegramWebApp?.expand?.()
  telegramWebApp?.disableVerticalSwipes?.()
  WebApp.ready()
  WebApp.expand()
  WebApp.disableVerticalSwipes()
  await authenticateTelegram(await waitForTelegramInitData())
}

void bootstrapTelegram().catch(() => undefined).finally(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
})
