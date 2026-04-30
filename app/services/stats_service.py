from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Answer, Streak, User, UserDuelRating, UserWordProgress, UserXP
from app.services.duel_rating_service import DuelRatingService
from app.services.xp_service import XPService


class StatsService:
    @staticmethod
    async def get_stats(db: AsyncSession, user_id: int):
        result = await db.execute(
            select(
                func.count(Answer.id),
                func.sum(case((Answer.is_correct == True, 1), else_=0)),
                func.sum(case((Answer.is_correct == False, 1), else_=0)),
            ).where(Answer.user_id == user_id)
        )

        total_seen, total_correct, total_wrong = result.one()

        progress_result = await db.execute(
            select(
                func.sum(case((UserWordProgress.mastery_score < 60, 1), else_=0)),
                func.sum(case((UserWordProgress.mastery_score >= 80, 1), else_=0)),
                func.count(UserWordProgress.word_id),
            ).where(UserWordProgress.user_id == user_id)
        )

        weak_words, mastered_words, learned_words = progress_result.one()

        total_seen = int(total_seen or 0)
        total_correct = int(total_correct or 0)
        total_wrong = int(total_wrong or 0)
        accuracy = round((total_correct / total_seen) * 100) if total_seen else 0

        return {
            "total_seen": total_seen,
            "total_correct": total_correct,
            "total_wrong": total_wrong,
            "accuracy": accuracy,
            "weak_words_count": int(weak_words or 0),
            "mastered_words_count": int(mastered_words or 0),
            "learned_words_count": int(learned_words or 0),
        }

    @staticmethod
    async def get_public_profile_stats(db: AsyncSession, user_id: int):
        user_result = await db.execute(select(User).where(User.tg_id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            return None

        xp_result = await db.execute(select(UserXP).where(UserXP.user_id == user_id))
        xp_row = xp_result.scalar_one_or_none()
        xp = int(getattr(xp_row, "total_xp", 0) or 0)
        level = XPService.level_from_xp(xp)

        streak_result = await db.execute(select(Streak).where(Streak.user_id == user_id))
        streak_row = streak_result.scalar_one_or_none()

        rating_result = await db.execute(select(UserDuelRating).where(UserDuelRating.user_id == user_id))
        rating_row = rating_result.scalar_one_or_none()
        elo = int(getattr(rating_row, "elo", DuelRatingService.DEFAULT_ELO) or DuelRatingService.DEFAULT_ELO)
        rank_info = DuelRatingService.rank_from_elo(elo)

        learning = await StatsService.get_learning_stats(db, user_id)
        achievements = await StatsService.get_achievement_stats(db, user_id)
        units_completed = await StatsService.get_units_completed_count(db, user_id)

        wins = int(getattr(rating_row, "wins", 0) or 0)
        losses = int(getattr(rating_row, "losses", 0) or 0)
        draws = int(getattr(rating_row, "draws", 0) or 0)
        games_played = int(getattr(rating_row, "games_played", wins + losses + draws) or 0)
        win_rate = round((wins / games_played) * 100) if games_played else 0

        display_name = user.nickname or user.first_name or user.username or "Learner"

        return {
            "user": {
                "user_id": int(user.tg_id),
                "display_name": display_name,
                "username": user.username,
                "photo_url": user.photo_url,
                "xp": xp,
                "level": level,
                "level_progress": XPService.level_progress_percent(xp),
                "next_level_xp": XPService.next_level_xp(level),
                "elo": elo,
                "rank_title": rank_info["rank_title"],
                "rank_icon": rank_info["rank_icon"],
                "rank_min_elo": rank_info["rank_min_elo"],
                "rank_max_elo": rank_info.get("rank_max_elo"),
            },
            "overview": {
                "units_completed": units_completed,
                "words_learned": int(learning.get("learned_words_count", 0)),
                "mastered_words": int(learning.get("mastered_words_count", 0)),
                "weak_words": int(learning.get("weak_words_count", 0)),
                "total_answers": int(learning.get("total_seen", 0)),
                "total_correct": int(learning.get("total_correct", 0)),
                "total_wrong": int(learning.get("total_wrong", 0)),
                "accuracy": int(learning.get("accuracy", 0)),
                "streak": int(getattr(streak_row, "streak", 0) or 0),
                "best_streak": int(getattr(streak_row, "best_streak", 0) or 0),
            },
            "duel": {
                "total": games_played,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": win_rate,
                "elo": elo,
                "rank_title": rank_info["rank_title"],
                "rank_icon": rank_info["rank_icon"],
            },
            "learning": learning,
            "achievements": achievements,
        }

    @staticmethod
    async def get_learning_stats(db: AsyncSession, user_id: int):
        base = await StatsService.get_stats(db, user_id)
        mode_rows = []
        if hasattr(Answer, "mode"):
            result = await db.execute(
                select(
                    Answer.mode,
                    func.count(Answer.id),
                    func.sum(case((Answer.is_correct == True, 1), else_=0)),
                    func.sum(case((Answer.is_correct == False, 1), else_=0)),
                )
                .where(Answer.user_id == user_id)
                .group_by(Answer.mode)
            )
            mode_rows = result.all()

        modes = {}
        for mode, total, correct, wrong in mode_rows:
            total = int(total or 0)
            correct = int(correct or 0)
            wrong = int(wrong or 0)
            modes[str(mode)] = {
                "total": total,
                "correct": correct,
                "wrong": wrong,
                "accuracy": round((correct / total) * 100) if total else 0,
            }

        for required_mode in ["test", "writing", "listening", "flashcard", "weak_test", "weak_writing"]:
            modes.setdefault(required_mode, {"total": 0, "correct": 0, "wrong": 0, "accuracy": 0})

        base["modes"] = modes
        return base

    @staticmethod
    async def get_units_completed_count(db: AsyncSession, user_id: int) -> int:
        for table_name in ["user_mode_progress", "user_mode_progresses", "mode_progress", "mode_progresses"]:
            if not await StatsService._table_exists(db, table_name):
                continue

            columns = await StatsService._table_columns(db, table_name)
            if "user_id" not in columns or "unit_id" not in columns:
                continue

            completed_condition = ""
            if "is_completed" in columns:
                completed_condition = " AND is_completed = true"
            elif "progress_percent" in columns:
                completed_condition = " AND progress_percent >= 100"

            result = await db.execute(
                text(
                    f"SELECT COUNT(DISTINCT unit_id) FROM {table_name} "
                    f"WHERE user_id = :user_id{completed_condition}"
                ),
                {"user_id": user_id},
            )
            return int(result.scalar() or 0)

        if hasattr(Answer, "unit_id"):
            result = await db.execute(
                select(func.count(func.distinct(Answer.unit_id))).where(Answer.user_id == user_id)
            )
            return int(result.scalar() or 0)

        return 0

    @staticmethod
    async def get_achievement_stats(db: AsyncSession, user_id: int):
        total = 0
        completed = 0
        claimed = 0

        for achievement_table in ["achievements", "achievement"]:
            if await StatsService._table_exists(db, achievement_table):
                result = await db.execute(text(f"SELECT COUNT(*) FROM {achievement_table}"))
                total = int(result.scalar() or 0)
                break

        for user_achievement_table in ["user_achievements", "user_achievement"]:
            if not await StatsService._table_exists(db, user_achievement_table):
                continue

            columns = await StatsService._table_columns(db, user_achievement_table)
            if "user_id" not in columns:
                continue

            completed_condition = ""
            if "is_completed" in columns:
                completed_condition = " AND is_completed = true"
            elif "completed_at" in columns:
                completed_condition = " AND completed_at IS NOT NULL"

            claimed_condition = ""
            if "claimed" in columns:
                claimed_condition = " AND claimed = true"
            elif "claimed_at" in columns:
                claimed_condition = " AND claimed_at IS NOT NULL"
            elif "is_claimed" in columns:
                claimed_condition = " AND is_claimed = true"

            completed_result = await db.execute(
                text(f"SELECT COUNT(*) FROM {user_achievement_table} WHERE user_id = :user_id{completed_condition}"),
                {"user_id": user_id},
            )
            completed = int(completed_result.scalar() or 0)

            if claimed_condition:
                claimed_result = await db.execute(
                    text(f"SELECT COUNT(*) FROM {user_achievement_table} WHERE user_id = :user_id{claimed_condition}"),
                    {"user_id": user_id},
                )
                claimed = int(claimed_result.scalar() or 0)

            break

        progress_percent = round((completed / total) * 100) if total else 0
        return {
            "total": total,
            "completed": completed,
            "claimed": claimed,
            "progress_percent": progress_percent,
        }

    @staticmethod
    async def _table_exists(db: AsyncSession, table_name: str) -> bool:
        result = await db.execute(text("SELECT to_regclass(:table_name)"), {"table_name": table_name})
        return result.scalar() is not None

    @staticmethod
    async def _table_columns(db: AsyncSession, table_name: str) -> set[str]:
        result = await db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :table_name"
            ),
            {"table_name": table_name},
        )
        return {str(row[0]) for row in result.all()}
