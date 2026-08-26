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
  pending_expire_hours: settings.pending_expire_hours ?? 24,
  timezone_offset_minutes: settings.timezone_offset_minutes,
})

const numberOrNull = (value: string) => (value.trim() === '' ? null : Number(value))

type FaqContent = Pick<AdminSettingsPayload, 'important' | 'important_uz' | 'faq'>
type FaqEditorModalProps = {
  initial: FaqContent
  busy: boolean
  error: string
  onClose: () => void
  onSave: (value: FaqContent) => Promise<void>
}

const copyFaqContent = (value: FaqContent): FaqContent => ({
  important: value.important,
  important_uz: value.important_uz,
  faq: value.faq.map(item => ({ ...item })),
})

/** A focused editor keeps every keystroke away from the much larger settings page. */
function FaqEditorModal({ initial, busy, error, onClose, onSave }: FaqEditorModalProps) {
  const { t } = useI18n()
  const [draft, setDraft] = useState<FaqContent>(() => copyFaqContent(initial))

  const setFaqField = (index: number, field: keyof FaqContent['faq'][number], value: string) =>
    setDraft(current => ({
      ...current,
      faq: current.faq.map((item, itemIndex) => (itemIndex === index ? { ...item, [field]: value } : item)),
    }))

  const addFaqItem = () =>
    setDraft(current => ({
      ...current,
      faq: [...current.faq, { question_ru: '', answer_ru: '', question_uz: '', answer_uz: '' }],
    }))

  const removeFaqItem = (index: number) =>
    setDraft(current => ({ ...current, faq: current.faq.filter((_, itemIndex) => itemIndex !== index) }))

  return (
    <div className="modal-backdrop faq-editor-backdrop" role="presentation">
      <section className="modal faq-editor-modal" role="dialog" aria-modal="true" aria-label="FAQ и Важно знать">
        <header className="faq-editor-head">
          <div>
            <span className="admin-eyebrow">Контент / Kontent</span>
            <h2>FAQ и «Важно знать»</h2>
            <p>Русская и узбекская версии редактируются в одном окне.</p>
          </div>
          <button type="button" className="admin-ghost cms-close" onClick={onClose} disabled={busy} aria-label={t('close')}>×</button>
        </header>

        <fieldset className="faq-editor-body" disabled={busy}>
          <section className="faq-important-grid">
            <label>
              <b>Важно знать</b><small>{t('russianVersion')}</small>
              <textarea value={draft.important} onChange={event => setDraft(current => ({ ...current, important: event.target.value }))} />
            </label>
            <label>
              <b>Muhim maʼlumot</b><small>{t('uzbekVersion')}</small>
              <textarea value={draft.important_uz} onChange={event => setDraft(current => ({ ...current, important_uz: event.target.value }))} />
            </label>
          </section>

          <section className="faq-editor-list">
            <header className="faq-list-head">
              <div><h3>FAQ</h3><p>{draft.faq.length} / 20</p></div>
              <button type="button" className="admin-ghost" onClick={addFaqItem} disabled={draft.faq.length >= 20}>{t('add')}</button>
            </header>
            {draft.faq.map((item, index) => (
              <article className="faq-editor-item" key={index}>
                <header><b>FAQ #{index + 1}</b><button type="button" className="admin-ghost danger" onClick={() => removeFaqItem(index)}>{t('remove')}</button></header>
                <div className="faq-language-grid">
                  <label>
                    <span>RU</span><small>{t('russianVersion')}</small>
                    <input value={item.question_ru} placeholder="Вопрос" onChange={event => setFaqField(index, 'question_ru', event.target.value)} />
                    <textarea value={item.answer_ru} placeholder="Ответ" onChange={event => setFaqField(index, 'answer_ru', event.target.value)} />
                  </label>
                  <label>
                    <span>UZ</span><small>{t('uzbekVersion')}</small>
                    <input value={item.question_uz} placeholder="Savol" onChange={event => setFaqField(index, 'question_uz', event.target.value)} />
                    <textarea value={item.answer_uz} placeholder="Javob" onChange={event => setFaqField(index, 'answer_uz', event.target.value)} />
                  </label>
                </div>
              </article>
            ))}
            {!draft.faq.length && <p className="empty">{t('none')}</p>}
          </section>
        </fieldset>

        <footer className="faq-editor-footer">
          {error && <p className="error">{error}</p>}
          <div>
            <button type="button" className="admin-ghost" onClick={onClose} disabled={busy}>{t('close')}</button>
            <button type="button" className="book fit" onClick={() => { void onSave(draft) }} disabled={busy}>{busy ? t('saving') : t('save')}</button>
          </div>
        </footer>
      </section>
    </div>
  )
}

/** Spec 4.9 / 16: the cinema profile the Mini App and the bot both read. */
export default function CinemaSettingsView({ settings, onSaved }: CinemaSettingsViewProps) {
  const { t } = useI18n()
  const [draft, setDraft] = useState<AdminSettingsPayload>(() => toPayload(settings))
  const [faqOpen, setFaqOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => setDraft(toPayload(settings)), [settings])

  const set = <K extends keyof AdminSettingsPayload>(key: K, value: AdminSettingsPayload[K]) =>
    setDraft(current => ({ ...current, [key]: value }))

  const save = async (payload: AdminSettingsPayload = draft): Promise<boolean> => {
    if (!payload.name.trim()) {
      setError(t('bonusRequired'))
      return false
    }
    setBusy(true)
    setError('')
    try {
      await updateAdminSettings(payload)
      setDraft(payload)
      await onSaved(t('settingsSaved'))
      return true
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('settingsSaveFailed'))
      return false
    } finally {
      setBusy(false)
    }
  }

  const saveFaq = async (value: FaqContent) => {
    const next = { ...draft, ...copyFaqContent(value) }
    if (await save(next)) setFaqOpen(false)
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

      <section className="session-builder faq-launcher">
        <header><span>FAQ</span><b>Важно / Muhim</b></header>
        <div className="faq-launcher-body">
          <div className="faq-launcher-stats">
            <article><strong>{draft.faq.length}</strong><span>FAQ</span></article>
            <article><strong>{[draft.important, draft.important_uz].filter(value => value.trim()).length}/2</strong><span>Важно / Muhim</span></article>
          </div>
          <p>Откройте отдельное большое окно, чтобы спокойно редактировать оба языка.</p>
          <button type="button" className="book fit" onClick={() => setFaqOpen(true)}>{t('edit')}</button>
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
              <b>{t('pendingExpireHours')}</b><small>{t('pendingExpireHoursHint')}</small>
              <input
                type="number"
                min="0"
                max="336"
                value={draft.pending_expire_hours}
                onChange={event => set('pending_expire_hours', Number(event.target.value))}
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

      {faqOpen && (
        <FaqEditorModal
          initial={{ important: draft.important, important_uz: draft.important_uz, faq: draft.faq }}
          busy={busy}
          error={error}
          onClose={() => setFaqOpen(false)}
          onSave={saveFaq}
        />
      )}
    </section>
  )
}
