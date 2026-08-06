import { useMemo, useState } from 'react'
import {
  createAdminMovie,
  deleteAdminMovie,
  updateAdminMovie,
  type MovieDetail,
  type MoviePayload,
} from './api'
import AdminMovieForm from './AdminMovieForm'
import { formatMoney, useI18n } from './i18n'

const emptyMovie = (): MoviePayload => ({
  title: '',
  genre: '',
  description: '',
  poster: '',
  trailer_id: '',
  duration: 90,
  age: 12,
  year: new Date().getFullYear(),
  country: '',
  director: '',
  cast: [],
  gallery: [],
  imdb: 0,
  kinopoisk: 0,
  internal_rating: null,
  ticket_price: null,
  is_published: true,
  sort_order: 0,
})

const includes = (source: string, query: string) => source.toLowerCase().includes(query.trim().toLowerCase())
const toMoviePayload = (movie: MovieDetail): MoviePayload => ({
  title: movie.title,
  genre: movie.genre,
  description: movie.description,
  poster: movie.poster,
  trailer_id: movie.trailer_id,
  duration: movie.duration,
  age: movie.age,
  year: movie.year,
  country: movie.country,
  director: movie.director,
  cast: movie.cast,
  gallery: movie.gallery,
  imdb: movie.imdb,
  kinopoisk: movie.kinopoisk,
  internal_rating: movie.internal_rating,
  ticket_price: movie.ticket_price,
  is_published: movie.is_published,
  sort_order: movie.sort_order,
})

type MoviesViewProps = {
  movies: MovieDetail[]
  onSaved: (message: string) => Promise<void>
}

export default function MoviesView({ movies, onSaved }: MoviesViewProps) {
  const { language, t } = useI18n()
  const [query, setQuery] = useState('')
  const [draft, setDraft] = useState<MoviePayload>(emptyMovie)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const rows = useMemo(
    () => movies.filter(movie => includes(`${movie.title} ${movie.genre} ${movie.country} ${movie.director}`, query)),
    [movies, query],
  )

  const startCreate = () => {
    setDraft(emptyMovie())
    setEditingId(null)
    setError('')
    setOpen(true)
  }
  const startEdit = (movie: MovieDetail) => {
    setDraft(toMoviePayload(movie))
    setEditingId(movie.id)
    setError('')
    setOpen(true)
  }
  const save = async () => {
    if (!draft.title.trim() || !draft.genre.trim() || !draft.poster.trim()) {
      setError(t('movieRequired'))
      return
    }
    setBusy(true)
    setError('')
    try {
      const result = editingId === null ? await createAdminMovie(draft) : await updateAdminMovie(editingId, draft)
      setOpen(false)
      await onSaved(result.translation_warning ? t('movieSavedTranslationFallback') : editingId === null ? t('movieCreated') : t('movieSaved'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('movieSaveFailed'))
    } finally {
      setBusy(false)
    }
  }
  const remove = async (movie: MovieDetail) => {
    if (!window.confirm(`${t('deleteMovieConfirm')} "${movie.title}"? ${t('deleteMovieSuffix')}`)) return
    try {
      await deleteAdminMovie(movie.id)
      await onSaved(t('movieDeleted'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('movieSaveFailed'))
    }
  }
  const togglePublish = async (movie: MovieDetail) => {
    try {
      await updateAdminMovie(movie.id, { ...toMoviePayload(movie), is_published: !movie.is_published })
      await onSaved(movie.is_published ? t('movieHidden') : t('moviePublished'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('movieSaveFailed'))
    }
  }

  return (
    <section>
      <div className="section-head admin-page-intro">
        <div>
          <span className="admin-eyebrow">{t('content')}</span>
          <h1>{t('movieCatalog')}</h1>
          <p className="admin-hint">{t('movieCatalogHint')}</p>
        </div>
        <button className="book fit admin-primary" onClick={startCreate}>＋ {t('addMovie')}</button>
      </div>
      <label className="admin-search">
        <span>⌕</span>
        <input value={query} onChange={event => setQuery(event.target.value)} placeholder={t('movieSearchAdminPlaceholder')} />
      </label>
      <div className="admin-movie-grid">
        {rows.map(movie => (
          <article className="admin-movie-card" key={movie.id}>
            <div className="admin-movie-poster">
              <img src={movie.poster} alt={movie.title} loading="lazy" />
              <span className={movie.is_published ? 'status-chip live' : 'status-chip muted'}>
                {movie.is_published ? t('published') : t('draft')}
              </span>
            </div>
            <div className="admin-movie-body">
              <h2>{movie.title}</h2>
              <p>{movie.genre} · {movie.age}+</p>
              <div className="admin-rating-line"><span>IMDb {movie.imdb}</span><span>{t('kinopoiskShort')} {movie.kinopoisk}</span><span>Nova {movie.internal_rating ?? '—'}</span></div>
              <small>{movie.country} · {movie.year} · {movie.duration} {t('minutes')} · {t('photo')}: {movie.gallery.length}{movie.ticket_price ? ` · ${formatMoney(movie.ticket_price, language)}` : ''}</small>
            </div>
            <div className="admin-card-actions">
              <button className="admin-ghost" onClick={() => startEdit(movie)}>✎ {t('editMovie')}</button>
              <button className="admin-ghost" onClick={() => { void togglePublish(movie) }}>{movie.is_published ? t('hide') : t('publish')}</button>
              <button className="admin-ghost danger" onClick={() => { void remove(movie) }}>{t('remove')}</button>
            </div>
          </article>
        ))}
        {!rows.length && <p className="empty">{t('moviesNotFound')}</p>}
      </div>
      {open && (
        <AdminMovieForm
          draft={draft}
          editing={editingId !== null}
          busy={busy}
          error={error}
          onChange={setDraft}
          onClose={() => setOpen(false)}
          onSave={() => { void save() }}
        />
      )}
    </section>
  )
}
