import { useState } from 'react'

import { createAdminSlot, deleteAdminSlot, updateAdminSlot, type AdminSlot } from '../../api'
import { useI18n } from '../../i18n'

/**
 * The times the hall opens.
 *
 * There is no film here on purpose: Nova Cinema sells places in one auditorium
 * at a date and an hour, and what gets played is agreed with the viewer
 * afterwards. Switching a time off hides it from the booking flow without
 * touching the requests already filed for it.
 */

type SlotsViewProps = {
  slots: AdminSlot[]
  onSaved: (message: string) => Promise<void>
}

const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/

export default function SlotsView({ slots, onSaved }: SlotsViewProps) {
  const { language, t } = useI18n()
  const [startTime, setStartTime] = useState('12:00')
  const [editing, setEditing] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const hint = language === 'ru'
    ? 'Общие сеансы без привязки к фильму. Фильм согласуется с гостем отдельно.'
    : "Filmga bog'lanmagan umumiy vaqtlar. Film mehmon bilan alohida kelishiladi."
  const invalid = language === 'ru' ? 'Введите время в формате ЧЧ:ММ' : 'Vaqtni SS:DD ko‘rinishida kiriting'
  const activeLabel = language === 'ru' ? 'Показывать в приложении' : 'Ilovada ko‘rsatilsin'

  const reset = () => { setEditing(null); setStartTime('12:00') }

  const save = async () => {
    if (!TIME_PATTERN.test(startTime)) { setError(invalid); return }
    setBusy(true)
    setError('')
    try {
      const payload = { start_time: startTime, is_active: true, sort_order: slots.length }
      if (editing === null) await createAdminSlot(payload)
      else {
        const current = slots.find(item => item.id === editing)
        await updateAdminSlot(editing, { ...payload, is_active: current?.is_active ?? true, sort_order: current?.sort_order ?? 0 })
      }
      reset()
      await onSaved(t('sessionSaved'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('sessionSaveFailed'))
    } finally {
      setBusy(false)
    }
  }

  /** Hiding a time is reversible; the requests already made for it are not touched. */
  const toggle = async (slot: AdminSlot) => {
    setBusy(true)
    try {
      await updateAdminSlot(slot.id, {
        start_time: slot.start_time,
        is_active: !slot.is_active,
        sort_order: slot.sort_order,
      })
      await onSaved(t('sessionSaved'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('sessionSaveFailed'))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (slot: AdminSlot) => {
    if (!window.confirm(`${t('remove')} ${slot.start_time}?`)) return
    setBusy(true)
    try {
      await deleteAdminSlot(slot.id)
      if (editing === slot.id) reset()
      await onSaved(t('sessionDeleted'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('sessionSaveFailed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section>
      <div className="admin-page-intro">
        <span className="admin-eyebrow">NOVA</span>
        <h1>{t('sessionsManagement')}</h1>
        <p className="admin-hint">{hint}</p>
      </div>

      <section className="session-builder">
        <div className="session-options">
          <label>
            <b>{t('timeShow')}</b>
            <input type="time" value={startTime} onChange={event => setStartTime(event.target.value)} />
          </label>
        </div>
        {error && <p className="error">{error}</p>}
        <button className="book" disabled={busy} onClick={() => void save()}>{t('saveChanges')}</button>
        {editing !== null && <button className="admin-ghost" onClick={reset}>{t('cancel')}</button>}
      </section>

      <div className="session-card-list">
        {slots.map(item => (
          <article className="session-card" key={item.id}>
            <div className="session-date"><b>{item.start_time}</b></div>
            <div className="session-card-body">
              <span className={`status-chip ${item.is_active ? 'live' : 'muted'}`}>
                {item.is_active ? activeLabel : t('hidden')}
              </span>
            </div>
            <div className="admin-actions">
              <button className="admin-ghost" onClick={() => { setEditing(item.id); setStartTime(item.start_time) }}>{t('edit')}</button>
              <button className="admin-ghost" disabled={busy} onClick={() => void toggle(item)}>
                {item.is_active ? t('hide') : t('show')}
              </button>
              <button className="admin-ghost danger" disabled={busy} onClick={() => void remove(item)}>{t('remove')}</button>
            </div>
          </article>
        ))}
        {!slots.length && <p className="empty">{t('noSessions')}</p>}
      </div>
    </section>
  )
}
