"""Open the Mini App in a normal browser, signed in, without Telegram.

The app authenticates with Telegram `initData`: a query string signed with the
bot token. Inside Telegram the client supplies it; in a browser there is none,
so the profile and the admin panel stay locked and nothing can be booked —
which makes a local demo useless.

This script signs `initData` with the same token the server verifies against
and prints the URL that carries it. Telegram's own web SDK reads those values
from the URL fragment, so the app boots exactly as it does inside Telegram:
same HMAC check on the server, same JWT, same roles. No back door is added to
the application, and nothing here works without the bot token.

    python demo_login.py

Pass ids to sign in as somebody else:

    python demo_login.py 111111111
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
from urllib.parse import quote, urlencode

from backend.core import config

FRONTEND = "http://localhost:5173"
DEMO_VIEWER_ID = 111111111


def init_data(telegram_id: int, username: str, first_name: str, last_name: str = "") -> str:
    token = config.bot_token()
    if not token:
        raise SystemExit("BOT_TOKEN is not set: the signature cannot be produced")
    user = {"id": telegram_id, "username": username, "first_name": first_name}
    if last_name:
        user["last_name"] = last_name
    values = {
        "auth_date": str(int(time.time())),
        "user": json.dumps(user, separators=(",", ":"), ensure_ascii=False),
    }
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**values, "hash": signature})


def link(telegram_id: int, username: str, first_name: str, last_name: str = "") -> str:
    signed = init_data(telegram_id, username, first_name, last_name)
    # The web SDK looks for these three in the fragment, exactly as Telegram sends them.
    fragment = f"tgWebAppData={quote(signed, safe='')}&tgWebAppVersion=7.0&tgWebAppPlatform=web"
    return f"{FRONTEND}/#{fragment}"


def main() -> None:
    requested = [int(value) for value in sys.argv[1:] if value.lstrip("-").isdigit()]
    if requested:
        people = [(item, "demo", "Демо") for item in requested]
    else:
        people = [(item, "admin", "Администратор") for item in sorted(config.ADMIN_TELEGRAM_IDS)]
        people.append((DEMO_VIEWER_ID, "demo_viewer", "Алина", "Каримова"))
        if not config.ADMIN_TELEGRAM_IDS:
            print("ADMIN_TELEGRAM_IDS is empty: nobody would see the admin panel.\n")

    print("Ссылки живут сутки (TELEGRAM_AUTH_MAX_AGE_SECONDS). Открывайте в браузере:\n")
    for person in people:
        telegram_id, username, first_name = person[0], person[1], person[2]
        last_name = person[3] if len(person) > 3 else ""
        role = "администратор" if telegram_id in config.ADMIN_TELEGRAM_IDS else "зритель"
        print(f"  {first_name} {last_name} ({role}, id {telegram_id}):")
        print(f"  {link(telegram_id, username, first_name, last_name)}\n")


if __name__ == "__main__":
    main()
