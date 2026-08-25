import { useEffect, useState } from 'react'

import { updateAdminSettings, type AdminSettings, type AdminSettingsPayload } from '../../api'
import { useI18n } from '../../i18n'

type CinemaSettingsViewProps = {
  settings: AdminSettings
  onSaved: (message: string) => Promise<void>
}

/** hall_seats is derived and updated_at is server-owned, so neither is submitted. */
const toPayload = (settings: AdminSettings): AdminSettingsPayload => ({
  name: settings.name,
  name_uz: settings.name_uz,
  address: settings.address,
  address_uz: settings.address_uz,
  phone: settings.phone,
  telegram_url: settings.telegram_url,
  instagram_url: settings.instagram_url,
  bot_username: settings.bot_username,
  map_url: settings.map_url,
  latitude: settings.latitude,
  longitude: settings.longitude,
  work_hours: settings.work_hours,
  work_hours_uz: settings.work_hours_uz,
  about: settings.about,
  about_uz: settings.about_uz,
  important: settings.important ?? '',
  important_uz: settings.important_uz ?? '',
  faq: settings.faq ?? [],
  base_ticket_price: settings.base_ticket_price,
  currency: settings.currency,
  hall_rows: settings.hall_rows,
  hall_cols: settings.hall_cols,
  max_seats_per_booking: settings.max_seats_per_booking,
  hold_minutes: settings.hold_minutes,
  booking_days_ahead: settings.booking_days_ahead,
  timezone_offset_minutes: settings.timezone_offset_minutes,
})

const numberOrNull = (value: string) => (value.trim() === '' ? null : Number(value))

/** Spec 4.9 / 16: the cinema profile the Mini App and the bot both read. */
export default function CinemaSettingsView({ settings, onSaved }: CinemaSettingsViewProps) {
  const { t } = useI18n()
  const [draft, setDraft] = useState<AdminSettingsPayload>(() => toPayload(settings))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => setDraft(toPayload(settings)), [settings])

  const set = <K extends keyof AdminSettingsPayload>(key: K, value: AdminSettingsPayload[K]) =>
    setDraft(current => ({ ...current, [key]: value }))

  const save = async () => {
    if (!draft.name.trim()) {
      setError(t('bonusRequired'))
      return
    }
    setBusy(true)
    setError('')
    try {
      await updateAdminSettings(draft)
      await onSaved(t('settingsSaved'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('settingsSaveFailed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section>
      <div className="admin-page-intro">
        <span className="admin-eyebrow">{t('adminCinemaTab')}</span>
        <h1>{t('cinemaSettings')}</h1>
        <p className="admin-hint">{t('cinemaSettingsHint')}</p>
      </div>

      <section className="session-builder">
        <header><span>1</span><b>{t('mainInfo')}</b></header>
        <div className="session-step">
          <div className="session-step-body session-options">
            <label>
              <b>{t('cinemaName')}</b><small>{t('russianVersion')}</small>
              <input value={draft.name} onChange={event => set('name', event.target.value)} />
            </label>
            <label>
              <b>{t('cinemaName')}</b><small>{t('uzbekVersion')}</small>
              <input value={draft.name_uz} onChange={event => set('name_uz', event.target.value)} />
            </label>
            <label>
              <b>{t('address')}</b><small>{t('russianVersion')}</small>
              <input value={draft.address} onChange={event => set('address', event.target.value)} />
            </label>
            <label>
              <b>{t('address')}</b><small>{t('uzbekVersion')}</small>
              <input value={draft.address_uz} onChange={event => set('address_uz', event.target.value)} />
            </label>
            <label>
              <b>{t('workHours')}</b><small>{t('russianVersion')}</small>
              <input value={draft.work_hours} onChange={event => set('work_hours', event.target.value)} />
            </label>
            <label>
              <b>{t('workHours')}</b><small>{t('uzbekVersion')}</small>
              <input value={draft.work_hours_uz} onChange={event => set('work_hours_uz', event.target.value)} />
            </label>
          </div>
        </div>
      </section>

      <section className="session-builder">
        <header><span>FAQ</span><b>Важно / Muhim</b></header>
        <div className="session-step-body session-options">
          <label><b>Важно знать</b><small>{t('russianVersion')}</small><textarea value={draft.important} onChange={event => set('important', event.target.value)} /></label>
          <label><b>Muhim maʼlumot</b><small>{t('uzbekVersion')}</small><textarea value={draft.important_uz} onChange={event => set('important_uz', event.target.value)} /></label>
          <label><b>FAQ RU</b><textarea value={draft.faq[0]?.question_ru ?? ''} placeholder="Вопрос" onChange={event => set('faq', [{ question_ru: event.target.value, answer_ru: draft.faq[0]?.answer_ru ?? '', question_uz: draft.faq[0]?.question_uz ?? '', answer_uz: draft.faq[0]?.answer_uz ?? '' }])} /><textarea value={draft.faq[0]?.answer_ru ?? ''} placeholder="Ответ" onChange={event => set('faq', [{ question_ru: draft.faq[0]?.question_ru ?? '', answer_ru: event.target.value, question_uz: draft.faq[0]?.question_uz ?? '', answer_uz: draft.faq[0]?.answer_uz ?? '' }])} /></label>
          <label><b>FAQ UZ</b><textarea value={draft.faq[0]?.question_uz ?? ''} placeholder="Savol" onChange={event => set('faq', [{ question_ru: draft.faq[0]?.question_ru ?? '', answer_ru: draft.faq[0]?.answer_ru ?? '', question_uz: event.target.value, answer_uz: draft.faq[0]?.answer_uz ?? '' }])} /><textarea value={draft.faq[0]?.answer_uz ?? ''} placeholder="Javob" onChange={event => set('faq', [{ question_ru: draft.faq[0]?.question_ru ?? '', answer_ru: draft.faq[0]?.answer_ru ?? '', question_uz: draft.faq[0]?.question_uz ?? '', answer_uz: event.target.value }])} /></label>
        </div>
      </section>

      <section className="session-builder">
        <header><span>2</span><b>{t('contactsSection')}</b></header>
        <div className="session-step">
          <div className="session-step-body session-options">
            <label>
              <b>{t('phone')}</b><small>+998 …</small>
              <input value={draft.phone} onChange={event => set('phone', event.target.value)} inputMode="tel" />
            </label>
            <label>
              <b>{t('telegram')}</b><small>https://t.me/…</small>
              <input value={draft.telegram_url} onChange={event => set('telegram_url', event.target.value)} />
            </label>
            <label>
              <b>{t('instagram')}</b><small>https://instagram.com/…</small>
              <input value={draft.instagram_url} onChange={event => set('instagram_url', event.target.value)} />
            </label>
            <label>
              <b>{t('botUsername')}</b><small>{t('botUsernameHint')}</small>
              <input value={draft.bot_username} onChange={event => set('bot_username', event.target.value)} placeholder="novacinema_bot" />
            </label>
            <label>
              <b>{t('mapLink')}</b><small>https://…</small>
              <input value={draft.map_url} onChange={event => set('map_url', event.target.value)} />
            </label>
            <label>
              <b>{t('latitude')}</b><small>41.31</small>
              <input
                value={draft.latitude ?? ''}
                onChange={event => set('latitude', numberOrNull(event.target.value))}
                inputMode="decimal"
              />
            </label>
            <label>
              <b>{t('longitude')}</b><small>69.24</small>
              <input
                value={draft.longitude ?? ''}
                onChange={event => set('longitude', numberOrNull(event.target.value))}
                inputMode="decimal"
              />
            </label>
          </div>
        </div>
      </section>

      <section className="session-builder">
        <header><span>3</span><b>{t('aboutText')}</b></header>
        <div className="session-step">
          <div className="session-step-body session-options">
            <label>
              <b>{t('aboutText')}</b><small>{t('russianVersion')}</small>
              <textarea value={draft.about} onChange={event => set('about', event.target.value)} />
            </label>
            <label>
              <b>{t('aboutText')}</b><small>{t('uzbekVersion')}</small>
              <textarea value={draft.about_uz} onChange={event => set('about_uz', event.target.value)} />
            </label>
          </div>
        </div>
      </section>

      <section className="session-builder">
        <header><span>4</span><b>{t('hallSection')}</b></header>
        <div className="session-step">
          <div className="session-step-body session-options">
            <label>
              <b>{t('rowsCount')}</b><small>{t('hallSectionHint')}</small>
              <input
                type="number"
                min="1"
                max="26"
                value={draft.hall_rows}
                onChange={event => set('hall_rows', Number(event.target.value))}
              />
            </label>
            <label>
              <b>{t('colsCount')}</b><small>{t('hallSectionHint')}</small>
              <input
                type="number"
                min="1"
                max="20"
                value={draft.hall_cols}
                onChange={event => set('hall_cols', Number(event.target.value))}
              />
            </label>
            <label>
              <b>{t('totalSeats')}</b><small>{t('mainHall')}</small>
              <input value={draft.hall_rows * draft.hall_cols} disabled />
            </label>
          </div>
        </div>
      </section>

      <section className="session-builder">
        <header><span>5</span><b>{t('bookingRules')}</b></header>
        <div className="session-step">
          <div className="session-step-body session-options">
            <label>
              <b>{t('maxSeatsPerBooking')}</b><small>1 … {draft.hall_rows * draft.hall_cols}</small>
              <input
                type="number"
                min="1"
                value={draft.max_seats_per_booking}
                onChange={event => set('max_seats_per_booking', Number(event.target.value))}
              />
            </label>
            <label>
              <b>{t('holdMinutes')}</b><small>1 … 180</small>
              <input
                type="number"
                min="1"
                max="180"
                value={draft.hold_minutes}
                onChange={event => set('hold_minutes', Number(event.target.value))}
              />
            </label>
            <label>
              <b>{t('bookingDaysAhead')}</b><small>1 … 60</small>
              <input
                type="number"
                min="1"
                max="60"
                value={draft.booking_days_ahead}
                onChange={event => set('booking_days_ahead', Number(event.target.value))}
              />
            </label>
            <label>
              <b>{t('timezoneOffset')}</b><small>{t('timezoneOffsetHint')}</small>
              <input
                type="number"
                min="-720"
                max="840"
                value={draft.timezone_offset_minutes}
                onChange={event => set('timezone_offset_minutes', Number(event.target.value))}
              />
            </label>
            <label>
              <b>{t('currency')}</b><small>UZS</small>
              <input value={draft.currency} onChange={event => set('currency', event.target.value)} />
            </label>
          </div>
        </div>
        {error && <p className="error">{error}</p>}
        <footer className="session-builder-actions">
          <button className="book" onClick={() => { void save() }} disabled={busy}>
            {busy ? t('saving') : t('save')}
          </button>
        </footer>
      </section>
    </section>
  )
}
