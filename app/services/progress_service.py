from sqlalchemy import select, func
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

            book_ids = [book.id for book in books]

            if not book_ids:
                output.append({
                    "id": collection.id,
                    "slug": collection.slug,
                    "title": collection.title,
                    "description": collection.description,
                    "cover_url": collection.cover_url,
                    "total_books": 0,
                    "total_units": 0,
                    "completed_units": 0,
                    "progress_percent": 0,
                })
                continue

            units_result = await db.execute(
                select(Unit.id).where(Unit.book_id.in_(book_ids), Unit.is_active == True)
            )
            unit_ids = [row[0] for row in units_result.all()]

            total_units = len(unit_ids)

            completed_units = await ProgressService.count_completed_units_by_modes(
                db=db,
                user_id=user_id,
                unit_ids=unit_ids,
            )

            progress_percent = int((completed_units / total_units) * 100) if total_units else 0

            output.append({
                "id": collection.id,
                "slug": collection.slug,
                "title": collection.title,
                "description": collection.description,
                "cover_url": collection.cover_url,
                "total_books": len(books),
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
            output.append(
                await ProgressService.get_single_book_progress(db, user_id, book)
            )

        return output

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
    async def get_single_book_progress(db: AsyncSession, user_id: int, book: Book):
        units_result = await db.execute(
            select(Unit.id).where(Unit.book_id == book.id, Unit.is_active == True)
        )
        unit_ids = [row[0] for row in units_result.all()]

        total_units = len(unit_ids)

        completed_units = await ProgressService.count_completed_units_by_modes(
            db=db,
            user_id=user_id,
            unit_ids=unit_ids,
        )

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
    async def count_completed_units_by_modes(
        db: AsyncSession,
        user_id: int,
        unit_ids: list[int],
    ) -> int:
        if not unit_ids:
            return 0

        result = await db.execute(
            select(ModeProgress.unit_id, ModeProgress.mode, ModeProgress.progress_percent)
            .where(
                ModeProgress.user_id == user_id,
                ModeProgress.unit_id.in_(unit_ids),
                ModeProgress.mode.in_(REQUIRED_UNIT_UNLOCK_MODES),
            )
        )

        rows = result.all()

        progress_by_unit = {}

        for unit_id, mode, percent in rows:
            if unit_id not in progress_by_unit:
                progress_by_unit[unit_id] = {}

            progress_by_unit[unit_id][mode] = percent

        completed = 0

        for unit_id in unit_ids:
            mode_map = progress_by_unit.get(unit_id, {})

            is_completed = all(
                mode_map.get(mode, 0) >= REQUIRED_UNIT_UNLOCK_PERCENT
                for mode in REQUIRED_UNIT_UNLOCK_MODES
            )

            if is_completed:
                completed += 1

        return completed

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
    async def get_unit_progress(
        db: AsyncSession,
        user_id: int,
        unit_id: int,
        order_index: int | None = None,
    ):
        total_words_result = await db.execute(
            select(func.count(Word.id)).where(Word.unit_id == unit_id)
        )
        total_words = total_words_result.scalar() or 0

        mastered_result = await db.execute(
            select(func.count(UserWordProgress.id))
            .join(Word, Word.id == UserWordProgress.word_id)
            .where(
                Word.unit_id == unit_id,
                UserWordProgress.user_id == user_id,
                UserWordProgress.mastery_score >= 80,
                UserWordProgress.seen_count >= 2,
            )
        )
        mastered = mastered_result.scalar() or 0

        progress_percent = int((mastered / total_words) * 100) if total_words else 0

        mode_progress = await ProgressService.get_mode_progress_for_unit(
            db,
            user_id,
            unit_id,
        )

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
    async def get_mode_progress_for_units(
        db: AsyncSession,
        user_id: int,
        unit_ids: list[int],
    ):
        if not unit_ids:
            return {}

        result = await db.execute(
            select(ModeProgress)
            .where(
                ModeProgress.user_id == user_id,
                ModeProgress.unit_id.in_(unit_ids),
            )
        )
        rows = result.scalars().all()

        output = {}

        for unit_id in unit_ids:
            output[unit_id] = {}

            for mode in ["flashcard", "writing", "test", "listening", "weak"]:
                output[unit_id][mode] = {
                    "mode": mode,
                    "total_questions": 0,
                    "correct_answers": 0,
                    "progress_percent": 0,
                    "is_completed": False,
                }

        for row in rows:
            output[row.unit_id][row.mode] = {
                "mode": row.mode,
                "total_questions": row.total_questions,
                "correct_answers": row.correct_answers,
                "progress_percent": row.progress_percent,
                "is_completed": row.is_completed,
            }

        return output

    @staticmethod
    async def get_word_stats_for_units(
        db: AsyncSession,
        user_id: int,
        unit_ids: list[int],
    ):
        if not unit_ids:
            return {}

        total_words_result = await db.execute(
            select(Word.unit_id, func.count(Word.id))
            .where(Word.unit_id.in_(unit_ids))
            .group_by(Word.unit_id)
        )

        total_words_map = {
            unit_id: count
            for unit_id, count in total_words_result.all()
        }

        mastered_result = await db.execute(
            select(Word.unit_id, func.count(UserWordProgress.id))
            .join(UserWordProgress, UserWordProgress.word_id == Word.id)
            .where(
                Word.unit_id.in_(unit_ids),
                UserWordProgress.user_id == user_id,
                UserWordProgress.mastery_score >= 80,
                UserWordProgress.seen_count >= 2,
            )
            .group_by(Word.unit_id)
        )

        mastered_map = {
            unit_id: count
            for unit_id, count in mastered_result.all()
        }

        output = {}

        for unit_id in unit_ids:
            total_words = total_words_map.get(unit_id, 0)
            mastered_words = mastered_map.get(unit_id, 0)
            progress_percent = int((mastered_words / total_words) * 100) if total_words else 0

            output[unit_id] = {
                "total_words": total_words,
                "mastered_words": mastered_words,
                "progress_percent": progress_percent,
            }

        return output

    @staticmethod
    def is_mode_progress_completed(mode_progress: dict) -> bool:
        return all(
            mode_progress[mode]["progress_percent"] >= REQUIRED_UNIT_UNLOCK_PERCENT
            for mode in REQUIRED_UNIT_UNLOCK_MODES
        )

    @staticmethod
    async def is_unit_unlocked(
        db: AsyncSession,
        user_id: int,
        units: list[Unit],
        index: int,
        mode_progress_by_unit: dict | None = None,
    ) -> bool:
        if index == 0:
            return True

        previous_unit = units[index - 1]

        if mode_progress_by_unit is not None:
            previous_progress = mode_progress_by_unit.get(previous_unit.id, {})
        else:
            previous_progress = await ProgressService.get_mode_progress_for_unit(
                db,
                user_id,
                previous_unit.id,
            )

        return ProgressService.is_mode_progress_completed(previous_progress)

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
            .where(Unit.book_id == current_unit.book_id, Unit.is_active == True)
            .order_by(Unit.order_index, Unit.unit_number)
        )
        units = units_result.scalars().all()

        current_index = next((i for i, unit in enumerate(units) if unit.id == unit_id), None)

        if current_index is None:
            return {
                "allowed": False,
                "reason": "Unit bu kitob ichida topilmadi.",
            }

        unit_ids = [unit.id for unit in units]
        mode_progress_by_unit = await ProgressService.get_mode_progress_for_units(
            db,
            user_id,
            unit_ids,
        )

        allowed = await ProgressService.is_unit_unlocked(
            db,
            user_id,
            units,
            current_index,
            mode_progress_by_unit,
        )

        return {
            "allowed": allowed,
            "reason": None if allowed else "Oldingi unitda Writing, Test va Listening mode kamida 80% bo‘lishi kerak.",
        }

    @staticmethod
    async def get_units_with_progress(db: AsyncSession, user_id: int, book_id: int):
        units_result = await db.execute(
            select(Unit)
            .where(Unit.book_id == book_id, Unit.is_active == True)
            .order_by(Unit.order_index, Unit.unit_number)
        )
        units = units_result.scalars().all()

        unit_ids = [unit.id for unit in units]

        mode_progress_by_unit = await ProgressService.get_mode_progress_for_units(
            db,
            user_id,
            unit_ids,
        )

        word_stats_by_unit = await ProgressService.get_word_stats_for_units(
            db,
            user_id,
            unit_ids,
        )

        output = []

        for index, unit in enumerate(units):
            word_stats = word_stats_by_unit.get(unit.id, {
                "total_words": 0,
                "mastered_words": 0,
                "progress_percent": 0,
            })

            mode_progress = mode_progress_by_unit.get(unit.id, {})
            required_done = ProgressService.is_mode_progress_completed(mode_progress)

            is_unlocked = await ProgressService.is_unit_unlocked(
                db,
                user_id,
                units,
                index,
                mode_progress_by_unit,
            )

            if not is_unlocked:
                status = "locked"
            elif required_done:
                status = "completed"
            elif word_stats["progress_percent"] > 0:
                status = "in_progress"
            else:
                status = "in_progress"

            output.append({
                "id": unit.id,
                "book_id": unit.book_id,
                "unit_number": unit.unit_number,
                "title": unit.title,
                "description": unit.description,
                "total_words": word_stats["total_words"],
                "mastered_words": word_stats["mastered_words"],
                "progress_percent": word_stats["progress_percent"],
                "mode_progress": mode_progress,
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

        word_ids = [word.id for word in words]

        progress_result = await db.execute(
            select(UserWordProgress).where(
                UserWordProgress.user_id == user_id,
                UserWordProgress.word_id.in_(word_ids),
            )
        )
        progress_rows = progress_result.scalars().all()

        progress_map = {
            progress.word_id: progress
            for progress in progress_rows
        }

        output = []

        for word in words:
            progress = progress_map.get(word.id)

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