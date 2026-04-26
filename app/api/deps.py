from datetime import datetime
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.models import User, UserXP, Streak


async def get_db():
    async with SessionLocal() as session:
        yield session


async def get_current_user(
        authorization: str | None = Header(default=None),
        db: AsyncSession = Depends(get_db),
):
    # TEST MODE - Sizning Telegram ID-ingiz
    TEST_USER_ID = 5467664026

    # User ni topish
    result = await db.execute(
        select(User).where(User.tg_id == TEST_USER_ID)
    )
    user = result.scalar_one_or_none()

    if not user:
        # User yaratish
        user = User(
            tg_id=TEST_USER_ID,
            first_name="Test",
            last_name="User",
            nickname="Test User",
            created_at=datetime.utcnow(),
        )
        db.add(user)
        await db.flush()

        # XP yaratish
        xp = UserXP(user_id=user.tg_id, total_xp=0)
        streak = Streak(user_id=user.tg_id, streak=0, best_streak=0)
        db.add(xp)
        db.add(streak)
        await db.commit()

        print(f"✅ Created user: {TEST_USER_ID}")

    # User object ni qaytarish (xp va streak alohida)
    return user