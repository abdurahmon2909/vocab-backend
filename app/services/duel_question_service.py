import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Word
from app.services.test_service import TestService


class DuelQuestionService:
    @staticmethod
    async def build_data_driven_duel_questions(
        db: AsyncSession,
        limit: int = 20,
    ) -> list[dict]:
        limit = max(1, min(50, int(limit or 20)))

        easy_limit = max(1, int(limit * 0.2))
        medium_limit = max(1, int(limit * 0.3))
        hard_limit = max(1, limit - easy_limit - medium_limit)

        easy_words = (
            await db.execute(
                select(Word)
                .where(
                    Word.total_answers >= 5,
                    Word.difficulty_score < 0.3,
                )
                .order_by(func.random())
                .limit(easy_limit)
            )
        ).scalars().all()

        medium_words = (
            await db.execute(
                select(Word)
                .where(
                    Word.total_answers >= 5,
                    Word.difficulty_score >= 0.3,
                    Word.difficulty_score < 0.6,
                )
                .order_by(func.random())
                .limit(medium_limit)
            )
        ).scalars().all()

        hard_words = (
            await db.execute(
                select(Word)
                .where(
                    Word.total_answers >= 5,
                    Word.difficulty_score >= 0.6,
                )
                .order_by(func.random())
                .limit(hard_limit)
            )
        ).scalars().all()

        words = list(easy_words) + list(medium_words) + list(hard_words)
        existing_ids = {word.id for word in words}
        missing = limit - len(words)

        if missing > 0:
            fallback_query = select(Word)

            if existing_ids:
                fallback_query = fallback_query.where(~Word.id.in_(existing_ids))

            fallback_words = (
                await db.execute(
                    fallback_query
                    .order_by(func.random())
                    .limit(missing)
                )
            ).scalars().all()

            words.extend(fallback_words)

        random.shuffle(words)

        return TestService._build_questions(words, limit)