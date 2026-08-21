"""Telegram initData validation, JWT issuing and the auth dependencies."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import config
from backend.core.db import get_db, utcnow
from backend.models import User

security = HTTPBearer(auto_error=False)


def telegram_user(init_data: str) -> dict[str, object]:
    """Verify Telegram initData server-side and return the embedded user object."""
    token = config.bot_token()
    if not token:
        raise HTTPException(503, "Telegram Auth is not configured")
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received = values.pop("hash", "")
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not received or not hmac.compare_digest(expected, received):
        raise HTTPException(401, "Invalid Telegram signature")
    try:
        auth_date = int(values["auth_date"])
    except (KeyError, ValueError) as error:
        raise HTTPException(401, "Telegram auth_date missing") from error
    issued = datetime.fromtimestamp(auth_date, timezone.utc)
    if utcnow() - issued > timedelta(seconds=config.TELEGRAM_AUTH_MAX_AGE_SECONDS):
        raise HTTPException(401, "Telegram initData expired")
    try:
        return json.loads(str(values["user"]))
    except (KeyError, json.JSONDecodeError) as error:
        raise HTTPException(401, "Telegram user missing") from error


def expected_role(telegram_id: int) -> str:
    return "admin" if telegram_id in config.ADMIN_TELEGRAM_IDS else "user"


def issue_token(user: User) -> str:
    if not config.JWT_SECRET:
        raise HTTPException(503, "JWT_SECRET is not configured")
    payload = {"sub": str(user.id), "role": user.role, "exp": utcnow() + timedelta(hours=12)}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or not config.JWT_SECRET:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as error:
        raise HTTPException(401, "Invalid access token") from error
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(401, "User not found")
    role = expected_role(user.telegram_id)
    if user.role != role:
        user.role = role
        await session.commit()
        await session.refresh(user)
    return user


async def admin_required(user: User = Depends(current_user)) -> User:
    if user.telegram_id not in config.ADMIN_TELEGRAM_IDS or user.role != "admin":
        raise HTTPException(403, "Admin role required")
    return user


async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_db),
) -> User | None:
    """Like `current_user`, but returns None instead of raising.

    The hall layout is public, yet a signed-in viewer must see their own held
    seats as selectable rather than blocked.
    """
    if credentials is None or not config.JWT_SECRET:
        return None
    try:
        payload = jwt.decode(credentials.credentials, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    return await session.get(User, user_id)
