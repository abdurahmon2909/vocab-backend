from datetime import datetime
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.core.security import validate_telegram
from app.core.config import settings
from app.models.models import User, UserXP, Streak


async def get_db():
    async with SessionLocal() as session:
        yield session


async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    if not authorization.startswith("tma "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    init_data = authorization.replace("tma ", "", 1)

    try:
        tg = validate_telegram(init_data, settings.BOT_TOKEN)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Telegram auth")

    result = await db.execute(
        select(User)
        .options(selectinload(User.xp), selectinload(User.streak))
        .where(User.tg_id == tg["id"])
    )
    user = result.scalar_one_or_none()

    if not user:
        initial_nickname = " ".join([
            tg.get("first_name") or "",
            tg.get("last_name") or "",
        ]).strip()

        user = User(
            tg_id=tg["id"],
            first_name=tg.get("first_name"),
            last_name=tg.get("last_name"),
            username=tg.get("username"),
            nickname=initial_nickname or tg.get("username") or "Learner",
            photo_url=tg.get("photo_url"),
            language_code=tg.get("language_code"),
            is_premium=bool(tg.get("is_premium", False)),
            last_seen_at=datetime.utcnow(),
        )
        db.add(user)
        await db.flush()

        db.add(UserXP(user_id=user.tg_id, total_xp=0))
        db.add(Streak(user_id=user.tg_id, streak=0, best_streak=0, last_active_date=None))

        await db.commit()

        result = await db.execute(
            select(User)
            .options(selectinload(User.xp), selectinload(User.streak))
            .where(User.tg_id == tg["id"])
        )
        user = result.scalar_one()

    else:
        user.first_name = tg.get("first_name")
        user.last_name = tg.get("last_name")
        user.username = tg.get("username")
        user.photo_url = tg.get("photo_url")
        user.language_code = tg.get("language_code")
        user.is_premium = bool(tg.get("is_premium", False))
        user.last_seen_at = datetime.utcnow()

        if not user.nickname:
            fallback = " ".join([
                tg.get("first_name") or "",
                tg.get("last_name") or "",
            ]).strip()
            user.nickname = fallback or tg.get("username") or "Learner"

        await db.commit()

    return user