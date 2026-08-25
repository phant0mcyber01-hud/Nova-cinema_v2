import { useMemo, useState } from 'react'

import { deleteAdminReview, moderateReview, type AdminReview } from '../../api'
import Icon from '../../components/Icon'
import { formatDateTime, useI18n } from '../../i18n'

type ReviewsViewProps = {
  reviews: AdminReview[]
  onSaved: (message: string) => Promise<void>
}

/** The `approved` flag existed from the start but had no interface behind it. */
export default function ReviewsView({ reviews, onSaved }: ReviewsViewProps) {
  const { language, t } = useI18n()
  const [onlyHidden, setOnlyHidden] = useState(false)
  const [error, setError] = useState('')

  const rows = useMemo(
    () => reviews.filter(review => !onlyHidden || !review.approved),
    [onlyHidden, reviews],
  )

  const moderate = async (review: AdminReview, approved: boolean) => {
    setError('')
    try {
      await moderateReview(review.id, approved)
      await onSaved(approved ? t('reviewApproved') : t('reviewHidden'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
    }
  }

  const remove = async (review: AdminReview) => {
    if (!window.confirm(`${t('deleteReviewConfirm')} #${review.id}? ${t('cannotUndo')}`)) return
    setError('')
    try {
      await deleteAdminReview(review.id)
      await onSaved(t('reviewDeleted'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
    }
  }

  return (
    <section>
      <div className="admin-page-intro">
        <span className="admin-eyebrow">{t('adminReviewsTab')}</span>
        <h1>{t('reviewsModeration')}</h1>
        <p className="admin-hint">{t('reviewsModerationHint')}</p>
      </div>

      <div className="admin-toolbar">
        <button
          className={onlyHidden ? 'admin-ghost active' : 'admin-ghost'}
          onClick={() => setOnlyHidden(!onlyHidden)}
        >
          {t('onlyHidden')}
        </button>
      </div>
      {error && <p className="error">{error}</p>}

      <div className="admin-table">
        {rows.map(review => (
          <article className="admin-row" key={review.id}>
            {review.poster && <img src={review.poster} alt={review.movie ?? ''} loading="lazy" />}
            <div className="booking-admin-meta">
              <b>{review.movie} · <Icon name="star" /> {review.rating}/5</b>
              <span>
                {review.user_name}
                {review.telegram_username ? ` · @${review.telegram_username}` : ''}
              </span>
              <span>{review.text}</span>
              <span>{formatDateTime(review.created_at, language)}</span>
              <span className={review.approved ? 'status-chip live' : 'status-chip muted'}>
                {review.approved ? t('published') : t('draft')}
              </span>
            </div>
            <div className="admin-actions">
              {review.approved
                ? <button className="admin-ghost" onClick={() => { void moderate(review, false) }}>{t('hideReview')}</button>
                : <button className="admin-ghost" onClick={() => { void moderate(review, true) }}>{t('approveReview')}</button>}
              <button className="admin-ghost danger" onClick={() => { void remove(review) }}>{t('remove')}</button>
            </div>
          </article>
        ))}
        {!rows.length && <p className="empty">{t('noReviewsYet')}</p>}
      </div>
    </section>
  )
}
