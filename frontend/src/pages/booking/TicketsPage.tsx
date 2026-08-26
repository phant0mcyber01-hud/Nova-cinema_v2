import WebApp from '@twa-dev/sdk'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  confirmBooking,
  getBookingDates,
  getBookingSlots,
  getProfile,
  holdBooking,
  releaseBookingHold,
  type BookingDate,
  type BookingHold,
  type BookingSlot,
} from '../../api'
import Shell from '../../components/Shell'
import AdminContacts from '../../components/AdminContacts'
import { formatDateParts, formatMoney, setCurrency, useI18n } from '../../i18n'
import { apiMessage } from '../../lib/apiMessage'
import { haptic } from '../../lib/haptic'

/**
 * The only way to book: pick a day, pick one of the cinema's fixed times, say
 * how many people are coming. The film is agreed with the administrator later,
 * the places are allocated by the backend, and payment happens by hand.
 */

const text = {
  ru: {
    title: 'Билеты',
    date: 'Выберите дату',
    time: 'Выберите время',
    guests: 'Количество гостей',
    left: 'Осталось {n} из {total}',
    full: 'Мест нет',
    next: 'Продолжить',
    back: 'Изменить',
    contacts: 'Контакты и итог',
    first: 'Имя',
    last: 'Фамилия',
    phone: 'Телефон',
    telegram: 'Telegram',
    comment: 'Комментарий (необязательно)',
    perPerson: 'за одного человека',
    total: 'Итого',
    send: 'Отправить заявку',
    pending:
      'Это заявка, а не оплаченный билет. Администратор свяжется с вами, согласует фильм, отправит реквизиты, получит перевод и подтвердит бронь.',
    seatsNote: 'Места распределяются автоматически — выбирать ряд и кресло не нужно.',
    holdNote: 'Места удерживаются {n} мин, пока вы заполняете форму.',
    empty: 'Доступных дат пока нет',
    refresh: 'Свободных мест стало меньше. Проверьте количество гостей.',
  },
  uz: {
    title: 'Chiptalar',
    date: 'Sanani tanlang',
    time: 'Vaqtni tanlang',
    guests: 'Mehmonlar soni',
    left: '{total} tadan {n} ta qoldi',
    full: "Joy yo'q",
    next: 'Davom etish',
    back: "O'zgartirish",
    contacts: 'Aloqa va yakun',
    first: 'Ism',
    last: 'Familiya',
    phone: 'Telefon',
    telegram: 'Telegram',
    comment: 'Izoh (ixtiyoriy)',
    perPerson: 'bir kishi uchun',
    total: 'Jami',
    send: 'Ariza yuborish',
    pending:
      "Bu to'langan chipta emas, ariza. Administrator siz bilan bog'lanadi, filmni kelishadi, rekvizitlarni yuboradi, o'tkazmani qabul qiladi va bronni tasdiqlaydi.",
    seatsNote: "Joylar avtomatik taqsimlanadi — qator va o'rindiqni tanlash shart emas.",
    holdNote: "Siz shaklni to'ldirguningizcha joylar {n} daqiqa saqlanadi.",
    empty: "Hozircha bo'sh sana yo'q",
    refresh: "Bo'sh joylar kamaydi. Mehmonlar sonini tekshiring.",
  },
} as const

/** The 3x4 hall picture. Decoration only: nobody picks a chair. */
function HallPreview({ filled, capacity }: { filled: number; capacity: number }) {
  return (
    <div className="availability-grid" aria-hidden="true">
      {Array.from({ length: 12 }, (_, index) => (
        <i className={index < filled ? 'filled' : index >= capacity ? 'unavailable' : ''} key={index} />
      ))}
    </div>
  )
}

/**
 * One day of the calendar strip: weekday, day number and month on their own
 * lines, plus a fill meter -- how much of the hall this day still has free,
 * read straight off the same `available`/`capacity` the text label uses.
 * A full day is shown, not hidden, so the viewer sees the whole week at a
 * glance instead of days quietly vanishing from the strip.
 */
function DateChip({
  date, language, active, full, available, capacity, label, onSelect,
}: {
  date: string
  language: 'ru' | 'uz'
  active: boolean
  full: boolean
  available: number
  capacity: number
  label: string
  onSelect: () => void
}) {
  const parts = formatDateParts(date, language)
  const fill = capacity > 0 ? Math.max(0, Math.min(1, available / capacity)) : 0
  return (
    <button
      className={`date-chip${active ? ' active' : ''}${full ? ' full' : ''}`}
      disabled={full}
      onClick={onSelect}
    >
      <span className="date-chip-weekday">{parts.weekday}</span>
      <span className="date-chip-day">{parts.day}</span>
      <span className="date-chip-month">{parts.month}</span>
      <span className="date-chip-meter" aria-hidden="true">
        <i style={{ width: `${fill * 100}%` }} />
      </span>
      <small>{label}</small>
    </button>
  )
}

export default function TicketsPage() {
  const { language } = useI18n()
  const copy = text[language]
  const navigate = useNavigate()

  const [dates, setDates] = useState<BookingDate[] | null>(null)
  const [date, setDate] = useState('')
  const [slots, setSlots] = useState<BookingSlot[]>([])
  const [slot, setSlot] = useState<BookingSlot | null>(null)
  const [capacity, setCapacity] = useState(12)
  const [price, setPrice] = useState(0)
  const [partySize, setPartySize] = useState(1)
  const [hold, setHold] = useState<BookingHold | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submitting = useRef(false)
  const [contact, setContact] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    telegram_username: WebApp.initDataUnsafe.user?.username ?? '',
    comment: '',
  })

  const loadSlots = useCallback(async (chosenDate: string, resumed = false) => {
    if (!chosenDate) return
    try {
      const result = await getBookingSlots(chosenDate)
      setCapacity(result.capacity)
      setPrice(result.price)
      setCurrency(result.currency)
      setSlots(result.slots)
      setSlot(current => {
        if (!current) return null
        const refreshed = result.slots.find(item => item.time === current.time) ?? null
        if (refreshed) {
          setPartySize(size => Math.max(1, Math.min(size, refreshed.available + refreshed.mine)))
        }
        return refreshed
      })
      if (resumed) setError(copy.refresh)
    } catch (reason) {
      setError(apiMessage(reason, 'serverError'))
    }
  }, [copy.refresh])

  useEffect(() => {
    void getBookingDates()
      .then(result => {
        setDates(result.dates)
        setCapacity(result.capacity)
        setPrice(result.price)
        setCurrency(result.currency)
      })
      .catch(reason => setError(apiMessage(reason, 'serverError')))
    void getProfile()
      .then(profile =>
        setContact(current => ({
          ...current,
          first_name: profile.first_name,
          last_name: profile.last_name,
          phone: profile.phone,
        })),
      )
      .catch(() => undefined)
  }, [])

  useEffect(() => { if (date) void loadSlots(date) }, [date, loadSlots])

  // Coming back to a backgrounded Mini App: somebody may have taken the places.
  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === 'visible' && date) void loadSlots(date, true)
    }
    document.addEventListener('visibilitychange', refresh)
    return () => document.removeEventListener('visibilitychange', refresh)
  }, [date, loadSlots])

  const createHold = async () => {
    if (!slot || busy) return
    setBusy(true)
    try {
      const result = await holdBooking({ date, time: slot.time, party_size: partySize })
      setHold(result)
      setCapacity(result.capacity)
      setPrice(result.ticket_price)
      setError('')
      haptic.select()
    } catch (reason) {
      setError(apiMessage(reason, 'failedBooking'))
      void loadSlots(date)
    } finally {
      setBusy(false)
    }
  }

  /** Editing the party means the current claim is wrong — give it back. */
  const cancelHold = async () => {
    if (!hold) return
    setHold(null)
    try {
      await releaseBookingHold(hold.date, hold.time)
    } catch { /* the hold expires on its own anyway */ }
    void loadSlots(date)
  }

  const submit = async () => {
    if (!hold || submitting.current || busy) return
    if (!contact.first_name.trim() || !contact.last_name.trim() || !contact.phone.trim()) {
      setError(apiMessage(new Error('Required'), 'userInfoRequired'))
      return
    }
    submitting.current = true
    setBusy(true)
    try {
      const result = await confirmBooking({
        date: hold.date,
        time: hold.time,
        party_size: hold.party_size,
        ...contact,
      })
      haptic.success()
      navigate(`/booking/success/${result.ticket_code}`)
    } catch (reason) {
      setError(apiMessage(reason, 'failedBooking'))
      submitting.current = false
      setHold(null)
      void loadSlots(date)
    } finally {
      setBusy(false)
    }
  }

  // The viewer's own hold is theirs to re-take, so it is not in their way.
  const maximum = slot ? Math.max(1, Math.min(slot.available + slot.mine, capacity)) : 1
  const left = (value: number) =>
    copy.left.replace('{n}', String(value)).replace('{total}', String(capacity))

  return (
    <Shell>
      <section className="tickets-flow">
        <h1>{copy.title}</h1>
        <p className="ticket-honesty">{copy.pending}</p>

        <h2>{copy.date}</h2>
        {dates === null && <div className="hall-skeleton compact" />}
        {dates?.length === 0 && <p className="empty">{copy.empty}</p>}
        <div className="date-strip">
          {dates?.map(item => (
            <DateChip
              active={date === item.date}
              available={item.available}
              capacity={capacity}
              date={item.date}
              full={item.slots === 0}
              key={item.date}
              label={item.slots ? left(item.available) : copy.full}
              language={language}
              onSelect={() => { haptic.tap(); setDate(item.date); setSlot(null); setHold(null) }}
            />
          ))}
        </div>

        {date && (
          <>
            <h2>{copy.time}</h2>
            <div className="ticket-options">
              {slots.map(item => (
                <button
                  key={item.time}
                  disabled={item.available + item.mine < 1}
                  className={slot?.time === item.time ? 'active' : ''}
                  onClick={() => {
                    haptic.tap()
                    setSlot(item)
                    setPartySize(size => Math.max(1, Math.min(size, item.available + item.mine)))
                    setHold(null)
                  }}
                >
                  <b>{item.time}</b>
                  <small>{item.available + item.mine ? left(item.available + item.mine) : copy.full}</small>
                </button>
              ))}
            </div>
          </>
        )}

        {slot && !hold && (
          <section className="party-card">
            <h2>{copy.guests}</h2>
            <div className="party-selector">
              <button onClick={() => setPartySize(size => Math.max(1, size - 1))} disabled={partySize <= 1}>−</button>
              <b>{partySize}</b>
              <button onClick={() => setPartySize(size => Math.min(maximum, size + 1))} disabled={partySize >= maximum}>+</button>
            </div>
            <HallPreview filled={partySize} capacity={capacity} />
            <p>{left(slot.available + slot.mine)}</p>
            <p className="ticket-note">{copy.seatsNote}</p>
            <div className="summary-total">
              <span>{copy.total}</span>
              <strong>{formatMoney(price * partySize, language)}</strong>
            </div>
            <button className="book" disabled={busy} onClick={() => void createHold()}>{copy.next}</button>
          </section>
        )}

        {hold && (
          <section className="contact-form request-form">
            <h2>{copy.contacts}</h2>
            <p className="ticket-note">
              {hold.time} · {hold.party_size} · {copy.holdNote.replace('{n}', String(hold.expires_in_minutes))}
            </p>
            <input value={contact.first_name} onChange={event => setContact({ ...contact, first_name: event.target.value })} placeholder={copy.first} />
            <input value={contact.last_name} onChange={event => setContact({ ...contact, last_name: event.target.value })} placeholder={copy.last} />
            <input value={contact.phone} onChange={event => setContact({ ...contact, phone: event.target.value })} placeholder={copy.phone} inputMode="tel" />
            <input value={contact.telegram_username} onChange={event => setContact({ ...contact, telegram_username: event.target.value })} placeholder={copy.telegram} />
            <textarea value={contact.comment} onChange={event => setContact({ ...contact, comment: event.target.value })} placeholder={copy.comment} />
            <div className="summary-total">
              <span>{formatMoney(hold.ticket_price, language)} {copy.perPerson}</span>
              <strong>{formatMoney(hold.total, language)}</strong>
            </div>
            <button className="book" disabled={busy} onClick={() => void submit()}>{copy.send}</button>
            <button className="admin-ghost" disabled={busy} onClick={() => void cancelHold()}>{copy.back}</button>
          </section>
        )}

        <AdminContacts />
        {error && <p className="error">{error}</p>}
      </section>
    </Shell>
  )
}
