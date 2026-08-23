# Nova Cinema Runbook

## Release Checklist

1. Fill `.env` from `.env.example`.
2. Set `BOT_TOKEN`, `WEBAPP_URL`, `ADMIN_TELEGRAM_IDS`, `JWT_SECRET`, and PostgreSQL credentials.
3. Run migrations:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

4. Run local checks:

```powershell
.\.venv\Scripts\python.exe -m pytest
Set-Location frontend
npm run lint -- --max-warnings=0
npm run build
```

5. Start with Docker:

```powershell
docker compose up --build
```

## Operational Notes

- Admin access is controlled by `ADMIN_TELEGRAM_IDS`; changing the value and re-authenticating updates the user role.
- Everything the cinema shows is stored in the database, not in code: the `cinema_settings` row holds the name,
  address, phone, Telegram/Instagram links, geo, work hours, currency, ticket price, hall size and booking rules.
  `GET /api/settings` serves it to the Mini App; `PUT /api/admin/settings` updates it.
- Price priority is show price, movie price, global base price. The unit price is frozen on the booking row at
  request time, so changing the price never rewrites existing bookings. A freeform time matches no `shows` row,
  so it is priced from the movie or the base price - never a failure.
- The schedule lives in `shows` and gates the dates, not the hours: a movie is bookable only on a day that has
  an active screening, and on such a day the viewer may request any well-formed HH:MM. Rejected with 404 are a
  malformed time, a past date, a time already started in the cinema's own clock, and a day with no screening.
- Double booking is prevented by `uq_seat_hold` on (movie_id, show_date, session, seat) plus the rule that
  `/api/bookings/confirm` needs a live hold. `session` stores the requested time verbatim, so two viewers
  wanting one seat at the same hour collide with 409 while different hours never conflict.
- Booking lifecycle: `pending` -> `contacting` -> `confirmed` -> `watched`, with `cancelled` at any point.
  Cancelling frees the seats; every other status keeps them. QR is valid for `confirmed` and `watched`.
- One hall only. Its size comes from `hall_rows` x `hall_cols` in settings (seeded to the real 3x5 = 15 seats).
- At most three melodies can exist; the API rejects the fourth with 409.
- Uploaded images live under `UPLOAD_DIR` in local mode and the `uploads` Docker volume in Compose.
- Telegram Mini Apps require a public HTTPS frontend URL.
- `CORS_ORIGINS` is normalised on load: a trailing slash is stripped, so `https://host/` and `https://host` both work.
- An empty `DATABASE_URL` falls back to local SQLite instead of failing at import.

## Useful Commands

```powershell
.\.venv\Scripts\alembic.exe heads
.\.venv\Scripts\alembic.exe history
docker compose logs -f api
docker compose logs -f frontend
docker compose exec api alembic current
```
