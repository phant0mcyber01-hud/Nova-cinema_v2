import { call } from './client'
import type { Bonus, GalleryImage, PublicSettings } from './types'

export const getPublicSettings = (lang = 'ru') => call<PublicSettings>(`/settings?lang=${encodeURIComponent(lang)}`)
export const getBonuses = (lang = 'ru') => call<Bonus[]>(`/bonuses?lang=${encodeURIComponent(lang)}`)
export const getGallery = (lang = 'ru') => call<GalleryImage[]>(`/gallery?lang=${encodeURIComponent(lang)}`)
