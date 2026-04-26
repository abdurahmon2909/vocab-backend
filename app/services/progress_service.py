from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Book,
    Collection,
    ModeProgress,
    Unit,
    Word,
    UserWordProgress,
)


REQUIRED_UNIT_UNLOCK_MODES = ["writing", "test", "listening"]
REQUIRED_UNIT_UNLOCK_PERCENT = 80


class ProgressService:
    @staticmethod
    async def get_collections_with_progress(db: AsyncSession, user_id: int):
        collections_result = await db.execute(
            select(Collection)
            .where(Collection.is_active == True)
            .order_by(Collection.order_index, Collection.id)
        )
        collections = collections_result.scalars().all()

        output = []

        for collection in collections:
            books_result = await db.execute(
                select(Book)
                .where(
                    Book.collection_id == collection.id,
                    Book.is_active == True,
                )
                .order_by(Book.order_index, Book.id)
            )
            books = books_result.scalars().all()

            total_books = len(books)
            total_units = 0
            completed_units = 0

            for book in books:
                units_result = await db.execute(
                    select(Unit).where(Unit.book_id == book.id)
                )
                units = units_result.scalars().all()
                total_units += len(units)

                for unit in units:
                    unit_progress = await ProgressService.get_unit_progress(db, user_id, unit.id)
                    if unit_progress["status"] == "completed":
                        completed_units += 1

            progress_percent = int((completed_units / total_units) * 100) if total_units else 0

            output.append({
                "id": collection.id,
                "slug": collection.slug,
                "title": collection.title,
                "description": collection.description,
                "cover_url": collection.cover_url,
                "total_books": total_books,
                "total_units": total_units,
                "completed_units": completed_units,
                "progress_percent": progress_percent,
            })

        return output

    @staticmethod
    async def get_collection_books_with_progress(
        db: AsyncSession,
        user_id: int,
        collection_id: int,
    ):
        books_result = await db.execute(
            select(Book)
            .where(
                Book.collection_id == collection_id,
                Book.is_active == True,
            )
            .order_by(Book.order_index, Book.id)
        )
        books = books_result.scalars().all()

        output = []

        for book in books:
            book_progress = await ProgressService.get_single_book_progress(db, user_id, book)

            output.append(book_progress)

        return output

    @staticmethod
    async def get_single_book_progress(db: AsyncSession, user_id: int, book: Book):
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

        return {
            "id": book.id,
            "collection_id": book.collection_id,
            "slug": book.slug,
            "title": book.title,
            "description": book.description,
            "cover_url": book.cover_url,
            "total_units": total_units,
            "completed_units": completed_units,
            "progress_percent": progress_percent,
        }

    @staticmethod
    async def get_books_with_progress(db: AsyncSession, user_id: int):
        books_result = await db.execute(
            select(Book)
            .where(Book.is_active == True)
            .order_by(Book.order_index, Book.id)
        )
        books = books_result.scalars().all()

        output = []

        for book in books:
            output.append(
                await ProgressService.get_single_book_progress(db, user_id, book)
            )

        return output

    @staticmethod
    async def get_mode_progress_for_unit(db: AsyncSession, user_id: int, unit_id: int):
        result = await db.execute(
            select(ModeProgress).where(
                ModeProgress.user_id == user_id,
                ModeProgress.unit_id == unit_id,
            )
        )
        rows = result.scalars().all()

        progress_map = {
            row.mode: {
                "mode": row.mode,
                "total_questions": row.total_questions,
                "correct_answers": row.correct_answers,
                "progress_percent": row.progress_percent,
                "is_completed": row.is_completed,
            }
            for row in rows
        }

        for mode in ["flashcard", "writing", "test", "listening", "weak"]:
            if mode not in progress_map:
                progress_map[mode] = {
                    "mode": mode,
                    "total_questions": 0,
                    "correct_answers": 0,
                    "progress_percent": 0,
                    "is_completed": False,
                }

        return progress_map

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
                "mode_progress": await ProgressService.get_mode_progress_for_unit(db, user_id, unit_id),
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

        mode_progress = await ProgressService.get_mode_progress_for_unit(db, user_id, unit_id)

        required_done = all(
            mode_progress[mode]["progress_percent"] >= REQUIRED_UNIT_UNLOCK_PERCENT
            for mode in REQUIRED_UNIT_UNLOCK_MODES
        )

        if required_done:
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
            "mode_progress": mode_progress,
        }

    @staticmethod
    async def is_unit_unlocked(
        db: AsyncSession,
        user_id: int,
        units: list[Unit],
        index: int,
    ) -> bool:
        if index == 0:
            return True

        previous_unit = units[index - 1]
        previous_progress = await ProgressService.get_mode_progress_for_unit(
            db,
            user_id,
            previous_unit.id,
        )

        return all(
            previous_progress[mode]["progress_percent"] >= REQUIRED_UNIT_UNLOCK_PERCENT
            for mode in REQUIRED_UNIT_UNLOCK_MODES
        )

    @staticmethod
    async def can_access_unit(db: AsyncSession, user_id: int, unit_id: int):
        current_unit = await db.get(Unit, unit_id)

        if not current_unit:
            return {
                "allowed": False,
                "reason": "Unit topilmadi.",
            }

        units_result = await db.execute(
            select(Unit)
            .where(Unit.book_id == current_unit.book_id)
            .order_by(Unit.order_index, Unit.unit_number)
        )
        units = units_result.scalars().all()

        current_index = next((i for i, unit in enumerate(units) if unit.id == unit_id), None)

        if current_index is None:
            return {
                "allowed": False,
                "reason": "Unit bu kitob ichida topilmadi.",
            }

        allowed = await ProgressService.is_unit_unlocked(db, user_id, units, current_index)

        return {
            "allowed": allowed,
            "reason": None if allowed else "Oldingi unitda Writing, Test va Listening mode kamida 80% bo‘lishi kerak.",
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

        for index, unit in enumerate(units):
            progress = await ProgressService.get_unit_progress(
                db,
                user_id,
                unit.id,
                unit.order_index,
            )

            is_unlocked = await ProgressService.is_unit_unlocked(
                db,
                user_id,
                units,
                index,
            )

            if not is_unlocked:
                status = "locked"
            elif progress["status"] == "locked":
                status = "in_progress"
            else:
                status = progress["status"]

            output.append({
                "id": unit.id,
                "book_id": unit.book_id,
                "unit_number": unit.unit_number,
                "title": unit.title,
                "description": unit.description,
                "total_words": progress["total_words"],
                "mastered_words": progress["mastered_words"],
                "progress_percent": progress["progress_percent"],
                "mode_progress": progress["mode_progress"],
                "status": status,
                "is_locked": not is_unlocked,
                "unlock_reason": None if is_unlocked else "Oldingi unitda Writing, Test va Listening mode kamida 80% bo‘lishi kerak.",
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