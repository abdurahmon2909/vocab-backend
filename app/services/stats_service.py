from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.achievement_service import AchievementService


class StatsService:
    @staticmethod
    async def get_stats(db: AsyncSession, user_id: int):
        result = await db.execute(
            text("""
                SELECT
                    COALESCE(SUM(seen_count), 0) AS total_seen,
                    COALESCE(SUM(correct_count), 0) AS total_correct,
                    COALESCE(SUM(wrong_count), 0) AS total_wrong,
                    COUNT(*) FILTER (WHERE mastery_score < 60) AS weak_words_count,
                    COUNT(*) FILTER (WHERE mastery_score >= 80) AS mastered_words_count
                FROM user_word_progress
                WHERE user_id = :user_id
            """),
            {"user_id": user_id},
        )
        row = result.mappings().one()
        return {
            "total_seen": int(row["total_seen"] or 0),
            "total_correct": int(row["total_correct"] or 0),
            "total_wrong": int(row["total_wrong"] or 0),
            "weak_words_count": int(row["weak_words_count"] or 0),
            "mastered_words_count": int(row["mastered_words_count"] or 0),
        }

    @staticmethod
    async def get_profile_stats_fast(db: AsyncSession, user_id: int):
        """Fast version without achievements - for batch loading"""
        result = await db.execute(
            text("""
                WITH
                user_info AS (
                    SELECT
                        COALESCE(nickname, first_name, username, 'Learner') AS display_name,
                        COALESCE((SELECT total_xp FROM user_xp WHERE user_id = :user_id), 0) AS xp
                    FROM users
                    WHERE tg_id = :user_id
                ),
                word_stats AS (
                    SELECT
                        COUNT(*) AS words_learned,
                        COUNT(*) FILTER (WHERE mastery_score >= 80) AS mastered_words,
                        COUNT(*) FILTER (WHERE mastery_score < 60) AS weak_words
                    FROM user_word_progress
                    WHERE user_id = :user_id
                ),
                answer_stats AS (
                    SELECT
                        COUNT(*) AS total_answers,
                        COUNT(*) FILTER (WHERE is_correct = true) AS correct_answers,
                        COUNT(*) FILTER (WHERE is_correct = false) AS wrong_answers,
                        COUNT(*) FILTER (WHERE mode = 'test' AND is_correct = true) AS test_correct,
                        COUNT(*) FILTER (WHERE mode = 'writing' AND is_correct = true) AS writing_correct,
                        COUNT(*) FILTER (WHERE mode = 'listening' AND is_correct = true) AS listening_correct,
                        COUNT(*) FILTER (WHERE mode = 'test') AS test_answers,
                        COUNT(*) FILTER (WHERE mode = 'writing') AS writing_answers,
                        COUNT(*) FILTER (WHERE mode = 'listening') AS listening_answers
                    FROM answers
                    WHERE user_id = :user_id
                ),
                completed_units AS (
                    SELECT COUNT(DISTINCT unit_id) AS units_completed
                    FROM mode_progress
                    WHERE user_id = :user_id
                      AND mode IN ('test', 'writing', 'listening')
                      AND progress_percent >= 80
                ),
                duel_stats AS (
                    SELECT
                        COALESCE(elo, 1000) AS elo,
                        COALESCE(games_played, 0) AS games_played,
                        COALESCE(wins, 0) AS wins,
                        COALESCE(losses, 0) AS losses,
                        COALESCE(draws, 0) AS draws
                    FROM user_duel_ratings
                    WHERE user_id = :user_id
                ),
                streak_stats AS (
                    SELECT
                        COALESCE(streak, 0) AS streak,
                        COALESCE(best_streak, 0) AS best_streak
                    FROM streaks
                    WHERE user_id = :user_id
                )
                SELECT
                    (SELECT display_name FROM user_info) AS display_name,
                    (SELECT xp FROM user_info) AS xp,
                    FLOOR(SQRT(COALESCE((SELECT xp FROM user_info), 0) / 10)) AS level,
                    COALESCE((SELECT words_learned FROM word_stats), 0) AS words_learned,
                    COALESCE((SELECT mastered_words FROM word_stats), 0) AS mastered_words,
                    COALESCE((SELECT weak_words FROM word_stats), 0) AS weak_words,
                    COALESCE((SELECT total_answers FROM answer_stats), 0) AS total_answers,
                    COALESCE((SELECT correct_answers FROM answer_stats), 0) AS correct_answers,
                    COALESCE((SELECT wrong_answers FROM answer_stats), 0) AS wrong_answers,
                    COALESCE((SELECT test_correct FROM answer_stats), 0) AS test_correct,
                    COALESCE((SELECT writing_correct FROM answer_stats), 0) AS writing_correct,
                    COALESCE((SELECT listening_correct FROM answer_stats), 0) AS listening_correct,
                    COALESCE((SELECT test_answers FROM answer_stats), 0) AS test_answers,
                    COALESCE((SELECT writing_answers FROM answer_stats), 0) AS writing_answers,
                    COALESCE((SELECT listening_answers FROM answer_stats), 0) AS listening_answers,
                    COALESCE((SELECT units_completed FROM completed_units), 0) AS units_completed,
                    COALESCE((SELECT elo FROM duel_stats), 1000) AS elo,
                    COALESCE((SELECT games_played FROM duel_stats), 0) AS games_played,
                    COALESCE((SELECT wins FROM duel_stats), 0) AS wins,
                    COALESCE((SELECT losses FROM duel_stats), 0) AS losses,
                    COALESCE((SELECT draws FROM duel_stats), 0) AS draws,
                    COALESCE((SELECT streak FROM streak_stats), 0) AS streak,
                    COALESCE((SELECT best_streak FROM streak_stats), 0) AS best_streak
            """),
            {"user_id": user_id},
        )

        row = result.mappings().first()
        if not row:
            return None

        total_answers = int(row["total_answers"] or 0)
        correct_answers = int(row["correct_answers"] or 0)
        duel_total = int(row["games_played"] or 0)
        duel_wins = int(row["wins"] or 0)

        accuracy = round((correct_answers / total_answers) * 100) if total_answers else 0
        win_rate = round((duel_wins / duel_total) * 100) if duel_total else 0

        xp = int(row["xp"] or 0)
        level = int(row["level"] or 0)
        next_level_xp = ((level + 1) ** 2) * 10
        current_level_xp = (level ** 2) * 10
        level_progress = int(((xp - current_level_xp) / (
                    next_level_xp - current_level_xp)) * 100) if next_level_xp > current_level_xp else 100

        return {
            "overview": {
                "display_name": row["display_name"],
                "level": level,
                "xp": xp,
                "level_progress": level_progress,
                "next_level_xp": next_level_xp,
                "units_completed": int(row["units_completed"] or 0),
                "words_learned": int(row["words_learned"] or 0),
                "mastered_words": int(row["mastered_words"] or 0),
                "weak_words": int(row["weak_words"] or 0),
                "accuracy": accuracy,
                "streak": int(row["streak"] or 0),
                "best_streak": int(row["best_streak"] or 0),
            },
            "duel": {
                "total": duel_total,
                "wins": duel_wins,
                "losses": int(row["losses"] or 0),
                "draws": int(row["draws"] or 0),
                "win_rate": win_rate,
                "elo": int(row["elo"] or 1000),
            },
            "learning": {
                "total_answers": total_answers,
                "correct": correct_answers,
                "wrong": int(row["wrong_answers"] or 0),
                "accuracy": accuracy,
                "test_correct": int(row["test_correct"] or 0),
                "writing_correct": int(row["writing_correct"] or 0),
                "listening_correct": int(row["listening_correct"] or 0),
                "test_answers": int(row["test_answers"] or 0),
                "writing_answers": int(row["writing_answers"] or 0),
                "listening_answers": int(row["listening_answers"] or 0),
                "weak_words_count": int(row["weak_words"] or 0),
                "mastered_words_count": int(row["mastered_words"] or 0),
                "modes": {
                    "test": {
                        "total": int(row["test_answers"] or 0),
                        "correct": int(row["test_correct"] or 0),
                        "accuracy": round((int(row["test_correct"] or 0) / max(int(row["test_answers"] or 0), 1)) * 100)
                    },
                    "writing": {
                        "total": int(row["writing_answers"] or 0),
                        "correct": int(row["writing_correct"] or 0),
                        "accuracy": round(
                            (int(row["writing_correct"] or 0) / max(int(row["writing_answers"] or 0), 1)) * 100)
                    },
                    "listening": {
                        "total": int(row["listening_answers"] or 0),
                        "correct": int(row["listening_correct"] or 0),
                        "accuracy": round(
                            (int(row["listening_correct"] or 0) / max(int(row["listening_answers"] or 0), 1)) * 100)
                    }
                }
            },
            "achievements": {
                "completed": 0,
                "claimed": 0,
                "total": 0,
                "progress": 0,
            },
        }

    @staticmethod
    async def get_profile_stats(db: AsyncSession, user_id: int):
        """Full version with achievements - for single user"""
        fast_stats = await StatsService.get_profile_stats_fast(db, user_id)
        if not fast_stats:
            return None

        # Add achievements
        achievements_payload = await AchievementService.get_payload(db, user_id)
        groups = achievements_payload.get("groups", []) if isinstance(achievements_payload, dict) else []

        all_tiers = []
        for group in groups:
            tiers = group.get("tiers") or group.get("achievements") or []
            if tiers:
                all_tiers.extend(tiers)
            elif group.get("active_tier"):
                all_tiers.append(group["active_tier"])

        total_achievements = len(all_tiers)
        completed_achievements = sum(1 for item in all_tiers if item.get("is_completed") or item.get("completed"))
        claimed_achievements = sum(1 for item in all_tiers if item.get("is_claimed") or item.get("claimed"))
        achievement_progress = round((completed_achievements / total_achievements) * 100) if total_achievements else 0

        fast_stats["achievements"] = {
            "completed": completed_achievements,
            "claimed": claimed_achievements,
            "unclaimed": completed_achievements - claimed_achievements,
            "total": total_achievements,
            "progress": achievement_progress,
            "progress_percent": achievement_progress,
        }

        return fast_stats