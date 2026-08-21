import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import Shell from '../../components/Shell'
import { useI18n } from '../../i18n'
import { haptic } from '../../lib/haptic'

// NOTE: this still asks the user to type a time.  Stage 9 replaces it with the
// real screening list from GET /api/movies/{id}/sessions.
export default function TimePage() {
  const { t } = useI18n()
  const { id, date } = useParams()
  const [time, setTime] = useState('19:00')
  const valid = /^([01]\d|2[0-3]):[0-5]\d$/.test(time)

  return (
    <Shell>
      <Link className="back" to={`/booking/${id}/date`}>← {t('date')}</Link>
      <h1>{t('chooseConvenientTime')}</h1>
      <div className="manual-time-card">
        <label>
          <span>{t('preferredTime')}</span>
          <input type="time" value={time} onChange={event => setTime(event.target.value)} />
        </label>
        {!valid && <p className="error">{t('invalidTime')}</p>}
        <Link
          className={`book${valid ? '' : ' disabled-link'}`}
          to={valid ? `/booking/${id}/date/${date}/time/${time}/hall` : '#'}
          onClick={event => { if (!valid) event.preventDefault(); else haptic.select() }}
        >
          {t('continue')}
        </Link>
      </div>
    </Shell>
  )
}
