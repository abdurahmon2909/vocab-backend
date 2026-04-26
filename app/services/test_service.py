import random
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Word, UserWordProgress


class TestService:
    @staticmethod
    async def build_unit_questions(db: AsyncSession, unit_id: int, limit: int = 20):
        """Build questions for a specific unit"""
        words_result = await db.execute(
            select(Word).where(Word.unit_id == unit_id)
        )
        words = words_result.scalars().all()

        return TestService._build_questions(words, limit)

    @staticmethod
    async def build_weak_questions(db: AsyncSession, user_id: int, limit: int = 20):
        """Build questions for weak words (words with 2+ wrong answers)"""
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
    async def build_random_questions(db: AsyncSession, limit: int = 5):
        """Build random questions for duel and team fight modes"""
        words_result = await db.execute(
            select(Word).order_by(func.random()).limit(limit)
        )
        words = words_result.scalars().all()

        return TestService._build_questions(words, limit)

    @staticmethod
    async def build_custom_questions(db: AsyncSession, word_ids: list[int], limit: int = 20):
        """Build questions from specific word IDs"""
        if not word_ids:
            return []

        words_result = await db.execute(
            select(Word).where(Word.id.in_(word_ids)).limit(limit)
        )
        words = words_result.scalars().all()

        return TestService._build_questions(words, limit)

    @staticmethod
    def _build_questions(words: list[Word], limit: int):
        """Internal method to build questions from words"""
        if not words:
            return []

        # TO'LIQ RANDOM
        random.shuffle(words)

        selected = words[:limit]

        output = []

        for word in selected:
            # Randomly choose direction: English -> Uzbek or Uzbek -> English
            direction = random.choice(["en_uz", "uz_en"])

            if direction == "en_uz":
                question = word.english
                correct = word.uzbek
                option_field = "uzbek"
            else:
                question = word.uzbek
                correct = word.english
                option_field = "english"

            # Generate distractors (wrong options)
            distractors = [
                getattr(w, option_field)
                for w in words
                if w.id != word.id
            ]

            random.shuffle(distractors)

            # Take first 3 distractors, if not enough, reuse some
            if len(distractors) < 3:
                distractors = (distractors * 3)[:3]

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

    @staticmethod
    async def get_question_by_id(db: AsyncSession, word_id: int):
        """Get single question for a specific word"""
        word_result = await db.execute(
            select(Word).where(Word.id == word_id)
        )
        word = word_result.scalar_one_or_none()

        if not word:
            return None

        questions = TestService._build_questions([word], 1)
        return questions[0] if questions else None