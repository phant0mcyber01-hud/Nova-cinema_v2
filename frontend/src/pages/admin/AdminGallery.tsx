import { useRef, useState } from 'react'

import {
  createAdminImage,
  deleteAdminImage,
  updateAdminImage,
  uploadAdminImage,
  type AdminGalleryImage,
  type AdminGalleryImagePayload,
} from '../../api'
import { useI18n } from '../../i18n'

type GalleryViewProps = {
  images: AdminGalleryImage[]
  onSaved: (message: string) => Promise<void>
}

const emptyImage = (): AdminGalleryImagePayload => ({
  image_url: '',
  caption: '',
  caption_uz: '',
  sort_order: 0,
})

const toPayload = (image: AdminGalleryImage): AdminGalleryImagePayload => ({
  image_url: image.image_url,
  caption: image.caption,
  caption_uz: image.caption_uz,
  sort_order: image.sort_order,
})

/** Spec 16: interior, hall and bar photos — no prices, no bar orders. */
export default function GalleryView({ images, onSaved }: GalleryViewProps) {
  const { t } = useI18n()
  const [draft, setDraft] = useState<AdminGalleryImagePayload>(emptyImage)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  const reset = () => {
    setDraft(emptyImage())
    setEditingId(null)
    setError('')
    if (fileInput.current) fileInput.current.value = ''
  }

  const upload = async (file: File) => {
    setBusy(true)
    setError('')
    try {
      const { url } = await uploadAdminImage(file)
      setDraft(current => ({ ...current, image_url: url }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
    } finally {
      setBusy(false)
    }
  }

  const save = async () => {
    if (!draft.image_url.trim()) {
      setError(t('imageRequired'))
      return
    }
    setBusy(true)
    setError('')
    try {
      if (editingId === null) await createAdminImage(draft)
      else await updateAdminImage(editingId, draft)
      reset()
      await onSaved(t('imageSaved'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
    } finally {
      setBusy(false)
    }
  }

  const edit = (image: AdminGalleryImage) => {
    setDraft(toPayload(image))
    setEditingId(image.id)
    setError('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const remove = async (image: AdminGalleryImage) => {
    if (!window.confirm(`${t('deleteImageConfirm')} #${image.id}?`)) return
    try {
      await deleteAdminImage(image.id)
      if (editingId === image.id) reset()
      await onSaved(t('imageDeleted'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
    }
  }

  return (
    <section>
      <div className="admin-page-intro">
        <span className="admin-eyebrow">{t('media')}</span>
        <h1>{t('cinemaGallery')}</h1>
        <p className="admin-hint">{t('cinemaGalleryHint')}</p>
      </div>

      <section className="session-builder">
        <header>
          <span>{editingId === null ? t('addPhoto') : t('edit')}</span>
          <b>{editingId === null ? t('cinemaGallery') : `#${editingId}`}</b>
        </header>
        <div className="session-step">
          <div className="session-step-body session-options">
            <label>
              <b>{t('chooseImage')}</b><small>{t('uploadImage')}</small>
              <input
                ref={fileInput}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                disabled={busy}
                onChange={event => {
                  const file = event.target.files?.[0]
                  if (file) void upload(file)
                }}
              />
            </label>
            <label>
              <b>{t('imageUrl')}</b><small>/uploads/…</small>
              <input value={draft.image_url} onChange={event => setDraft({ ...draft, image_url: event.target.value })} />
            </label>
            <label>
              <b>{t('photoCaption')}</b><small>{t('russianVersion')}</small>
              <input value={draft.caption} onChange={event => setDraft({ ...draft, caption: event.target.value })} />
            </label>
            <label>
              <b>{t('photoCaption')}</b><small>{t('uzbekVersion')}</small>
              <input value={draft.caption_uz} onChange={event => setDraft({ ...draft, caption_uz: event.target.value })} />
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
        {draft.image_url && <img className="admin-image-preview" src={draft.image_url} alt={t('photo')} />}
        {error && <p className="error">{error}</p>}
        <footer className="session-builder-actions">
          {editingId !== null && <button className="admin-ghost" onClick={reset} disabled={busy}>{t('cancel')}</button>}
          <button className="book" onClick={() => { void save() }} disabled={busy}>
            {busy ? t('uploading') : editingId === null ? t('add') : t('saveChanges')}
          </button>
        </footer>
      </section>

      <div className="admin-movie-grid">
        {images.map(image => (
          <article className="admin-movie-card" key={image.id}>
            <div className="admin-movie-poster">
              <img src={image.image_url} alt={image.caption || t('photo')} loading="lazy" />
            </div>
            <div className="admin-movie-body">
              <h2>{image.caption || `#${image.id}`}</h2>
              {image.caption_uz && <p>{image.caption_uz}</p>}
              <small>{t('catalogPosition')}: {image.sort_order}</small>
            </div>
            <div className="admin-card-actions">
              <button className="admin-ghost" onClick={() => edit(image)}>✎ {t('edit')}</button>
              <button className="admin-ghost danger" onClick={() => { void remove(image) }}>{t('remove')}</button>
            </div>
          </article>
        ))}
        {!images.length && <p className="empty">{t('noImages')}</p>}
      </div>
    </section>
  )
}
