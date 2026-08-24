import { translate } from '../i18n'
import type { AuthState } from './types'

/** Carries the HTTP status so callers can react to 404 specifically. */
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const authStorageKey = 'nova-cinema-auth-v1'

type StoredAuth = {
  accessToken: string
  role: string
}

const readStoredAuth = (): StoredAuth | null => {
  try {
    const value = window.localStorage.getItem(authStorageKey) ?? window.sessionStorage.getItem(authStorageKey)
    if (!value) return null
    const parsed = JSON.parse(value) as Partial<StoredAuth>
    if (typeof parsed.accessToken !== 'string' || !parsed.accessToken) return null
    return { accessToken: parsed.accessToken, role: typeof parsed.role === 'string' ? parsed.role : '' }
  } catch {
    return null
  }
}

let accessToken: string | null = null
let role = ''
let authReady = true
let authPromise: Promise<void> = Promise.resolve()

const applyAuth = (data: StoredAuth) => {
  accessToken = data.accessToken
  role = data.role
}

const deactivateAuth = () => {
  accessToken = null
  role = ''
}

const saveAuth = (data: StoredAuth) => {
  applyAuth(data)
  try {
    window.localStorage.setItem(authStorageKey, JSON.stringify(data))
    window.sessionStorage.setItem(authStorageKey, JSON.stringify(data))
  } catch {
    window.sessionStorage.setItem(authStorageKey, JSON.stringify(data))
  }
}

const clearAuth = () => {
  deactivateAuth()
  try {
    window.localStorage.removeItem(authStorageKey)
    window.sessionStorage.removeItem(authStorageKey)
  } catch {
    window.sessionStorage.removeItem(authStorageKey)
  }
}

const storedAuth = readStoredAuth()
if (storedAuth) applyAuth(storedAuth)

/** Single fetch wrapper: attaches the bearer token, unwraps JSON and normalises errors. */
export const call = async <T>(path: string, options: RequestInit = {}): Promise<T> => {
  const isFormData = options.body instanceof FormData
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
      ...(accessToken && path !== '/auth/telegram' ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...options.headers,
    },
  })
  const text = await response.text()
  let data: unknown = {}
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = { detail: text }
    }
  }
  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/telegram') clearAuth()
    const detail = typeof data === 'object' && data !== null && 'detail' in data ? String(data.detail) : translate('serverError')
    throw new ApiError(detail, response.status)
  }
  return data as T
}

export async function authenticateTelegram(initData: string | Promise<string>): Promise<void> {
  authReady = false
  const cached = readStoredAuth()
  // Do not expose a previous Telegram user's token while a new identity is pending.
  deactivateAuth()
  authPromise = (async () => {
    const resolvedInitData = await initData
    if (!resolvedInitData) {
      if (cached) applyAuth(cached)
      return
    }
    clearAuth()
    const data = await call<{ access_token: string; user: { role: string } }>('/auth/telegram', {
      method: 'POST',
      body: JSON.stringify({ init_data: resolvedInitData }),
    })
    saveAuth({ accessToken: data.access_token, role: data.user.role })
  })().finally(() => {
    authReady = true
  })
  return authPromise
}

export const isAdmin = () => role === 'admin'
export const getAuthState = (): AuthState => ({
  ready: authReady,
  authenticated: Boolean(accessToken),
  role,
  isAdmin: role === 'admin',
})
export const waitForAuth = () => authPromise
