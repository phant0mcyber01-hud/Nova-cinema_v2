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
.\.venv\Scripts\python.exe -m py_compile app.py bot.py
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
- The base ticket price is stored in `cinema_settings` and can be changed from the admin settings page.
- Price priority is session price, movie price, global base price, fallback `30000`.
- User QR validity is derived from booking status: valid for `confirmed` and `completed`, invalid for `pending` and `cancelled`.
- Uploaded images live under `UPLOAD_DIR` in local mode and the `uploads` Docker volume in Compose.
- Telegram Mini Apps require a public HTTPS frontend URL.

## Useful Commands

```powershell
.\.venv\Scripts\alembic.exe heads
.\.venv\Scripts\alembic.exe history
docker compose logs -f api
docker compose logs -f frontend
docker compose exec api alembic current
```
