import WebApp from '@twa-dev/sdk'
import { useEffect, useState } from 'react'

import { getGallery, getPublicSettings, type GalleryImage, type PublicSettings } from '../api'
import Shell from '../components/Shell'
import { translate, useI18n } from '../i18n'
import { haptic } from '../lib/haptic'

/** Where to send someone who taps "open on the map". */
const mapLink = (settings: PublicSettings) => {
  if (settings.map_url) return settings.map_url
  if (settings.latitude !== null && settings.longitude !== null) {
    return `https://maps.google.com/?q=${settings.latitude},${settings.longitude}`
  }
  if (settings.address) return `https://maps.google.com/?q=${encodeURIComponent(settings.address)}`
  return ''
}

/** Telegram opens t.me links itself; everything else goes to the browser. */
const openExternal = (url: string) => {
  haptic.tap()
  if (!WebApp.initData) {
    window.open(url, '_blank', 'noopener')
    return
  }
  if (url.includes('t.me/')) WebApp.openTelegramLink(url)
  else WebApp.openLink(url)
}

/** Spec 16: the cinema's own page. Everything on it is admin-managed. */
export default function About() {
  const { language, t } = useI18n()
  const [settings, setSettings] = useState<PublicSettings | null>(null)
  const [photos, setPhotos] = useState<GalleryImage[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void Promise.all([getPublicSettings(language), getGallery(language)])
      .then(([profile, images]) => {
        if (!active) return
        setSettings(profile)
        setPhotos(images)
        setError('')
      })
      .catch(reason => {
        if (active) setError(reason instanceof Error ? reason.message : translate('serverError'))
      })
    return () => { active = false }
  }, [language])

  if (error) return <Shell><p className="error">{error}</p></Shell>
  if (!settings) return <Shell><div className="hall-skeleton compact" /></Shell>

  const map = mapLink(settings)

  return (
    <Shell>
      <section className="about-hero">
        <p>{t('aboutTitle')}</p>
        <h1>{settings.name}</h1>
        {settings.about && <p className="about-text">{settings.about}</p>}
      </section>

      <section className="about-block">
        <h2>{t('howToFindUs')}</h2>
        <div className="about-facts">
          {settings.address && (
            <div><small>{t('address')}</small><b>{settings.address}</b></div>
          )}
          {settings.work_hours && (
            <div><small>{t('workHours')}</small><b>{settings.work_hours}</b></div>
          )}
        </div>
        <div className="about-actions">
          {settings.phone && (
            <a className="book fit" href={`tel:${settings.phone.replace(/[^\d+]/g, '')}`} onClick={haptic.tap}>
              ☎ {settings.phone}
            </a>
          )}
          {map && (
            <button className="admin-ghost" onClick={() => openExternal(map)}>📍 {t('openMap')}</button>
          )}
          {settings.telegram_url && (
            <button className="admin-ghost" onClick={() => openExternal(settings.telegram_url)}>
              💬 {t('writeTelegram')}
            </button>
          )}
          {settings.instagram_url && (
            <button className="admin-ghost" onClick={() => openExternal(settings.instagram_url)}>
              📸 {t('instagram')}
            </button>
          )}
        </div>
      </section>

      <section className="about-block">
        <h2>{t('cinemaPhotos')}</h2>
        {photos.length ? (
          <div className="about-gallery">
            {photos.map(photo => (
              <figure key={photo.id}>
                <img src={photo.image_url} alt={photo.caption || settings.name} loading="lazy" />
                {photo.caption && <figcaption>{photo.caption}</figcaption>}
              </figure>
            ))}
          </div>
        ) : <p className="empty">{t('noPhotosYet')}</p>}
      </section>
    </Shell>
  )
}
