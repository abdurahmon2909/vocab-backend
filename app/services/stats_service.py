from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Answer, UserWordProgress


class StatsService:
    @staticmethod
    async def get_stats(db: AsyncSession, user_id: int):
        # 🔥 HAMMASI BITTA QUERY
        result = await db.execute(
            select(
                func.count(Answer.id),
                func.sum(func.case((Answer.is_correct == True, 1), else_=0)),
                func.sum(func.case((Answer.is_correct == False, 1), else_=0)),
            ).where(Answer.user_id == user_id)
        )

        total_seen, total_correct, total_wrong = result.one()

        # 🔥 weak + mastered ham batch
        progress_result = await db.execute(
            select(
                func.sum(func.case((UserWordProgress.mastery_score < 60, 1), else_=0)),
                func.sum(func.case((UserWordProgress.mastery_score >= 80, 1), else_=0)),
            ).where(UserWordProgress.user_id == user_id)
        )

        weak_words, mastered_words = progress_result.one()

        return {
            "total_seen": total_seen or 0,
            "total_correct": total_correct or 0,
            "total_wrong": total_wrong or 0,
            "weak_words_count": weak_words or 0,
            "mastered_words_count": mastered_words or 0,
        }