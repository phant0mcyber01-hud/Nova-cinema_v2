import { useState } from 'react'

import {
  createAdminBonus,
  deleteAdminBonus,
  updateAdminBonus,
  type AdminBonus,
  type AdminBonusPayload,
} from '../../api'
import { useI18n } from '../../i18n'

type BonusesViewProps = {
  bonuses: AdminBonus[]
  onSaved: (message: string) => Promise<void>
}

const emptyBonus = (): AdminBonusPayload => ({
  title: '',
  title_uz: '',
  text: '',
  text_uz: '',
  is_active: true,
  sort_order: 0,
})

const toPayload = (bonus: AdminBonus): AdminBonusPayload => ({
  title: bonus.title,
  title_uz: bonus.title_uz,
  text: bonus.text,
  text_uz: bonus.text_uz,
  is_active: bonus.is_active,
  sort_order: bonus.sort_order,
})

/** Spec 4.6: promotions are content, not code. */
export default function BonusesView({ bonuses, onSaved }: BonusesViewProps) {
  const { t } = useI18n()
  const [draft, setDraft] = useState<AdminBonusPayload>(emptyBonus)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const reset = () => {
    setDraft(emptyBonus())
    setEditingId(null)
    setError('')
  }

  const save = async () => {
    if (!draft.title.trim()) {
      setError(t('bonusRequired'))
      return
    }
    setBusy(true)
    setError('')
    try {
      if (editingId === null) await createAdminBonus(draft)
      else await updateAdminBonus(editingId, draft)
      reset()
      await onSaved(t('bonusSaved'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
    } finally {
      setBusy(false)
    }
  }

  const edit = (bonus: AdminBonus) => {
    setDraft(toPayload(bonus))
    setEditingId(bonus.id)
    setError('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const toggle = async (bonus: AdminBonus) => {
    try {
      await updateAdminBonus(bonus.id, { ...toPayload(bonus), is_active: !bonus.is_active })
      await onSaved(t('bonusSaved'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
    }
  }

  const remove = async (bonus: AdminBonus) => {
    if (!window.confirm(`${t('deleteBonusConfirm')} "${bonus.title}"?`)) return
    try {
      await deleteAdminBonus(bonus.id)
      if (editingId === bonus.id) reset()
      await onSaved(t('bonusDeleted'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
    }
  }

  return (
    <section>
      <div className="admin-page-intro">
        <span className="admin-eyebrow">{t('content')}</span>
        <h1>{t('bonusesManagement')}</h1>
        <p className="admin-hint">{t('bonusesHint')}</p>
      </div>

      <section className="session-builder">
        <header>
          <span>{editingId === null ? t('addBonus') : t('edit')}</span>
          <b>{editingId === null ? t('bonusesManagement') : `#${editingId}`}</b>
        </header>
        <div className="session-step">
          <span className="session-step-number">1</span>
          <div className="session-step-body session-options">
            <label>
              <b>{t('bonusTitle')}</b><small>{t('russianVersion')}</small>
              <input value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} />
            </label>
            <label>
              <b>{t('bonusTitle')}</b><small>{t('uzbekVersion')}</small>
              <input value={draft.title_uz} onChange={event => setDraft({ ...draft, title_uz: event.target.value })} />
            </label>
          </div>
        </div>
        <div className="session-step">
          <span className="session-step-number">2</span>
          <div className="session-step-body session-options">
            <label>
              <b>{t('bonusText')}</b><small>{t('russianVersion')}</small>
              <textarea value={draft.text} onChange={event => setDraft({ ...draft, text: event.target.value })} />
            </label>
            <label>
              <b>{t('bonusText')}</b><small>{t('uzbekVersion')}</small>
              <textarea value={draft.text_uz} onChange={event => setDraft({ ...draft, text_uz: event.target.value })} />
            </label>
          </div>
        </div>
        <div className="session-step">
          <span className="session-step-number">3</span>
          <div className="session-step-body session-options">
            <label>
              <b>{t('publication')}</b><small>{t('bonusesHint')}</small>
              <select
                value={draft.is_active ? 'on' : 'off'}
                onChange={event => setDraft({ ...draft, is_active: event.target.value === 'on' })}
              >
                <option value="on">{t('enabled')}</option>
                <option value="off">{t('disabled')}</option>
              </select>
            </label>
            <label>
              <b>{t('catalogPosition')}</b><small>{t('catalogPositionHint')}</small>
              <input
                type="number"
                value={draft.sort_order}
                onChange={event => setDraft({ ...draft, sort_order: Number(event.target.value) })}
              />
            </label>
          </div>
        </div>
        {error && <p className="error">{error}</p>}
        <footer className="session-builder-actions">
          {editingId !== null && <button className="admin-ghost" onClick={reset} disabled={busy}>{t('cancel')}</button>}
          <button className="book" onClick={() => { void save() }} disabled={busy}>
            {busy ? t('saving') : editingId === null ? t('add') : t('saveChanges')}
          </button>
        </footer>
      </section>

      <div className="admin-table">
        {bonuses.map(bonus => (
          <article className="admin-row" key={bonus.id}>
            <div className="booking-admin-meta">
              <b>{bonus.title}</b>
              {bonus.title_uz && <span>{bonus.title_uz}</span>}
              <span>{bonus.text || t('none')}</span>
              <span className={bonus.is_active ? 'status-chip live' : 'status-chip muted'}>
                {bonus.is_active ? t('enabled') : t('disabled')}
              </span>
            </div>
            <div className="admin-actions">
              <button className="admin-ghost" onClick={() => edit(bonus)}>{t('edit')}</button>
              <button className="admin-ghost" onClick={() => { void toggle(bonus) }}>
                {bonus.is_active ? t('hide') : t('publish')}
              </button>
              <button className="admin-ghost danger" onClick={() => { void remove(bonus) }}>{t('remove')}</button>
            </div>
          </article>
        ))}
        {!bonuses.length && <p className="empty">{t('noBonuses')}</p>}
      </div>
    </section>
  )
}
