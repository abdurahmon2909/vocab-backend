from datetime import datetime, time, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import EloExchange, UserXP
from app.services.duel_rating_service import DuelRatingService
from app.services.xp_service import XPService


class XpEloExchangeService:
    XP_PER_ELO = 100
    DAILY_ELO_LIMIT = 50
    ALLOWED_XP_PACKAGES = [100, 500, 1000, 5000, 10000]

    @staticmethod
    def _today_start_utc() -> datetime:
        today = datetime.now(timezone.utc).date()
        return datetime.combine(today, time.min, tzinfo=timezone.utc)

    @classmethod
    async def get_today_used_elo(cls, db: AsyncSession, user_id: int) -> int:
        today_start = cls._today_start_utc()

        result = await db.execute(
            select(func.coalesce(func.sum(EloExchange.elo_amount), 0))
            .where(
                EloExchange.user_id == user_id,
                EloExchange.created_at >= today_start,
            )
        )

        return int(result.scalar() or 0)

    @classmethod
    async def get_market_status(cls, db: AsyncSession, user_id: int) -> dict:
        xp_row = await db.get(UserXP, user_id)
        rating = await DuelRatingService.get_or_create_rating(db, user_id)

        total_xp = int(xp_row.total_xp if xp_row else 0)
        used_today = await cls.get_today_used_elo(db, user_id)
        remaining_today = max(0, cls.DAILY_ELO_LIMIT - used_today)

        packages = []
        for xp_amount in cls.ALLOWED_XP_PACKAGES:
            elo_amount = xp_amount // cls.XP_PER_ELO

            packages.append(
                {
                    "xp_amount": xp_amount,
                    "elo_amount": elo_amount,
                    "enabled": total_xp >= xp_amount and elo_amount <= remaining_today,
                    "disabled_reason": (
                        "XP yetarli emas"
                        if total_xp < xp_amount
                        else "Kunlik limit yetmaydi"
                        if elo_amount > remaining_today
                        else None
                    ),
                }
            )

        return {
            "total_xp": total_xp,
            "elo": int(rating.elo or DuelRatingService.DEFAULT_ELO),
            "xp_per_elo": cls.XP_PER_ELO,
            "daily_elo_limit": cls.DAILY_ELO_LIMIT,
            "used_elo_today": used_today,
            "remaining_elo_today": remaining_today,
            "packages": packages,
            "level": XPService.level_from_xp(total_xp),
        }

    @classmethod
    async def exchange(cls, db: AsyncSession, user_id: int, xp_amount: int) -> dict:
        try:
            xp_amount = int(xp_amount)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="xp_amount noto‘g‘ri")

        if xp_amount not in cls.ALLOWED_XP_PACKAGES:
            raise HTTPException(status_code=400, detail="Bunday exchange paketi yo‘q")

        elo_amount = xp_amount // cls.XP_PER_ELO
        used_today = await cls.get_today_used_elo(db, user_id)
        remaining_today = max(0, cls.DAILY_ELO_LIMIT - used_today)

        if elo_amount > remaining_today:
            raise HTTPException(
                status_code=400,
                detail=f"Kunlik limit: {cls.DAILY_ELO_LIMIT} ELO. Bugun qolgan limit: {remaining_today} ELO",
            )

        xp_row = await db.get(UserXP, user_id)
        if not xp_row or int(xp_row.total_xp or 0) < xp_amount:
            raise HTTPException(status_code=400, detail="XP yetarli emas")

        rating = await DuelRatingService.get_or_create_rating(db, user_id)

        old_xp = int(xp_row.total_xp or 0)
        old_elo = int(rating.elo or DuelRatingService.DEFAULT_ELO)

        xp_row.total_xp = old_xp - xp_amount
        rating.elo = old_elo + elo_amount

        db.add(
            EloExchange(
                user_id=user_id,
                xp_amount=xp_amount,
                elo_amount=elo_amount,
            )
        )

        await db.commit()

        new_xp = int(xp_row.total_xp or 0)
        new_level = XPService.level_from_xp(new_xp)

        return {
            "ok": True,
            "xp_spent": xp_amount,
            "elo_gained": elo_amount,
            "old_xp": old_xp,
            "new_xp": new_xp,
            "old_elo": old_elo,
            "new_elo": int(rating.elo),
            "level": new_level,
            "level_progress": XPService.level_progress_percent(new_xp),
            "next_level_xp": XPService.next_level_xp(new_level),
            "market": await cls.get_market_status(db, user_id),
        }
