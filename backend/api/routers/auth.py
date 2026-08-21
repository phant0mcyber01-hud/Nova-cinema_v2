from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.core.security import expected_role, issue_token, telegram_user
from backend.models import User
from backend.schemas.auth import TelegramAuthIn

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/telegram")
async def auth(payload: TelegramAuthIn, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    data = telegram_user(payload.init_data)
    telegram_id = int(data["id"])
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    role = expected_role(telegram_id)
    username = str(data.get("username", ""))
    if user is None:
        user = User(
            telegram_id=telegram_id,
            name=str(data.get("first_name", "Гость")),
            username=username,
            role=role,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    elif user.role != role or user.username != username:
        user.role = role
        user.username = username
        await session.commit()
    return {
        "access_token": issue_token(user),
        "token_type": "bearer",
        "user": {"id": user.id, "name": user.name, "role": user.role},
    }
