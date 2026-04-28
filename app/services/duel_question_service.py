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
        """
        Data-driven duel question mix.

        Boshlanishda hamma so'zlar difficulty_score=0.5 bo'ladi,
        shuning uchun medium pool asosiy ishlaydi.

        Formula:
        - 20% easy
        - 30% medium
        - 50% hard
        Fallback: yetmay qolgan savollar random bilan to'ldiriladi.
        """
        limit = max(1, min(50, int(limit or 20)))

        easy_limit = max(1, int(limit * 0.2))
        medium_limit = max(1, int(limit * 0.3))
        hard_limit = max(1, limit - easy_limit - medium_limit)

        easy_words = (
            await db.execute(
                select(Word)
                .where(Word.difficulty_score < 0.3)
                .order_by(func.random())
                .limit(easy_limit)
            )
        ).scalars().all()

        medium_words = (
            await db.execute(
                select(Word)
                .where(
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
                .where(Word.difficulty_score >= 0.6)
                .order_by(func.random())
                .limit(hard_limit)
            )
        ).scalars().all()

        words = list(easy_words) + list(medium_words) + list(hard_words)

        existing_ids = {word.id for word in words}
        missing = limit - len(words)

        if missing > 0:
            fallback_words = (
                await db.execute(
                    select(Word)
                    .where(~Word.id.in_(existing_ids) if existing_ids else True)
                    .order_by(func.random())
                    .limit(missing)
                )
            ).scalars().all()

            words.extend(fallback_words)

        random.shuffle(words)

        return TestService._build_questions(words, limit)
