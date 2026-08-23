import { call } from './client'
import type { Bonus, GalleryImage, Melody, PublicSettings } from './types'

/** Cinema profile, price, hall size and booking window — all admin-managed. */
export const getPublicSettings = (lang = 'ru') =>
  call<PublicSettings>(`/settings?lang=${encodeURIComponent(lang)}`)

export const getBonuses = (lang = 'ru') => call<Bonus[]>(`/bonuses?lang=${encodeURIComponent(lang)}`)

export const getMelodies = () => call<Melody[]>('/melodies')

export const getGallery = (lang = 'ru') => call<GalleryImage[]>(`/gallery?lang=${encodeURIComponent(lang)}`)
