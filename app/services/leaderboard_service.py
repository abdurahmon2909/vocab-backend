from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User, UserDuelRating, UserXP
from app.services.duel_rating_service import DuelRatingService
from app.services.xp_service import XPService


# Frontenddagi src/config/rankConfig.js bilan bir xil tartib.
# Legend endi 10000 ELO dan boshlanadi.
RANKS = [
    {
        "rank_title": "Bronze",
        "rank_icon": "🥉",
        "rank_min_elo": 0,
        "rank_max_elo": 999,
        "short_label": "Start",
        "description": "Duel yo‘lini boshlagan jangchi.",
    },
    {
        "rank_title": "Silver",
        "rank_icon": "⚪",
        "rank_min_elo": 1000,
        "rank_max_elo": 1249,
        "short_label": "Stable",
        "description": "Asosiy bilim va tezlik shakllangan bosqich.",
    },
    {
        "rank_title": "Gold",
        "rank_icon": "🟡",
        "rank_min_elo": 1250,
        "rank_max_elo": 1499,
        "short_label": "Sharp",
        "description": "Aniqlik kuchayadi, duel natijalari barqarorlashadi.",
    },
    {
        "rank_title": "Platinum",
        "rank_icon": "🟣",
        "rank_min_elo": 1500,
        "rank_max_elo": 1799,
        "short_label": "Elite",
        "description": "Yuqori tezlik va xotira kuchli ishlay boshlaydi.",
    },
    {
        "rank_title": "Diamond",
        "rank_icon": "💎",
        "rank_min_elo": 1800,
        "rank_max_elo": 2199,
        "short_label": "Crystal",
        "description": "Kuchli duelchi. Xatolar kam, reaksiyalar tez.",
    },
    {
        "rank_title": "Master",
        "rank_icon": "🔥",
        "rank_min_elo": 2200,
        "rank_max_elo": 2699,
        "short_label": "Fire",
        "description": "Raqibga bosim beradigan tajribali o‘yinchi.",
    },
    {
        "rank_title": "Grandmaster",
        "rank_icon": "⚡",
        "rank_min_elo": 2700,
        "rank_max_elo": 3999,
        "short_label": "Storm",
        "description": "Top darajadagi tezkor fikrlash va duel strategiyasi.",
    },
    {
        "rank_title": "Mythic",
        "rank_icon": "🌌",
        "rank_min_elo": 4000,
        "rank_max_elo": 9999,
        "short_label": "Cosmic",
        "description": "Juda kam uchraydigan, havas qilinadigan rank.",
    },
    {
        "rank_title": "Legend",
        "rank_icon": "👑",
        "rank_min_elo": 10000,
        "rank_max_elo": None,
        "short_label": "King",
        "description": "Eng yuqori maqom. Haqiqiy Word Legends cho‘qqisi.",
    },
]


def rank_from_elo(elo: int | None) -> dict:
    value = int(elo if elo is not None else DuelRatingService.DEFAULT_ELO)
    current = RANKS[0]

    for rank in RANKS:
        if value >= int(rank["rank_min_elo"]):
            current = rank
        else:
            break

    return dict(current)


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
    def _make_item(*, rank, user, total_xp, rating, current_user_id, total_users: int):
        xp = int(total_xp or 0)
        level = XPService.level_from_xp(xp)
        badge, badge_icon = LeaderboardService._badge_from_level(level)

        elo = int(rating.elo if rating else DuelRatingService.DEFAULT_ELO)
        rank_info = rank_from_elo(elo)

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
            "rank_max_elo": rank_info["rank_max_elo"],
            "rank_short_label": rank_info.get("short_label"),
            "rank_description": rank_info.get("description"),
            "wins": int(rating.wins if rating else 0),
            "losses": int(rating.losses if rating else 0),
            "draws": int(rating.draws if rating else 0),
            "games_played": int(rating.games_played if rating else 0),
            "is_me": user.tg_id == current_user_id,
            # Frontend ota component total_users prop bermasa ham Leaderboard.jsx me/itemsdan o‘qiy oladi.
            "total_users": total_users,
        }

    @staticmethod
    async def _get_total_bot_started_users(db: AsyncSession) -> int:
        started_result = await db.execute(
            select(func.count(User.tg_id)).where(User.is_bot_started.is_(True))
        )
        started_count = int(started_result.scalar() or 0)

        # Eski bazada is_bot_started hali to‘ldirilmagan bo‘lishi mumkin.
        # Shunda UI’da Users: 0 chiqib qolmasligi uchun User jadvalidagi umumiy sonni fallback qilamiz.
        if started_count > 0:
            return started_count

        total_result = await db.execute(select(func.count(User.tg_id)))
        return int(total_result.scalar() or 0)

    @staticmethod
    async def _get_rank_position(db: AsyncSession, elo: int) -> int:
        elo_expr = func.coalesce(UserDuelRating.elo, DuelRatingService.DEFAULT_ELO)

        result = await db.execute(
            select(func.count(User.tg_id))
            .outerjoin(UserDuelRating, UserDuelRating.user_id == User.tg_id)
            .where(elo_expr > elo)
        )

        return int(result.scalar() or 0) + 1

    @staticmethod
    async def get_leaderboard(
        db: AsyncSession,
        current_user_id: int,
        limit: int = 50,
        offset: int = 0,
    ):
        elo_expr = func.coalesce(UserDuelRating.elo, DuelRatingService.DEFAULT_ELO)
        xp_expr = func.coalesce(UserXP.total_xp, 0)
        total_users = await LeaderboardService._get_total_bot_started_users(db)

        result = await db.execute(
            select(User, UserXP.total_xp, UserDuelRating)
            .outerjoin(UserXP, UserXP.user_id == User.tg_id)
            .outerjoin(UserDuelRating, UserDuelRating.user_id == User.tg_id)
            .order_by(
                elo_expr.desc(),
                xp_expr.desc(),
                User.created_at.asc(),
            )
            .offset(offset)
            .limit(limit + 1)
        )

        rows = result.all()
        has_more = len(rows) > limit
        rows = rows[:limit]

        top = []
        me = None

        for index, (user, total_xp, rating) in enumerate(rows, start=offset + 1):
            item = LeaderboardService._make_item(
                rank=index,
                user=user,
                total_xp=total_xp,
                rating=rating,
                current_user_id=current_user_id,
                total_users=total_users,
            )
            top.append(item)

            if user.tg_id == current_user_id:
                me = item

        if me is None:
            me_result = await db.execute(
                select(User, UserXP.total_xp, UserDuelRating)
                .outerjoin(UserXP, UserXP.user_id == User.tg_id)
                .outerjoin(UserDuelRating, UserDuelRating.user_id == User.tg_id)
                .where(User.tg_id == current_user_id)
            )

            row = me_result.first()

            if row:
                user, total_xp, rating = row
                elo = int(rating.elo if rating else DuelRatingService.DEFAULT_ELO)
                rank_position = await LeaderboardService._get_rank_position(db, elo)

                me = LeaderboardService._make_item(
                    rank=rank_position,
                    user=user,
                    total_xp=total_xp,
                    rating=rating,
                    current_user_id=current_user_id,
                    total_users=total_users,
                )

        return {
            "me": me,
            "top": top,
            "total_users": total_users,
            "ranks": RANKS,
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit,
            "has_more": has_more,
        }
