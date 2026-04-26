from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User, UserXP
from app.services.xp_service import XPService


def display_name_for_user(user: User) -> str:
    if user.nickname and user.nickname.strip():
        return user.nickname.strip()

    full = " ".join([
        user.first_name or "",
        user.last_name or "",
    ]).strip()

    if full:
        return full

    if user.username:
        return f"@{user.username}"

    return "Learner"


def badge_for_level(level: int) -> dict:
    if level >= 30:
        return {"badge": "Legend", "badge_icon": "👑"}
    if level >= 20:
        return {"badge": "Master", "badge_icon": "🏆"}
    if level >= 12:
        return {"badge": "Pro", "badge_icon": "🔥"}
    if level >= 6:
        return {"badge": "Beginner", "badge_icon": "⭐"}
    return {"badge": "Amateur", "badge_icon": "🌱"}


class LeaderboardService:
    @staticmethod
    async def get_leaderboard(db: AsyncSession, current_user_id: int, limit: int = 50):
        result = await db.execute(
            select(User, UserXP.total_xp)
            .join(UserXP, UserXP.user_id == User.tg_id)
            .order_by(UserXP.total_xp.desc(), User.tg_id.asc())
            .limit(limit)
        )

        rows = result.all()
        top = []
        me = None

        for index, (user, xp) in enumerate(rows, start=1):
            level = XPService.level_from_xp(xp or 0)
            badge = badge_for_level(level)

            item = {
                "rank": index,
                "user_id": user.tg_id,
                "nickname": display_name_for_user(user),
                "username": user.username,
                "photo_url": user.photo_url,
                "xp": xp or 0,
                "level": level,
                "badge": badge["badge"],
                "badge_icon": badge["badge_icon"],
                "is_me": user.tg_id == current_user_id,
            }

            if user.tg_id == current_user_id:
                me = item

            top.append(item)

        if me is None:
            rank_result = await db.execute(
                select(func.count())
                .select_from(UserXP)
                .where(UserXP.total_xp > select(UserXP.total_xp).where(UserXP.user_id == current_user_id).scalar_subquery())
            )
            better_count = rank_result.scalar() or 0

            current_result = await db.execute(
                select(User, UserXP.total_xp)
                .join(UserXP, UserXP.user_id == User.tg_id)
                .where(User.tg_id == current_user_id)
            )
            current_row = current_result.first()

            if current_row:
                user, xp = current_row
                level = XPService.level_from_xp(xp or 0)
                badge = badge_for_level(level)

                me = {
                    "rank": better_count + 1,
                    "user_id": user.tg_id,
                    "nickname": display_name_for_user(user),
                    "username": user.username,
                    "photo_url": user.photo_url,
                    "xp": xp or 0,
                    "level": level,
                    "badge": badge["badge"],
                    "badge_icon": badge["badge_icon"],
                    "is_me": True,
                }

        return {
            "me": me,
            "top": top,
        }