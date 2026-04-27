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
    async def _ensure_all_ratings(db: AsyncSession) -> None:
        users_result = await db.execute(select(User.tg_id))
        user_ids = [int(x) for x in users_result.scalars().all()]

        ratings_result = await db.execute(select(UserDuelRating.user_id))
        existing_ids = {int(x) for x in ratings_result.scalars().all()}

        missing_ids = [user_id for user_id in user_ids if user_id not in existing_ids]

        for user_id in missing_ids:
            db.add(
                UserDuelRating(
                    user_id=user_id,
                    elo=DuelRatingService.DEFAULT_ELO,
                    wins=0,
                    losses=0,
                    draws=0,
                    games_played=0,
                )
            )

        if missing_ids:
            await db.flush()

    @staticmethod
    def _make_item(
        *,
        rank: int,
        user: User,
        total_xp: int | None,
        rating: UserDuelRating | None,
        current_user_id: int,
    ) -> dict:
        xp = int(total_xp or 0)
        level = XPService.level_from_xp(xp)
        badge, badge_icon = LeaderboardService._badge_from_level(level)

        elo = int(rating.elo if rating else DuelRatingService.DEFAULT_ELO)
        rank_info = DuelRatingService.rank_from_elo(elo)

        return {
            "rank": rank,
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
            "rank_min_elo": rank_info["rank_min_elo"],
            "wins": int(rating.wins if rating else 0),
            "losses": int(rating.losses if rating else 0),
            "draws": int(rating.draws if rating else 0),
            "games_played": int(rating.games_played if rating else 0),
            "is_me": user.tg_id == current_user_id,
        }

    @staticmethod
    async def get_leaderboard(
        db: AsyncSession,
        current_user_id: int,
        limit: int = 50,
    ):
        await LeaderboardService._ensure_all_ratings(db)

        result = await db.execute(
            select(User, UserXP.total_xp, UserDuelRating)
            .outerjoin(UserXP, UserXP.user_id == User.tg_id)
            .join(UserDuelRating, UserDuelRating.user_id == User.tg_id)
            .order_by(
                UserDuelRating.elo.desc(),
                UserXP.total_xp.desc().nullslast(),
                User.created_at.asc(),
            )
            .limit(limit)
        )

        rows = result.all()

        top = []
        me = None

        for index, (user, total_xp, rating) in enumerate(rows, start=1):
            item = LeaderboardService._make_item(
                rank=index,
                user=user,
                total_xp=total_xp,
                rating=rating,
                current_user_id=current_user_id,
            )
            top.append(item)

            if user.tg_id == current_user_id:
                me = item

        if me is None:
            me_result = await db.execute(
                select(User, UserXP.total_xp, UserDuelRating)
                .outerjoin(UserXP, UserXP.user_id == User.tg_id)
                .join(UserDuelRating, UserDuelRating.user_id == User.tg_id)
                .where(User.tg_id == current_user_id)
            )
            row = me_result.first()

            if row:
                user, total_xp, rating = row
                rank_position = await DuelRatingService.get_rank_position(db, current_user_id)

                me = LeaderboardService._make_item(
                    rank=rank_position,
                    user=user,
                    total_xp=total_xp,
                    rating=rating,
                    current_user_id=current_user_id,
                )

        await db.commit()

        return {
            "me": me,
            "top": top,
        }