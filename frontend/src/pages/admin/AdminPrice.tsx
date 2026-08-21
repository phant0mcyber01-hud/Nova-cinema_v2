import { useEffect, useState } from 'react'

import type { AdminSettings } from '../../api'
import { formatMoney, useI18n } from '../../i18n'

type PriceViewProps = {
  settings: AdminSettings
  onSave: (price: number) => Promise<void>
}

/** Spec 4.5: current price, currency and status in one obvious place. */
export default function PriceView({ settings, onSave }: PriceViewProps) {
  const { language, t } = useI18n()
  const [price, setPrice] = useState(String(settings.base_ticket_price))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => setPrice(String(settings.base_ticket_price)), [settings.base_ticket_price])

  const next = Number(price)
  const valid = Number.isInteger(next) && next > 0
  const changed = valid && next !== settings.base_ticket_price

  const save = async () => {
    if (!changed) return
    setBusy(true)
    setError('')
    try {
      await onSave(next)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('serverError'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section>
      <div className="admin-page-intro">
        <span className="admin-eyebrow">{t('adminPriceTab')}</span>
        <h1>{t('priceManagement')}</h1>
        <p className="admin-hint">{t('priceManagementHint')}</p>
      </div>

      <div className="admin-cards">
        <article>
          <small>{t('currentBasePrice')}</small>
          <b>{formatMoney(settings.base_ticket_price, language)}</b>
        </article>
        <article>
          <small>{t('currency')}</small>
          <b>{settings.currency}</b>
        </article>
        <article>
          <small>{t('priceStatus')}</small>
          <b><span className="status-chip live">{t('priceActive')}</span></b>
        </article>
      </div>

      <div className="admin-setting">
        <small>{t('newPrice')}</small>
        <div className="input-with-suffix">
          <input
            value={price}
            onChange={event => setPrice(event.target.value.replace(/[^\d]/g, ''))}
            inputMode="numeric"
          />
          <span>{settings.currency}</span>
        </div>
        {!valid && price !== '' && <p className="error">{t('serverError')}</p>}
        {error && <p className="error">{error}</p>}
        <button className="book fit" onClick={() => { void save() }} disabled={!changed || busy}>
          {busy ? t('saving') : t('savePrice')}
        </button>
      </div>
    </section>
  )
}
