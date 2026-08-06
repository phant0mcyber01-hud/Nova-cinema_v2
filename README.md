# Nova Cinema Mini App

Telegram Mini App for Nova Cinema: React frontend, FastAPI backend, Telegram initData auth, JWT roles, async SQLAlchemy, Alembic migrations, PostgreSQL, Docker Compose, and an admin panel.

## Production Stack

- Frontend: React, TypeScript, Vite, Telegram WebApp SDK.
- Backend: FastAPI, Pydantic, JWT, server-side Telegram initData validation.
- Database: PostgreSQL with SQLAlchemy 2.0 async and Alembic.
- Runtime: Docker Compose. Frontend image serves static files with nginx and proxies `/api` and `/uploads` to the API service.

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

## Local Development

Backend:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe seed_movies.py
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

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
.\.venv\Scripts\python.exe -m py_compile app.py bot.py
.\.venv\Scripts\alembic.exe heads
Set-Location frontend
npm run lint -- --max-warnings=0
npm run build
```

## Security Notes

- Telegram auth is validated on the server using the bot token, hash comparison, and `auth_date` freshness.
- Admin routes require a valid JWT and `admin` role.
- Uploads are admin-only, limited to image MIME types, checked by extension and file signature, and capped at 5 MB.
- Online payment is not enabled. Bookings are saved as requests and handled by the cinema staff.
