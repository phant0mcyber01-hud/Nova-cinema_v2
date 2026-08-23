# Nova Cinema Mini App

Telegram Mini App for Nova Cinema: React frontend, FastAPI backend, Telegram initData auth, JWT roles, async SQLAlchemy, Alembic migrations, PostgreSQL, Docker Compose, and an admin panel.

## Production Stack

- Frontend: React, TypeScript, Vite, Telegram WebApp SDK.
- Backend: FastAPI, Pydantic, JWT, server-side Telegram initData validation.
- Database: PostgreSQL with SQLAlchemy 2.0 async and Alembic.
- Runtime: Docker Compose. Frontend image serves static files with nginx and proxies `/api` and `/uploads` to the API service.

## Project Structure

```
backend/            FastAPI application
  core/             config, startup checks, engine/session, Telegram auth + JWT
  models/           SQLAlchemy tables
  schemas/          Pydantic request models
  services/         catalog, settings, i18n, pricing, hall, deep_link, booking, telegram, tmdb, media, seed
  api/routers/      auth, public, catalog, booking, profile, admin, admin_catalog, admin_content
  main.py           app assembly
app.py              compatibility shim so `uvicorn app:app` keeps working
bot.py              aiogram bot (imports the backend package, not the web layer)
tests/              pytest suite: every stage of the spec, plus the journey end to end
frontend/src/
  api/              typed API client split by domain
  i18n/             ru.ts / uz.ts dictionaries + language context
  components/       Shell, LanguageSwitcher, Telegram controls, admin guard
  pages/            Home, MoviePage, About, booking/*, profile/*, admin/*
  lib/              haptics, hall labels, booking dates, deep links, Telegram theme
```

## Admin-Managed Data

Nothing about the cinema is hardcoded. The admin panel owns movies, new-release flags, the `shows` schedule,
the ticket price and currency, bonuses, melodies (max 3), gallery images, the hall size and the booking rules,
plus the contact block used by both the Mini App and the bot. Environment variables only carry secrets and
infrastructure settings; `DEFAULT_*` constants seed the settings row once and are never read afterwards.

## Environment

Copy the template and fill secrets:

```powershell
Copy-Item .env.example .env
```

Required variables:

- `BOT_TOKEN`: Telegram bot token from BotFather.
- `WEBAPP_URL`: public HTTPS URL configured for the bot.
- `ADMIN_TELEGRAM_IDS`: comma-separated Telegram IDs with admin access.
- `JWT_SECRET`: long random secret for JWT signing.
- `POSTGRES_PASSWORD`: PostgreSQL password.
- `CORS_ORIGINS`: allowed frontend origins.
- `TELEGRAM_AUTH_MAX_AGE_SECONDS`: max accepted initData age, default `86400`.
- `UPLOAD_DIR`: local upload directory for API runtime, default `uploads`.
- `TMDB_API_KEY`: TMDb API key for admin movie auto-fill.
- `OMDB_API_KEY`: OMDb API key for IMDb rating during admin movie auto-fill.
- `DATABASE_URL`: leave empty locally to fall back to SQLite (`nova-dev.db`).
- `AUTO_CREATE_SCHEMA`: `true` creates the schema and seeds demo data on startup, bypassing Alembic. Keep `false` in production.
- `TRANSLATION_API_URL`: RU/UZ machine translation for the admin panel; empty turns the feature off.

Every value is read and normalised in `backend/core/config.py` — the only module that touches the
environment. On startup the API logs a warning for a short `JWT_SECRET`, a missing bot token, an
empty admin list, a temporary tunnel origin, or SQLite in production; none of them stop the server.

## Local Development

Backend:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe seed_movies.py
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Bot (separate process, not part of docker compose):

```powershell
.\.venv\Scripts\python.exe bot.py
```

The bot serves the catalog and the deep links; it reads the cinema contacts from the database,
so nothing about the cinema needs a code change. It refuses to start without BOT_TOKEN.

Frontend:

```powershell
Set-Location frontend
npm ci
npm run dev
```

The frontend dev server proxies `/api` to `http://127.0.0.1:8000`.

## Docker

```powershell
docker compose up --build
```

Services:

- API: `http://localhost:8000`
- Frontend/nginx: `http://localhost:5173`
- PostgreSQL: internal service `postgres:5432`

The API container runs `alembic upgrade head` before starting Uvicorn. Uploaded images are stored in the named Docker volume `uploads`.

Seed the demo movie catalog inside Docker:

```powershell
docker compose cp seed_movies.py api:/app/seed_movies.py
docker compose exec -T api python /app/seed_movies.py
```

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m py_compile app.py bot.py
.\.venv\Scripts\python.exe -m alembic heads
Set-Location frontend
npm run lint -- --max-warnings=0
npm run build
```

`PROJECT_STATUS.md` holds the current state of the project stage by stage.

## Security Notes

- Telegram auth is validated on the server using the bot token, hash comparison, and `auth_date` freshness.
- Admin routes require a valid JWT and `admin` role.
- Uploads are admin-only, limited to image MIME types, checked by extension and file signature, and capped at 5 MB.
- Online payment is not enabled. Bookings are saved as requests and handled by the cinema staff.
