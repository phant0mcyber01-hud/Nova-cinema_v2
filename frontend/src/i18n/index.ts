import WebApp from '@twa-dev/sdk'
import { createContext, createElement, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { ru, type TranslationKey } from './ru'
import { uz } from './uz'

export type { TranslationKey }
export { ru, uz }

export type Language = 'ru' | 'uz'

export const copy: Record<Language, Record<TranslationKey, string>> = { ru, uz }

const languageStorageKey = 'nova-cinema-language-v1'
const localeByLanguage: Record<Language, string> = { ru: 'ru-RU', uz: 'uz-UZ' }

type TelegramWindow = Window & {
  Telegram?: {
    WebApp?: {
      initDataUnsafe?: {
        user?: {
          language_code?: string
        }
      }
    }
  }
}

type LanguageContextValue = {
  language: Language
  setLanguage: (language: Language) => void
  t: (key: TranslationKey) => string
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

const normalizeLanguage = (value: string | null | undefined): Language => (
  value?.toLowerCase().startsWith('uz') ? 'uz' : 'ru'
)

const readStoredLanguage = (): Language | null => {
  try {
    const value = window.localStorage.getItem(languageStorageKey) ?? window.sessionStorage.getItem(languageStorageKey)
    return value === 'ru' || value === 'uz' ? value : null
  } catch {
    const value = window.sessionStorage.getItem(languageStorageKey)
    return value === 'ru' || value === 'uz' ? value : null
  }
}

const detectTelegramLanguage = () => {
  const telegramWindow = window as TelegramWindow
  return WebApp.initDataUnsafe.user?.language_code
    ?? telegramWindow.Telegram?.WebApp?.initDataUnsafe?.user?.language_code
    ?? navigator.language
}

const saveLanguage = (language: Language) => {
  try {
    window.localStorage.setItem(languageStorageKey, language)
    window.sessionStorage.setItem(languageStorageKey, language)
  } catch {
    window.sessionStorage.setItem(languageStorageKey, language)
  }
}

export const getCurrentLanguage = () => readStoredLanguage() ?? normalizeLanguage(detectTelegramLanguage())

export const translate = (key: TranslationKey) => copy[getCurrentLanguage()][key]

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => readStoredLanguage() ?? normalizeLanguage(detectTelegramLanguage()))

  useEffect(() => {
    document.documentElement.lang = language
    saveLanguage(language)
  }, [language])

  const setLanguage = useCallback((nextLanguage: Language) => {
    setLanguageState(nextLanguage)
  }, [])

  const value = useMemo<LanguageContextValue>(() => ({
    language,
    setLanguage,
    t: (key: TranslationKey) => copy[language][key],
  }), [language, setLanguage])

  return createElement(LanguageContext.Provider, { value }, children)
}

export function useI18n() {
  const context = useContext(LanguageContext)
  if (!context) throw new Error('useI18n must be used inside LanguageProvider')
  return context
}

export const formatMoney = (value: number, language: Language) => (
  `${value.toLocaleString(localeByLanguage[language])} ${copy[language].currency}`
)

export const formatDateShort = (date: string, language: Language) => (
  new Intl.DateTimeFormat(localeByLanguage[language], { weekday: 'short', day: 'numeric', month: 'short' })
    .format(new Date(`${date}T12:00:00`))
)

export const formatDateTime = (value: string, language: Language) => (
  new Date(value).toLocaleString(localeByLanguage[language])
)
