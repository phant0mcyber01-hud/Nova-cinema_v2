import { useRef, useState } from 'react'

import {
  createAdminMelody,
  deleteAdminMelody,
  updateAdminMelody,
  uploadMelodyFile,
  type AdminMelody,
} from '../../api'
import { useI18n } from '../../i18n'

const MAX_MELODIES = 3

type MelodiesViewProps = {
  melodies: AdminMelody[]
  onSaved: (message: string) => Promise<void>
}

/** Spec 4.7: at most three melodies, uploaded rather than committed to the repo. */
export default function MelodiesView({ melodies, onSaved }: MelodiesViewProps) {
  const { t } = useI18n()
  const [title, setTitle] = useState('')
  const [fileUrl, setFileUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const addInput = useRef<HTMLInputElement>(null)
  const replaceInput = useRef<HTMLInputElement>(null)
  const [replacingId, setReplacingId] = useState<number | null>(null)

  const full = melodies.length >= MAX_MELODIES

  const upload = async (file: File): Promise<string | null> => {
    setBusy(true)
    setError('')
    try {
      return (await uploadMelodyFile(file)).url
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
      return null
    } finally {
      setBusy(false)
    }
  }

  const create = async () => {
    if (!title.trim()) {
      setError(t('melodyRequired'))
      return
    }
    if (!fileUrl) {
      setError(t('melodyFileRequired'))
      return
    }
    setBusy(true)
    setError('')
    try {
      await createAdminMelody({ title: title.trim(), file_url: fileUrl, sort_order: melodies.length })
      setTitle('')
      setFileUrl('')
      if (addInput.current) addInput.current.value = ''
      await onSaved(t('melodySaved'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
    } finally {
      setBusy(false)
    }
  }

  const rename = async (melody: AdminMelody, next: string) => {
    if (!next.trim() || next === melody.title) return
    try {
      await updateAdminMelody(melody.id, { title: next.trim() })
      await onSaved(t('melodySaved'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
    }
  }

  const replace = async (melody: AdminMelody, file: File) => {
    const url = await upload(file)
    if (!url) return
    try {
      await updateAdminMelody(melody.id, { file_url: url })
      await onSaved(t('melodySaved'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
    }
  }

  const remove = async (melody: AdminMelody) => {
    if (!window.confirm(`${t('deleteMelodyConfirm')} "${melody.title}"?`)) return
    try {
      await deleteAdminMelody(melody.id)
      await onSaved(t('melodyDeleted'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
    }
  }

  return (
    <section>
      <div className="admin-page-intro">
        <span className="admin-eyebrow">{t('media')}</span>
        <h1>{t('melodiesManagement')}</h1>
        <p className="admin-hint">{t('melodiesHint')}</p>
      </div>

      <div className="admin-setting">
        <small>{t('addMelody')} · {melodies.length} / {MAX_MELODIES}</small>
        {full && <p className="empty">{t('melodyLimitReached')}</p>}
        {!full && (
          <>
            <input
              value={title}
              onChange={event => setTitle(event.target.value)}
              placeholder={t('melodyTitle')}
              disabled={busy}
            />
            <input
              ref={addInput}
              type="file"
              accept=".mp3,.ogg,.m4a,.wav,audio/*"
              disabled={busy}
              onChange={async event => {
                const file = event.target.files?.[0]
                if (!file) return
                const url = await upload(file)
                if (url) setFileUrl(url)
              }}
            />
            <small>{t('audioFormatHint')}</small>
            {fileUrl && <audio controls src={fileUrl} />}
            <button className="book fit" onClick={() => { void create() }} disabled={busy}>
              {busy ? t('uploading') : t('add')}
            </button>
          </>
        )}
        {error && <p className="error">{error}</p>}
      </div>

      <div className="admin-table">
        {melodies.map(melody => (
          <article className="admin-row" key={melody.id}>
            <div className="booking-admin-meta">
              <label className="admin-inline-field">
                <small>{t('melodyTitle')}</small>
                <input
                  defaultValue={melody.title}
                  onBlur={event => { void rename(melody, event.target.value) }}
                />
              </label>
              <audio controls src={melody.file_url} />
            </div>
            <div className="admin-actions">
              <button
                className="admin-ghost"
                disabled={busy}
                onClick={() => { setReplacingId(melody.id); replaceInput.current?.click() }}
              >
                {t('replaceFile')}
              </button>
              <button className="admin-ghost danger" onClick={() => { void remove(melody) }}>{t('remove')}</button>
            </div>
          </article>
        ))}
        {!melodies.length && <p className="empty">{t('noMelodies')}</p>}
      </div>

      <input
        ref={replaceInput}
        type="file"
        accept=".mp3,.ogg,.m4a,.wav,audio/*"
        hidden
        onChange={async event => {
          const file = event.target.files?.[0]
          const target = melodies.find(item => item.id === replacingId)
          event.target.value = ''
          if (file && target) await replace(target, file)
          setReplacingId(null)
        }}
      />
    </section>
  )
}
