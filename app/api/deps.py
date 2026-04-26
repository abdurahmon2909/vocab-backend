from datetime import datetime
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import SessionLocal
from app.core.security import validate_telegram
from app.core.config import settings
from app.models.models import User, UserXP, Streak


async def get_db():
    """Get database session"""
    async with SessionLocal() as session:
        yield session


async def get_current_user(
        authorization: str = Header(...),
        db: AsyncSession = Depends(get_db),
):
    """
    Get current user from Telegram authorization header.
    This works for ALL Telegram users.
    """
    # Check authorization header
    if not authorization.startswith("tma "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    # Extract init data
    init_data = authorization.replace("tma ", "", 1)

    # Validate with Telegram
    try:
        tg = validate_telegram(init_data, settings.BOT_TOKEN)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Telegram auth: {str(e)}")

    # Get or create user
    result = await db.execute(
        select(User).where(User.tg_id == tg["id"])
    )
    user = result.scalar_one_or_none()

    if not user:
        # Create new user
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

        # Create XP and Streak records
        db.add(UserXP(user_id=user.tg_id, total_xp=0))
        db.add(Streak(user_id=user.tg_id, streak=0, best_streak=0, last_active_date=None))

        await db.commit()

        # Refresh user
        result = await db.execute(
            select(User).where(User.tg_id == tg["id"])
        )
        user = result.scalar_one()

    else:
        # Update existing user info
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

    # Manually load XP and Streak (avoid relationship issues)
    xp_result = await db.execute(
        select(UserXP).where(UserXP.user_id == user.tg_id)
    )
    user.xp = xp_result.scalar_one_or_none()

    streak_result = await db.execute(
        select(Streak).where(Streak.user_id == user.tg_id)
    )
    user.streak = streak_result.scalar_one_or_none()

    return user


async def get_current_user_optional(
        authorization: str | None = Header(default=None),
        db: AsyncSession = Depends(get_db),
):
    """Get current user if authorized, otherwise return None"""
    if not authorization or not authorization.startswith("tma "):
        return None

    init_data = authorization.replace("tma ", "", 1)

    try:
        tg = validate_telegram(init_data, settings.BOT_TOKEN)
    except Exception:
        return None

    result = await db.execute(
        select(User).where(User.tg_id == tg["id"])
    )
    user = result.scalar_one_or_none()

    return user


async def get_db_transaction():
    """Get database session with transaction support"""
    async with SessionLocal() as session:
        async with session.begin():
            yield session