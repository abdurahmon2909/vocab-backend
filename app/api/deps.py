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
    # 🔥 SODDA TEST MODE
    test_user_id = 5467664026  # Sizning Telegram ID-ingiz

    # Userni topish yoki yaratish
    result = await db.execute(select(User).where(User.tg_id == test_user_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            tg_id=test_user_id,
            first_name="Test",
            last_name="User",
            nickname="Test User",
            created_at=datetime.utcnow(),
        )
        db.add(user)
        await db.flush()
        db.add(UserXP(user_id=user.tg_id, total_xp=0))
        db.add(Streak(user_id=user.tg_id, streak=0, best_streak=0))
        await db.commit()
        print(f"✅ Created test user: {test_user_id}")

    print(f"✅ Using user: {user.tg_id}")
    return user