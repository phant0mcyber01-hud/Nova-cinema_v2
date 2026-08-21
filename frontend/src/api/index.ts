/** Public surface of the API layer — call sites keep importing from './api'. */
export * from './types'
export { ApiError, authenticateTelegram, getAuthState, isAdmin, waitForAuth } from './client'
export * from './settings'
export * from './catalog'
export * from './booking'
export * from './profile'
export * from './admin'
