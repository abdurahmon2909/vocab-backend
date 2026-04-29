from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Answer,
    ModeProgress,
    UserWordProgress,
    UserXP,
    XPEvent,
    Word,
)
from app.services.xp_service import XPService
from app.services.streak_service import StreakService
from app.services.mission_service import MissionService
from app.services.achievement_service import AchievementService


class LearningService:
    XP_REWARD_MODES = {"test", "writing", "listening"}
    XP_PER_CORRECT_ANSWER = 10

    @staticmethod
    async def should_award_xp(
        db: AsyncSession,
        user_id: int,
        word_id: int,
        mode: str,
        is_correct: bool,
    ) -> bool:
        if not is_correct:
            return False

        if mode not in LearningService.XP_REWARD_MODES:
            return False

        previous_correct_result = await db.execute(
            select(Answer.id)
            .where(
                Answer.user_id == user_id,
                Answer.word_id == word_id,
                Answer.mode == mode,
                Answer.is_correct.is_(True),
            )
            .limit(1)
        )

        return previous_correct_result.scalar_one_or_none() is None

    @staticmethod
    def update_word_difficulty(word: Word, is_correct: bool) -> None:
        word.total_answers = int(word.total_answers or 0) + 1

        if is_correct:
            word.correct_answers = int(word.correct_answers or 0) + 1

        if word.total_answers > 0:
            word.difficulty_score = 1 - (
                int(word.correct_answers or 0) / int(word.total_answers or 1)
            )
            word.difficulty_score = max(0.0, min(1.0, float(word.difficulty_score)))

    @staticmethod
    async def get_or_create_word_progress(
        db: AsyncSession,
        user_id: int,
        word_id: int,
    ) -> UserWordProgress:
        stmt = (
            insert(UserWordProgress)
            .values(
                user_id=user_id,
                word_id=word_id,
                seen_count=0,
                correct_count=0,
                wrong_count=0,
                last_result=None,
                mastery_score=0,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "word_id"])
        )

        await db.execute(stmt)
        await db.flush()

        result = await db.execute(
            select(UserWordProgress)
            .where(
                UserWordProgress.user_id == user_id,
                UserWordProgress.word_id == word_id,
            )
            .with_for_update()
        )
        return result.scalar_one()

    @staticmethod
    async def get_or_create_mode_progress(
        db: AsyncSession,
        user_id: int,
        unit_id: int,
        mode: str,
        total_questions: int,
        correct_answers: int,
        progress_percent: int,
    ) -> ModeProgress:
        stmt = (
            insert(ModeProgress)
            .values(
                user_id=user_id,
                unit_id=unit_id,
                mode=mode,
                total_questions=total_questions,
                correct_answers=correct_answers,
                progress_percent=progress_percent,
                is_completed=progress_percent >= 80,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "unit_id", "mode"])
        )

        await db.execute(stmt)
        await db.flush()

        result = await db.execute(
            select(ModeProgress)
            .where(
                ModeProgress.user_id == user_id,
                ModeProgress.unit_id == unit_id,
                ModeProgress.mode == mode,
            )
            .with_for_update()
        )
        return result.scalar_one()

    @staticmethod
    async def update_mode_best_progress(
        db: AsyncSession,
        user_id: int,
        unit_id: int,
        mode: str,
        total_questions: int,
        correct_answers: int,
    ) -> ModeProgress:
        if total_questions <= 0:
            attempt_percent = 0
        else:
            attempt_percent = int((correct_answers / total_questions) * 100)

        progress = await LearningService.get_or_create_mode_progress(
            db=db,
            user_id=user_id,
            unit_id=unit_id,
            mode=mode,
            total_questions=total_questions,
            correct_answers=correct_answers,
            progress_percent=attempt_percent,
        )

        old_percent = int(progress.progress_percent or 0)
        if attempt_percent > old_percent:
            progress.total_questions = total_questions
            progress.correct_answers = correct_answers
            progress.progress_percent = attempt_percent
            progress.is_completed = attempt_percent >= 80

        await db.flush()
        return progress

    @staticmethod
    async def insert_answer_once(
        db: AsyncSession,
        user_id: int,
        word_id: int,
        unit_id: int,
        mode: str,
        answer_session_id: str,
        is_correct: bool,
        user_answer: str | None,
        correct_answer: str | None,
    ) -> bool:
        """
        Returns True only when this answer was newly inserted.
        If the same user/word/mode/session answer already exists, returns False.
        Requires migration unique constraint: uq_answer_once_per_session_word_mode.
        """
        stmt = (
            insert(Answer)
            .values(
                user_id=user_id,
                word_id=word_id,
                unit_id=unit_id,
                mode=mode,
                answer_session_id=answer_session_id,
                is_correct=is_correct,
                user_answer=user_answer,
                correct_answer=correct_answer,
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "word_id", "mode", "answer_session_id"]
            )
            .returning(Answer.id)
        )

        result = await db.execute(stmt)
        inserted_answer_id = result.scalar_one_or_none()
        return inserted_answer_id is not None

    @staticmethod
    async def process_answer(
        db: AsyncSession,
        user_id: int,
        word_id: int,
        unit_id: int,
        mode: str,
        is_correct: bool,
        user_answer: str | None = None,
        correct_answer: str | None = None,
        answer_session_id: str | None = None,
    ):
        answer_session_id = (answer_session_id or f"legacy:{unit_id}:{mode}").strip()[:120]

        progress = await LearningService.get_or_create_word_progress(
            db=db,
            user_id=user_id,
            word_id=word_id,
        )

        xp_row = await db.get(UserXP, user_id)
        if not xp_row:
            xp_row = UserXP(user_id=user_id, total_xp=0)
            db.add(xp_row)
            await db.flush()

        word = await db.get(Word, word_id)

        inserted_answer = await LearningService.insert_answer_once(
            db=db,
            user_id=user_id,
            word_id=word_id,
            unit_id=unit_id,
            mode=mode,
            answer_session_id=answer_session_id,
            is_correct=is_correct,
            user_answer=user_answer,
            correct_answer=correct_answer,
        )

        if not inserted_answer:
            total_xp = int(xp_row.total_xp or 0)
            level = XPService.level_from_xp(total_xp)

            return {
                "is_correct": is_correct,
                "xp_gain": 0,
                "total_xp": total_xp,
                "level": level,
                "level_progress": XPService.level_progress_percent(total_xp),
                "next_level_xp": XPService.next_level_xp(level),
                "mastery_score": int(progress.mastery_score or 0),
                "streak": 0,
                "mission_updates": [],
                "duplicate": True,
                "difficulty_score": float(word.difficulty_score or 0.5) if word else 0.5,
                "xp_awarded": False,
            }

        should_award_xp = await LearningService.should_award_xp(
            db=db,
            user_id=user_id,
            word_id=word_id,
            mode=mode,
            is_correct=is_correct,
        )

        progress.seen_count = int(progress.seen_count or 0) + 1

        if is_correct:
            progress.correct_count = int(progress.correct_count or 0) + 1
            progress.last_result = "correct"
        else:
            progress.wrong_count = int(progress.wrong_count or 0) + 1
            progress.last_result = "wrong"

        progress.mastery_score = int(
            (int(progress.correct_count or 0) / int(progress.seen_count or 1)) * 100
        )

        if word:
            LearningService.update_word_difficulty(word, is_correct)

        xp_gain = LearningService.XP_PER_CORRECT_ANSWER if should_award_xp else 0

        if xp_gain > 0:
            xp_row.total_xp = int(xp_row.total_xp or 0) + xp_gain
            db.add(
                XPEvent(
                    user_id=user_id,
                    amount=xp_gain,
                    reason=f"answer:{mode}",
                )
            )

        streak = await StreakService.update(db, user_id)

        mission_updates = []
        mission_updates.extend(
            await MissionService.increment(db, user_id, "questions", 1)
        )

        if mode.startswith("weak"):
            mission_updates.extend(
                await MissionService.increment(db, user_id, "weak_words", 1)
            )

        if is_correct and mode not in {"flashcard", "weak_flashcard"}:
            await AchievementService.increment_progress(
                db=db,
                user_id=user_id,
                group_code="words_correct",
                amount=1,
            )

        await db.commit()

        total_xp = int(xp_row.total_xp or 0)
        level = XPService.level_from_xp(total_xp)

        return {
            "is_correct": is_correct,
            "xp_gain": xp_gain,
            "total_xp": total_xp,
            "level": level,
            "level_progress": XPService.level_progress_percent(total_xp),
            "next_level_xp": XPService.next_level_xp(level),
            "mastery_score": int(progress.mastery_score or 0),
            "streak": streak.streak,
            "mission_updates": mission_updates,
            "duplicate": False,
            "difficulty_score": float(word.difficulty_score or 0.5) if word else 0.5,
            "xp_awarded": xp_gain > 0,
        }
