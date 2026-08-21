import WebApp from '@twa-dev/sdk'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { confirmBooking, getHall, holdSeats, type Hall } from '../../api'
import Shell from '../../components/Shell'
import { formatMoney, setCurrency, translate, useI18n } from '../../i18n'
import { rowLabel, seatLabel } from '../../lib/hall'
import { haptic } from '../../lib/haptic'

const REFRESH_INTERVAL_MS = 15_000

export default function HallPage() {
  const { language, t } = useI18n()
  const { id, date, time } = useParams()
  const navigate = useNavigate()
  const [hall, setHall] = useState<Hall | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [contact, setContact] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    telegram_username: WebApp.initDataUnsafe.user?.username ?? '',
    comment: '',
  })

  const loadHall = useCallback(async () => {
    if (!id || !date || !time) return
    try {
      const nextHall = await getHall(Number(id), date, time)
      setCurrency(nextHall.currency)
      setHall(nextHall)
      setSelected(current => current.filter(seat => !nextHall.taken.includes(seat)))
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : translate('failedRefreshHall'))
    }
  }, [date, id, time])

  useEffect(() => {
    void loadHall()
    const intervalId = window.setInterval(() => { void loadHall() }, REFRESH_INTERVAL_MS)
    return () => window.clearInterval(intervalId)
  }, [loadHall])

  const toggleSeat = (seat: string) => {
    if (hall?.taken.includes(seat)) return
    haptic.select()
    setSelected(current => (
      current.includes(seat)
        ? current.filter(item => item !== seat)
        : current.length < (hall?.max_seats ?? 1) ? [...current, seat] : current
    ))
  }

  const reserve = useCallback(async () => {
    if (!id || !date || !time || !selected.length) return
    if (!contact.first_name.trim() || !contact.last_name.trim() || !contact.phone.trim()) {
      setError(t('userInfoRequired'))
      haptic.error()
      return
    }
    setBusy(true)
    setError('')
    try {
      const payload = { movie_id: Number(id), show_date: date, session: time, seats: selected }
      await holdSeats(payload)
      const result = await confirmBooking({ ...payload, ...contact })
      haptic.success()
      navigate(`/booking/success/${result.ticket_code}`)
    } catch (reason) {
      haptic.error()
      setError(reason instanceof Error ? reason.message : t('failedBooking'))
      void loadHall()
    } finally {
      setBusy(false)
    }
  }, [contact, date, id, loadHall, navigate, selected, t, time])

  useEffect(() => {
    if (!hall || !selected.length || busy) {
      WebApp.MainButton.hide()
      return
    }
    WebApp.MainButton.setText(`${t('continue')} · ${formatMoney(selected.length * hall.price, language)}`)
    WebApp.MainButton.show()
    WebApp.MainButton.onClick(reserve)
    return () => {
      WebApp.MainButton.offClick(reserve)
      WebApp.MainButton.hide()
    }
  }, [busy, hall, language, reserve, selected.length, t])

  return (
    <Shell>
      <Link className="back" to={`/booking/${id}/date/${date}/time`}>← {t('sessions')}</Link>
      <section className="hall-page">
        <div className="hall-head">
          <p>NOVA HALL</p>
          <h1>{t('chooseSeats')}</h1>
        </div>
        <div className="legend">
          <span><i /> {t('free')}</span>
          <span><i className="taken" /> {t('taken')}</span>
          <span><i className="selected" /> {t('selected')}</span>
        </div>
        {hall ? (
          <>
            <div className="cinema-screen">
              <span>🎬 {t('screen')}</span>
              <i aria-hidden="true" />
            </div>
            <div className="hall" style={{ ['--seat-count' as string]: String(hall.cols) }}>
              <div className="hall-numbers" aria-hidden="true">
                <span />
                {Array.from({ length: hall.cols }, (_, columnIndex) => (
                  <b key={columnIndex + 1}>{columnIndex + 1}</b>
                ))}
              </div>
              {Array.from({ length: hall.rows }, (_, rowIndex) => (
                <div className="hall-row" key={rowLabel(rowIndex)}>
                  <span className="row-label">{rowLabel(rowIndex)}</span>
                  {Array.from({ length: hall.cols }, (_, columnIndex) => {
                    const seat = `${rowIndex + 1}-${columnIndex + 1}`
                    const taken = hall.taken.includes(seat)
                    const selectedSeat = selected.includes(seat)
                    return (
                      <button
                        key={seat}
                        disabled={taken}
                        onClick={() => toggleSeat(seat)}
                        className={`seat ${taken ? 'taken' : selectedSeat ? 'selected' : ''}`}
                        aria-label={`${t('seats')} ${seatLabel(seat)}`}
                      >
                        {columnIndex + 1}
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
            <div className="contact-form booking-form">
              <input value={contact.first_name} onChange={event => setContact({ ...contact, first_name: event.target.value })} placeholder={t('firstName')} />
              <input value={contact.last_name} onChange={event => setContact({ ...contact, last_name: event.target.value })} placeholder={t('lastName')} />
              <input value={contact.phone} onChange={event => setContact({ ...contact, phone: event.target.value })} placeholder={t('phone')} inputMode="tel" />
              <input value={contact.telegram_username} onChange={event => setContact({ ...contact, telegram_username: event.target.value })} placeholder={t('telegramUsername')} />
              <textarea value={contact.comment} onChange={event => setContact({ ...contact, comment: event.target.value })} placeholder={t('commentOptional')} />
            </div>
            <div className="summary">
              <div>
                <small>{t('selectedSeats')}</small>
                <b>{selected.length ? selected.map(seatLabel).join(', ') : t('noSeatsSelected')}</b>
              </div>
              <strong>{formatMoney(selected.length * hall.price, language)}</strong>
              <button className="book" disabled={!selected.length || busy} onClick={() => void reserve()}>{busy ? t('sendingRequest') : t('continue')}</button>
            </div>
          </>
        ) : <div className="hall-skeleton" />}
        {error && <p className="error">{error}</p>}
      </section>
    </Shell>
  )
}
