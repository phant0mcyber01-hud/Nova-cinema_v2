import { useState, type ChangeEvent, type ReactNode } from 'react'
import { lookupAdminMovie, uploadAdminImage, type MoviePayload } from '../../api'
import Icon from '../../components/Icon'
import { useI18n } from '../../i18n'

type MovieFormProps = {
  draft: MoviePayload
  editing: boolean
  busy: boolean
  error: string
  onChange: (value: MoviePayload) => void
  onClose: () => void
  onSave: () => void
}

type FieldProps = {
  label: string
  hint?: string
  children: ReactNode
  wide?: boolean
}

function Field({ label, hint, children, wide = false }: FieldProps) {
  return (
    <label className={`cms-field${wide ? ' wide' : ''}`}>
      <b>{label}</b>
      {hint && <small>{hint}</small>}
      {children}
    </label>
  )
}

const fromLines = (value: string) => value.split('\n').map(item => item.trim()).filter(Boolean)
const toLines = (value: string[]) => value.join('\n')

export default function AdminMovieForm({ draft, editing, busy, error, onChange, onClose, onSave }: MovieFormProps) {
  const { t } = useI18n()
  const [posterMode, setPosterMode] = useState<'upload' | 'url'>(draft.poster && !draft.poster.startsWith('/uploads/') ? 'url' : 'upload')
  const [galleryUrl, setGalleryUrl] = useState('')
  const [uploading, setUploading] = useState(false)
  const [lookupTitle, setLookupTitle] = useState(draft.title)
  const [lookupBusy, setLookupBusy] = useState(false)
  const [lookupMessage, setLookupMessage] = useState('')

  const uploadPoster = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const result = await uploadAdminImage(file)
      onChange({ ...draft, poster: result.url })
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }
  const uploadGallery = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    if (!files.length) return
    setUploading(true)
    try {
      const uploaded = await Promise.all(files.map(file => uploadAdminImage(file)))
      onChange({ ...draft, gallery: [...draft.gallery, ...uploaded.map(item => item.url)] })
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }
  const addGalleryUrl = () => {
    const url = galleryUrl.trim()
    if (!url) return
    onChange({ ...draft, gallery: [...draft.gallery, url] })
    setGalleryUrl('')
  }
  const removeGallery = (index: number) => onChange({ ...draft, gallery: draft.gallery.filter((_, current) => current !== index) })
  const moveGallery = (index: number, step: -1 | 1) => {
    const nextIndex = index + step
    if (nextIndex < 0 || nextIndex >= draft.gallery.length) return
    const gallery = [...draft.gallery]
    ;[gallery[index], gallery[nextIndex]] = [gallery[nextIndex], gallery[index]]
    onChange({ ...draft, gallery })
  }
  const lookupMovie = async () => {
    const title = lookupTitle.trim()
    if (!title) return
    setLookupBusy(true)
    setLookupMessage('')
    try {
      const result = await lookupAdminMovie(title)
      onChange(result)
      setPosterMode(result.poster && !result.poster.startsWith('/uploads/') ? 'url' : 'upload')
      setLookupMessage(t('movieLookupApplied'))
    } catch (reason) {
      setLookupMessage(reason instanceof Error ? reason.message : t('movieLookupFailed'))
    } finally {
      setLookupBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
      <section className="modal cms-modal" role="dialog" aria-modal="true" aria-label={editing ? t('editMovieLabel') : t('createMovieLabel')}>
        <header className="cms-modal-head">
          <div><span className="admin-eyebrow">{t('movieEditor')}</span><h2>{editing ? t('editMovie') : t('newMovie')}</h2></div>
          <button className="admin-ghost cms-close" onClick={onClose} aria-label={t('close')}>×</button>
        </header>

        <div className="cms-sections">
          <section className="cms-section movie-lookup-section">
            <div className="cms-section-title"><span><Icon name="search" /></span><div><h3>{t('findMovie')}</h3><p>{t('movieLookupHint')}</p></div></div>
            <div className="movie-lookup-row">
              <input value={lookupTitle} onChange={event => setLookupTitle(event.target.value)} placeholder={t('movieLookupPlaceholder')} />
              <button className="book fit" onClick={() => { void lookupMovie() }} disabled={lookupBusy}>{lookupBusy ? t('searching') : t('findMovie')}</button>
            </div>
            {lookupMessage && <p className={lookupMessage === t('movieLookupApplied') ? 'toast' : 'error'}>{lookupMessage}</p>}
          </section>

          <section className="cms-section">
            <div className="cms-section-title"><span>1</span><div><h3>{t('mainInfo')}</h3><p>{t('mainInfoHint')}</p></div></div>
            <div className="cms-fields">
              <Field label={t('movieTitle')} hint={t('movieTitleHint')} wide>
                <input value={draft.title} onChange={event => onChange({ ...draft, title: event.target.value })} placeholder={t('movieTitlePlaceholder')} />
              </Field>
              <Field label={t('description')} hint={t('descriptionHint')} wide>
                <textarea value={draft.description} onChange={event => onChange({ ...draft, description: event.target.value })} placeholder={t('descriptionPlaceholder')} />
              </Field>
              <Field label={t('genres')} hint={t('genresHint')}>
                <input value={draft.genre} onChange={event => onChange({ ...draft, genre: event.target.value })} placeholder={t('genrePlaceholder')} />
              </Field>
              <Field label={t('ageLimit')}>
                <div className="input-with-suffix"><input type="number" min="0" max="21" value={draft.age} onChange={event => onChange({ ...draft, age: Number(event.target.value) })} /><span>+</span></div>
              </Field>
              <Field label={t('duration')}>
                <div className="input-with-suffix"><input type="number" min="1" value={draft.duration} onChange={event => onChange({ ...draft, duration: Number(event.target.value) })} /><span>{t('minutes')}</span></div>
              </Field>
              <Field label={t('country')}>
                <input value={draft.country} onChange={event => onChange({ ...draft, country: event.target.value })} placeholder={t('countryPlaceholder')} />
              </Field>
              <Field label={t('releaseYear')}>
                <input type="number" min="1888" max="2100" value={draft.year} onChange={event => onChange({ ...draft, year: Number(event.target.value) })} placeholder="2026" />
              </Field>
              <Field label={t('director')}>
                <input value={draft.director} onChange={event => onChange({ ...draft, director: event.target.value })} placeholder={t('directorPlaceholder')} />
              </Field>
              <Field label={t('castLabel')} hint={t('castHint')} wide>
                <textarea value={toLines(draft.cast)} onChange={event => onChange({ ...draft, cast: fromLines(event.target.value) })} placeholder={t('castPlaceholder')} />
              </Field>
              <Field label={t('audioLanguages')} hint={t('audioLanguagesHint')} wide>
                <div className="audio-language-options">
                  {(['ru', 'uz'] as const).map(code => {
                    const active = draft.audio_languages.includes(code)
                    return (
                      <button
                        type="button"
                        key={code}
                        className={active ? 'active' : ''}
                        onClick={() => onChange({
                          ...draft,
                          audio_languages: active
                            ? draft.audio_languages.filter(item => item !== code)
                            : [...draft.audio_languages, code],
                        })}
                      >
                        {code === 'ru' ? t('audioLanguageRu') : t('audioLanguageUz')}
                      </button>
                    )
                  })}
                </div>
              </Field>
            </div>
          </section>

          <section className="cms-section">
            <div className="cms-section-title"><span>2</span><div><h3>{t('media')}</h3><p>{t('mediaHint')}</p></div></div>
            <div className="poster-editor cms-media-card">
              <div className="media-card-head"><div><b>{t('mainPoster')}</b><small>{t('mainPosterHint')}</small></div></div>
              {draft.poster ? <img className="poster-preview" src={draft.poster} alt={t('posterPreviewAlt')} /> : <div className="poster-placeholder"><span>＋</span><b>{t('posterEmpty')}</b></div>}
              <div className="segmented-control">
                <button className={posterMode === 'upload' ? 'active' : ''} onClick={() => setPosterMode('upload')}>{t('uploadImage')}</button>
                <button className={posterMode === 'url' ? 'active' : ''} onClick={() => setPosterMode('url')}>{t('pasteLink')}</button>
              </div>
              {posterMode === 'upload' ? (
                <label className="admin-upload">{uploading ? t('uploading') : t('chooseImage')}<input type="file" accept="image/*" onChange={event => { void uploadPoster(event) }} disabled={uploading} /></label>
              ) : (
                <input value={draft.poster} onChange={event => onChange({ ...draft, poster: event.target.value })} placeholder="https://example.com/poster.jpg" inputMode="url" />
              )}
            </div>

            <div className="gallery-editor cms-media-card">
              <div className="media-card-head"><div><b>{t('gallery')}</b><small>{t('galleryHint')}</small></div><span>{draft.gallery.length} {t('photo')}</span></div>
              <div className="gallery-add-row">
                <label className="admin-upload">＋ {t('addPhoto')}<input type="file" accept="image/*" multiple onChange={event => { void uploadGallery(event) }} disabled={uploading} /></label>
                <details><summary>{t('addByLink')}</summary><div><input value={galleryUrl} onChange={event => setGalleryUrl(event.target.value)} placeholder={t('imageUrl')} /><button className="admin-ghost" onClick={addGalleryUrl}>{t('add')}</button></div></details>
              </div>
              <div className="gallery-grid">
                {draft.gallery.map((image, index) => (
                  <article key={`${image}-${index}`}>
                    <a href={image} target="_blank" rel="noreferrer"><img src={image} alt={`${t('photoAlt')} ${index + 1}`} loading="lazy" /></a>
                    <span>{index + 1}</span>
                    <div className="gallery-actions">
                      <button onClick={() => moveGallery(index, -1)} disabled={index === 0} aria-label={t('previousPage')}>←</button>
                      <button onClick={() => moveGallery(index, 1)} disabled={index === draft.gallery.length - 1} aria-label={t('nextPage')}>→</button>
                      <button className="danger" onClick={() => removeGallery(index)} aria-label={t('deletePhoto')}>×</button>
                    </div>
                  </article>
                ))}
              </div>
              {!draft.gallery.length && <p className="empty compact">{t('galleryEmpty')}</p>}
            </div>

            <Field label={`${t('trailer')} YouTube`} hint={t('youtubeHint')} wide>
              <input value={draft.trailer_id} onChange={event => onChange({ ...draft, trailer_id: event.target.value })} placeholder="https://youtube.com/watch?v=…" inputMode="url" />
            </Field>
          </section>

          <section className="cms-section">
            <div className="cms-section-title"><span>3</span><div><h3>{t('ratingsAndPrice')}</h3><p>{t('ratingsHint')}</p></div></div>
            <div className="cms-fields three">
              <Field label="IMDb"><input type="number" min="0" max="10" step="0.1" value={draft.imdb} onChange={event => onChange({ ...draft, imdb: Number(event.target.value) })} placeholder="8.7" /></Field>
              <Field label={t('kinopoisk')}><input type="number" min="0" max="10" step="0.1" value={draft.kinopoisk} onChange={event => onChange({ ...draft, kinopoisk: Number(event.target.value) })} placeholder="8.4" /></Field>
              <Field label={t('internalRatingNova')} hint={t('internalRatingHint')}><input type="number" min="0" max="10" step="0.1" value={draft.internal_rating ?? ''} onChange={event => onChange({ ...draft, internal_rating: event.target.value ? Number(event.target.value) : null })} placeholder="8.5" /></Field>
              <Field label={t('movieTicketPrice')} hint={t('movieTicketPriceHint')}><div className="input-with-suffix"><input type="number" min="1" value={draft.ticket_price ?? ''} onChange={event => onChange({ ...draft, ticket_price: event.target.value ? Number(event.target.value) : null })} placeholder={t('notSet')} /><span>{t('currency')}</span></div></Field>
            </div>
          </section>

          <section className="cms-section publication-section">
            <div className="cms-section-title"><span>4</span><div><h3>{t('publication')}</h3><p>{t('publicationHint')}</p></div></div>
            <div className="publication-options">
              <button className={draft.is_published ? 'active' : ''} onClick={() => onChange({ ...draft, is_published: true })}><b>{t('publishMovie')}</b><small>{t('publishMovieHint')}</small></button>
              <button className={!draft.is_published ? 'active' : ''} onClick={() => onChange({ ...draft, is_published: false })}><b>{t('saveAsDraft')}</b><small>{t('saveAsDraftHint')}</small></button>
            </div>
            <div className="publication-options">
              <button className={draft.is_new ? 'active' : ''} onClick={() => onChange({ ...draft, is_new: true })}><b>{t('markAsNew')}</b><small>{t('newReleasesHint')}</small></button>
              <button className={!draft.is_new ? 'active' : ''} onClick={() => onChange({ ...draft, is_new: false, new_until: '' })}><b>{t('unmarkNew')}</b><small>{t('newUntilHint')}</small></button>
            </div>
            {draft.is_new && (
              <Field label={t('newUntil')} hint={t('newUntilHint')}>
                <input type="date" value={draft.new_until} onChange={event => onChange({ ...draft, new_until: event.target.value })} />
              </Field>
            )}
            <div className="publication-options">
              <button className={draft.is_hit ? 'active' : ''} onClick={() => onChange({ ...draft, is_hit: true })}><b>{t('markAsHit')}</b><small>{t('hitsSectionHint')}</small></button>
              <button className={!draft.is_hit ? 'active' : ''} onClick={() => onChange({ ...draft, is_hit: false })}><b>{t('unmarkHit')}</b><small>{t('hitsSectionHint')}</small></button>
            </div>
            <Field label={t('catalogPosition')} hint={t('catalogPositionHint')}><input type="number" value={draft.sort_order} onChange={event => onChange({ ...draft, sort_order: Number(event.target.value) })} placeholder="0" /></Field>
          </section>
        </div>

        {error && <p className="error">{error}</p>}
        <footer className="cms-modal-footer">
          <button className="admin-ghost" onClick={onClose} disabled={busy}>{t('cancel')}</button>
          <button className="book" onClick={onSave} disabled={busy || uploading}>{busy ? t('saving') : editing ? t('saveChanges') : t('addMovie')}</button>
        </footer>
      </section>
    </div>
  )
}
