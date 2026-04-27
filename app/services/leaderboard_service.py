from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User, UserDuelRating, UserXP
from app.services.duel_rating_service import DuelRatingService
from app.services.xp_service import XPService


class LeaderboardService:
    @staticmethod
    def _badge_from_level(level: int) -> tuple[str, str]:
        if level >= 30:
            return "Legend Learner", "🔥"
        if level >= 20:
            return "Master Learner", "👑"
        if level >= 12:
            return "Pro Learner", "💎"
        if level >= 6:
            return "Active Learner", "⚡"
        return "New Learner", "🌱"

    @staticmethod
    async def get_leaderboard(db: AsyncSession, current_user_id: int, limit: int = 50):
        await DuelRatingService.get_or_create_rating(db, current_user_id)
        await db.flush()

        result = await db.execute(
            select(User, UserXP.total_xp, UserDuelRating)
            .outerjoin(UserXP, UserXP.user_id == User.tg_id)
            .outerjoin(UserDuelRating, UserDuelRating.user_id == User.tg_id)
            .order_by(
                UserDuelRating.elo.desc().nullslast(),
                UserXP.total_xp.desc().nullslast(),
                User.created_at.asc(),
            )
            .limit(limit)
        )
        rows = result.all()

        top = []
        me = None

        for index, (user, total_xp, rating) in enumerate(rows, start=1):
            xp = int(total_xp or 0)
            level = XPService.level_from_xp(xp)
            badge, badge_icon = LeaderboardService._badge_from_level(level)

            elo = int(rating.elo if rating else DuelRatingService.DEFAULT_ELO)
            rank_info = DuelRatingService.rank_from_elo(elo)

            item = {
                "rank": index,
                "user_id": user.tg_id,
                "display_name": user.nickname or user.first_name or user.username or "Learner",
                "username": user.username,
                "photo_url": user.photo_url,
                "xp": xp,
                "level": level,
                "level_progress": XPService.level_progress_percent(xp),
                "badge": badge,
                "badge_icon": badge_icon,
                "elo": elo,
                "rank_title": rank_info["rank_title"],
                "rank_icon": rank_info["rank_icon"],
                "wins": int(rating.wins if rating else 0),
                "losses": int(rating.losses if rating else 0),
                "draws": int(rating.draws if rating else 0),
                "games_played": int(rating.games_played if rating else 0),
                "is_me": user.tg_id == current_user_id,
            }
            top.append(item)
            if user.tg_id == current_user_id:
                me = item

        if me is None:
            me_rank_result = await db.execute(
                select(User, UserXP.total_xp, UserDuelRating)
                .outerjoin(UserXP, UserXP.user_id == User.tg_id)
                .outerjoin(UserDuelRating, UserDuelRating.user_id == User.tg_id)
                .where(User.tg_id == current_user_id)
            )
            row = me_rank_result.first()
            if row:
                user, total_xp, rating = row
                rating = rating or await DuelRatingService.get_or_create_rating(db, current_user_id)
                rank_position = await DuelRatingService.get_rank_position(db, current_user_id)
                xp = int(total_xp or 0)
                level = XPService.level_from_xp(xp)
                badge, badge_icon = LeaderboardService._badge_from_level(level)
                rank_info = DuelRatingService.rank_from_elo(rating.elo)
                me = {
                    "rank": rank_position,
                    "user_id": user.tg_id,
                    "display_name": user.nickname or user.first_name or user.username or "Learner",
                    "username": user.username,
                    "photo_url": user.photo_url,
                    "xp": xp,
                    "level": level,
                    "level_progress": XPService.level_progress_percent(xp),
                    "badge": badge,
                    "badge_icon": badge_icon,
                    "elo": int(rating.elo),
                    "rank_title": rank_info["rank_title"],
                    "rank_icon": rank_info["rank_icon"],
                    "wins": int(rating.wins or 0),
                    "losses": int(rating.losses or 0),
                    "draws": int(rating.draws or 0),
                    "games_played": int(rating.games_played or 0),
                    "is_me": True,
                }

        return {"me": me, "top": top}
