import random
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Word, UserWordProgress


class TestService:
    @staticmethod
    async def build_unit_questions(db: AsyncSession, unit_id: int, limit: int = 20):
        words_result = await db.execute(
            select(Word).where(Word.unit_id == unit_id).order_by(Word.order_index, Word.id)
        )
        words = words_result.scalars().all()

        return TestService._build_questions(words, limit)

    @staticmethod
    async def build_weak_questions(db: AsyncSession, user_id: int, limit: int = 20):
        progress_result = await db.execute(
            select(UserWordProgress).where(
                UserWordProgress.user_id == user_id,
                UserWordProgress.wrong_count >= 2,
            )
        )
        progress_rows = progress_result.scalars().all()

        word_ids = [p.word_id for p in progress_rows]

        if not word_ids:
            return []

        words_result = await db.execute(
            select(Word).where(Word.id.in_(word_ids))
        )
        words = words_result.scalars().all()

        return TestService._build_questions(words, limit)

    @staticmethod
    def _build_questions(words: list[Word], limit: int):
        if not words:
            return []

        selected = words[:]
        random.shuffle(selected)
        selected = selected[:limit]

        output = []

        for word in selected:
            direction = random.choice(["en_uz", "uz_en"])

            if direction == "en_uz":
                question = word.english
                correct = word.uzbek
                option_field = "uzbek"
            else:
                question = word.uzbek
                correct = word.english
                option_field = "english"

            distractors = [
                getattr(w, option_field)
                for w in words
                if w.id != word.id
            ]

            random.shuffle(distractors)
            options = [correct] + distractors[:3]
            random.shuffle(options)

            output.append({
                "word_id": word.id,
                "unit_id": word.unit_id,
                "direction": direction,
                "question": question,
                "options": options,
                "correct_answer": correct,
            })

        return output