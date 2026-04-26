from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Answer,
    UserWordProgress,
    UserXP,
    XPEvent,
)
from app.services.xp_service import XPService
from app.services.streak_service import StreakService
from app.services.mission_service import MissionService


class LearningService:
    @staticmethod
    def xp_for_answer(is_correct: bool, mode: str) -> int:
        if not is_correct:
            return 2

        if mode.startswith("weak"):
            return 14

        if mode == "writing":
            return 15

        if mode == "listening":
            return 12

        if mode == "test":
            return 10

        return 8

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
    ):
        progress_result = await db.execute(
            select(UserWordProgress).where(
                UserWordProgress.user_id == user_id,
                UserWordProgress.word_id == word_id,
            )
        )
        progress = progress_result.scalar_one_or_none()

        if not progress:
            progress = UserWordProgress(
                user_id=user_id,
                word_id=word_id,
                seen_count=0,
                correct_count=0,
                wrong_count=0,
                mastery_score=0,
            )
            db.add(progress)
            await db.flush()

        progress.seen_count += 1

        if is_correct:
            progress.correct_count += 1
            progress.last_result = "correct"
        else:
            progress.wrong_count += 1
            progress.last_result = "wrong"

        progress.mastery_score = int((progress.correct_count / progress.seen_count) * 100)

        xp_gain = LearningService.xp_for_answer(is_correct, mode)

        xp_row = await db.get(UserXP, user_id)
        if not xp_row:
            xp_row = UserXP(user_id=user_id, total_xp=0)
            db.add(xp_row)
            await db.flush()

        xp_row.total_xp += xp_gain

        db.add(XPEvent(
            user_id=user_id,
            amount=xp_gain,
            reason=f"answer:{mode}",
        ))

        db.add(Answer(
            user_id=user_id,
            word_id=word_id,
            unit_id=unit_id,
            mode=mode,
            is_correct=is_correct,
            user_answer=user_answer,
            correct_answer=correct_answer,
        ))

        streak = await StreakService.update(db, user_id)

        mission_updates = []
        mission_updates.extend(
            await MissionService.increment(db, user_id, "questions", 1)
        )

        if mode.startswith("weak"):
            mission_updates.extend(
                await MissionService.increment(db, user_id, "weak_words", 1)
            )

        await db.commit()

        total_xp = xp_row.total_xp
        level = XPService.level_from_xp(total_xp)

        return {
            "is_correct": is_correct,
            "xp_gain": xp_gain,
            "total_xp": total_xp,
            "level": level,
            "level_progress": XPService.level_progress_percent(total_xp),
            "next_level_xp": XPService.next_level_xp(level),
            "mastery_score": progress.mastery_score,
            "streak": streak.streak,
            "mission_updates": mission_updates,
        }