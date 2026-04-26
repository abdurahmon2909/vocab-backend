from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Book,
    Unit,
    Word,
    UserWordProgress,
)


class ProgressService:
    @staticmethod
    async def get_books_with_progress(db: AsyncSession, user_id: int):
        books_result = await db.execute(
            select(Book).where(Book.is_active == True).order_by(Book.order_index, Book.id)
        )
        books = books_result.scalars().all()

        output = []

        for book in books:
            units_result = await db.execute(
                select(Unit).where(Unit.book_id == book.id)
            )
            units = units_result.scalars().all()

            completed_units = 0

            for unit in units:
                unit_progress = await ProgressService.get_unit_progress(db, user_id, unit.id)
                if unit_progress["status"] == "completed":
                    completed_units += 1

            total_units = len(units)
            progress_percent = int((completed_units / total_units) * 100) if total_units else 0

            output.append({
                "id": book.id,
                "slug": book.slug,
                "title": book.title,
                "description": book.description,
                "cover_url": book.cover_url,
                "total_units": total_units,
                "completed_units": completed_units,
                "progress_percent": progress_percent,
            })

        return output

    @staticmethod
    async def get_unit_progress(db: AsyncSession, user_id: int, unit_id: int, order_index: int | None = None):
        words_result = await db.execute(
            select(Word).where(Word.unit_id == unit_id)
        )
        words = words_result.scalars().all()

        total_words = len(words)

        if total_words == 0:
            return {
                "total_words": 0,
                "mastered_words": 0,
                "progress_percent": 0,
                "status": "locked" if order_index and order_index > 1 else "in_progress",
            }

        mastered = 0

        for word in words:
            progress_result = await db.execute(
                select(UserWordProgress).where(
                    UserWordProgress.user_id == user_id,
                    UserWordProgress.word_id == word.id,
                    UserWordProgress.mastery_score >= 80,
                    UserWordProgress.seen_count >= 2,
                )
            )
            progress = progress_result.scalar_one_or_none()

            if progress:
                mastered += 1

        progress_percent = int((mastered / total_words) * 100)

        if progress_percent >= 80:
            status = "completed"
        elif progress_percent > 0:
            status = "in_progress"
        else:
            status = "locked" if order_index and order_index > 1 else "in_progress"

        return {
            "total_words": total_words,
            "mastered_words": mastered,
            "progress_percent": progress_percent,
            "status": status,
        }

    @staticmethod
    async def get_units_with_progress(db: AsyncSession, user_id: int, book_id: int):
        units_result = await db.execute(
            select(Unit)
            .where(Unit.book_id == book_id)
            .order_by(Unit.order_index, Unit.unit_number)
        )
        units = units_result.scalars().all()

        output = []
        previous_completed = True

        for index, unit in enumerate(units):
            progress = await ProgressService.get_unit_progress(
                db,
                user_id,
                unit.id,
                unit.order_index,
            )

            if index == 0:
                status = progress["status"] if progress["status"] != "locked" else "in_progress"
            elif not previous_completed:
                status = "locked"
            else:
                status = progress["status"] if progress["status"] != "locked" else "in_progress"

            previous_completed = status == "completed"

            output.append({
                "id": unit.id,
                "book_id": unit.book_id,
                "unit_number": unit.unit_number,
                "title": unit.title,
                "description": unit.description,
                "total_words": progress["total_words"],
                "mastered_words": progress["mastered_words"],
                "progress_percent": progress["progress_percent"],
                "status": status,
            })

        return output

    @staticmethod
    async def get_words_with_progress(db: AsyncSession, user_id: int, unit_id: int):
        words_result = await db.execute(
            select(Word).where(Word.unit_id == unit_id).order_by(Word.order_index, Word.id)
        )
        words = words_result.scalars().all()

        output = []

        for word in words:
            progress_result = await db.execute(
                select(UserWordProgress).where(
                    UserWordProgress.user_id == user_id,
                    UserWordProgress.word_id == word.id,
                )
            )
            progress = progress_result.scalar_one_or_none()

            output.append({
                "id": word.id,
                "unit_id": word.unit_id,
                "english": word.english,
                "uzbek": word.uzbek,
                "definition": word.definition,
                "example": word.example,
                "seen_count": progress.seen_count if progress else 0,
                "correct_count": progress.correct_count if progress else 0,
                "wrong_count": progress.wrong_count if progress else 0,
                "mastery_score": progress.mastery_score if progress else 0,
            })

        return output

    @staticmethod
    async def get_stats(db: AsyncSession, user_id: int):
        rows_result = await db.execute(
            select(UserWordProgress).where(UserWordProgress.user_id == user_id)
        )
        rows = rows_result.scalars().all()

        total_seen = sum(r.seen_count for r in rows)
        total_correct = sum(r.correct_count for r in rows)
        total_wrong = sum(r.wrong_count for r in rows)
        weak_words_count = len([r for r in rows if r.wrong_count >= 2])
        mastered_words_count = len([r for r in rows if r.mastery_score >= 80 and r.seen_count >= 2])

        return {
            "total_seen": total_seen,
            "total_correct": total_correct,
            "total_wrong": total_wrong,
            "weak_words_count": weak_words_count,
            "mastered_words_count": mastered_words_count,
        }