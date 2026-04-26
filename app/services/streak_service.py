from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import Streak


class StreakService:
    @staticmethod
    async def update(db: AsyncSession, user_id: int) -> int:
        today = date.today()

        result = await db.execute(
            select(Streak).where(Streak.user_id == user_id)
        )
        streak = result.scalar_one_or_none()

        # 🔥 agar yo‘q bo‘lsa yaratamiz
        if not streak:
            streak = Streak(
                user_id=user_id,
                streak=1,
                best_streak=1,
                last_active_date=today,
            )
            db.add(streak)
            await db.commit()
            return 1

        # 🔥 MUHIM FIX
        last_date = streak.last_active_date

        if last_date == today:
            return streak.streak

        if last_date and (today - last_date).days == 1:
            streak.streak += 1
        else:
            streak.streak = 1

        if streak.streak > streak.best_streak:
            streak.best_streak = streak.streak

        streak.last_active_date = today

        await db.commit()

        return streak.streak