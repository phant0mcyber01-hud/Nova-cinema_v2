import { call } from './client'
import type { Bonus, GalleryImage, Melody, PublicSettings } from './types'

/** Cinema profile, price, hall size and booking window — all admin-managed. */
export const getPublicSettings = (lang = 'ru') =>
  call<PublicSettings>(`/settings?lang=${encodeURIComponent(lang)}`)

export const getBonuses = (lang = 'ru') => call<Bonus[]>(`/bonuses?lang=${encodeURIComponent(lang)}`)

let melodiesRequest: Promise<Melody[]> | null = null

const cacheMelodiesRequest = (request: Promise<Melody[]>): Promise<Melody[]> => {
  melodiesRequest = request.catch(error => {
    melodiesRequest = null
    throw error
  })
  return melodiesRequest
}

const earlyMelodies = (window as Window & {
  __novaMelodiesEarly?: Promise<Melody[] | null>
}).__novaMelodiesEarly

if (earlyMelodies) {
  cacheMelodiesRequest(earlyMelodies.then(melodies => melodies ?? call<Melody[]>('/melodies')))
}

/** Start once and share the result between the global player and About page. */
export const preloadMelodies = (): Promise<Melody[]> => {
  if (!melodiesRequest) return cacheMelodiesRequest(call<Melody[]>('/melodies'))
  return melodiesRequest
}

export const invalidateMelodies = () => { melodiesRequest = null }

export const getMelodies = preloadMelodies

export const getGallery = (lang = 'ru') => call<GalleryImage[]>(`/gallery?lang=${encodeURIComponent(lang)}`)
