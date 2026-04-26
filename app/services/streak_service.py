from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Streak


class StreakService:

    @staticmethod
    async def update(db: AsyncSession, user_id: int):
        today = date.today()

        streak = await db.get(Streak, user_id)

        if not streak:
            streak = Streak(user_id=user_id, streak=1, last_date=today)
            db.add(streak)
        else:
            if streak.last_date == today:
                return streak

            if streak.last_date == today - timedelta(days=1):
                streak.streak += 1
            else:
                streak.streak = 1

            streak.last_date = today

        await db.commit()
        return streak