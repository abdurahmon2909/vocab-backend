from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from dataclasses import dataclass
from app.models.models import (
    Referral,
    Streak,
    User,
    UserAchievementProgress,
    UserCompletedUnitAchievement,
    UserDuelRating,
    UserDuelWinStreakAchievement,
    UserXP,
)
from app.services.duel_rating_service import DuelRatingService


@dataclass(frozen=True)
class AchievementTier:
    group_code: str
    tier: int
    target: int
    reward_elo: int
    title: str
    description: str
    icon: str

    @property
    def achievement_code(self) -> str:
        return f"{self.group_code}_{self.tier}"


class AchievementService:
    """
    Way to Legend 🔥 achievement system.

    Rules:
    - One active tier per group is shown as claimable/active.
    - Next tier unlocks only after previous tier reward is claimed.
    - Rewards are ELO and are only granted when the user presses claim.
    - Referral counts only when the invited new user becomes qualified.
    """

    REFERRAL_QUALIFY_CORRECT_ANSWERS = 10

    ACHIEVEMENT_GROUPS: list[dict] = [
        {
            "group_code": "words_correct",
            "title": "So‘z ovchisi",
            "subtitle": "Test, Writing, Listening va Duel javoblari hisoblanadi",
            "icon": "🎯",
            "tiers": [
                (1, 10, 1, "10 ta so‘zni to‘g‘ri topish"),
                (2, 100, 10, "100 ta so‘zni to‘g‘ri topish"),
                (3, 500, 50, "500 ta so‘zni to‘g‘ri topish"),
                (4, 1000, 100, "1000 ta so‘zni to‘g‘ri topish"),
                (5, 5000, 500, "5000 ta so‘zni to‘g‘ri topish"),
                (6, 10000, 1000, "10 000 ta so‘zni to‘g‘ri topish"),
                (7, 50000, 5000, "50 000 ta so‘zni to‘g‘ri topish"),
                (8, 100000, 10000, "100 000 ta so‘zni to‘g‘ri topish"),
            ],
        },
        {
            "group_code": "units_completed",
            "title": "Unit ustasi",
            "subtitle": "Unitlarni yakunlab katta ELO oling",
            "icon": "📚",
            "tiers": [
                (1, 1, 10, "1 ta Unit tugatish"),
                (2, 5, 50, "5 ta Unit tugatish"),
                (3, 10, 100, "10 ta Unit tugatish"),
                (4, 20, 250, "20 ta Unit tugatish"),
                (5, 50, 500, "50 ta Unit tugatish"),
                (6, 100, 1000, "100 ta Unit tugatish"),
                (7, 250, 2500, "250 ta Unit tugatish"),
                (8, 500, 5000, "500 ta Unit tugatish"),
                (9, 1000, 10000, "1000 ta Unit tugatish"),
            ],
        },
        {
            "group_code": "invites_qualified",
            "title": "Legend elchisi",
            "subtitle": "Do‘stlarni taklif qiling va appni o‘stiring",
            "icon": "🔥",
            "tiers": [
                (1, 3, 100, "3 ta do‘st taklif qilish"),
                (2, 10, 333, "10 ta do‘st taklif qilish"),
                (3, 30, 999, "30 ta do‘st taklif qilish"),
                (4, 50, 2000, "50 ta do‘st taklif qilish"),
                (5, 100, 5000, "100 ta do‘st taklif qilish"),
            ],
        },
        {
            "group_code": "duel_wins",
            "title": "Duel Master",
            "subtitle": "1v1 duellarda g‘alaba qozoning",
            "icon": "⚔️",
            "tiers": [
                (1, 1, 25, "1 ta duel yutish"),
                (2, 10, 100, "10 ta duel yutish"),
                (3, 50, 300, "50 ta duel yutish"),
                (4, 100, 600, "100 ta duel yutish"),
                (5, 250, 1500, "250 ta duel yutish"),
                (6, 500, 3000, "500 ta duel yutish"),
                (7, 1000, 7000, "1000 ta duel yutish"),
            ],
        },
        {
            "group_code": "duel_win_streak",
            "title": "Win Streak",
            "subtitle": "Ketma-ket duel g‘alabalarini yig‘ing",
            "icon": "⚡",
            "tiers": [
                (1, 2, 20, "2 ta duelni ketma-ket yutish"),
                (2, 3, 50, "3 ta duelni ketma-ket yutish"),
                (3, 5, 150, "5 ta duelni ketma-ket yutish"),
                (4, 10, 500, "10 ta duelni ketma-ket yutish"),
                (5, 20, 1500, "20 ta duelni ketma-ket yutish"),
                (6, 50, 5000, "50 ta duelni ketma-ket yutish"),
            ],
        },
        {
            "group_code": "daily_grinder",
            "title": "Daily Grinder",
            "subtitle": "Har kuni faol bo‘lib streakni oshiring",
            "icon": "🔥",
            "tiers": [
                (1, 3, 30, "3 kunlik streak"),
                (2, 7, 100, "7 kunlik streak"),
                (3, 14, 250, "14 kunlik streak"),
                (4, 30, 700, "30 kunlik streak"),
                (5, 60, 1500, "60 kunlik streak"),
                (6, 100, 3000, "100 kunlik streak"),
                (7, 365, 10000, "365 kunlik streak"),
            ],
        },
        {
            "group_code": "xp_collector",
            "title": "XP Collector",
            "subtitle": "XP yig‘ib Legend yo‘lini tezlashtiring",
            "icon": "💎",
            "tiers": [
                (1, 100, 10, "100 XP yig‘ish"),
                (2, 1000, 50, "1000 XP yig‘ish"),
                (3, 5000, 150, "5000 XP yig‘ish"),
                (4, 10000, 300, "10 000 XP yig‘ish"),
                (5, 50000, 1000, "50 000 XP yig‘ish"),
                (6, 100000, 2500, "100 000 XP yig‘ish"),
                (7, 500000, 10000, "500 000 XP yig‘ish"),
            ],
        },
    ]

    @classmethod
    def _tiers(cls) -> list[AchievementTier]:
        tiers: list[AchievementTier] = []
        for group in cls.ACHIEVEMENT_GROUPS:
            for tier, target, reward_elo, description in group["tiers"]:
                tiers.append(
                    AchievementTier(
                        group_code=group["group_code"],
                        tier=tier,
                        target=target,
                        reward_elo=reward_elo,
                        title=group["title"],
                        description=description,
                        icon=group["icon"],
                    )
                )
        return tiers

    @classmethod
    def _group_meta(cls, group_code: str) -> dict:
        for group in cls.ACHIEVEMENT_GROUPS:
            if group["group_code"] == group_code:
                return group
        return {"group_code": group_code, "title": group_code, "subtitle": "", "icon": "🏆", "tiers": []}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def referral_link(cls, user_id: int) -> str | None:
        bot_username = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
        if not bot_username:
            return None
        return f"https://t.me/{bot_username}?start=ref_{quote(str(user_id))}"

    @classmethod
    async def ensure_progress_rows(cls, db: AsyncSession, user_id: int) -> None:
        for tier in cls._tiers():
            await db.execute(
                insert(UserAchievementProgress)
                .values(
                    user_id=user_id,
                    achievement_code=tier.achievement_code,
                    group_code=tier.group_code,
                    tier=tier.tier,
                    progress=0,
                    target=tier.target,
                    reward_elo=tier.reward_elo,
                    is_completed=False,
                    is_claimed=False,
                )
                .on_conflict_do_update(
                    index_elements=["user_id", "achievement_code"],
                    set_={
                        "target": tier.target,
                        "reward_elo": tier.reward_elo,
                    },
                )
            )
        await db.flush()

    @classmethod
    async def sync_derived_progress(cls, db: AsyncSession, user_id: int) -> None:
        xp_row = await db.get(UserXP, user_id)
        if xp_row:
            await cls.set_group_progress_at_least(
                db,
                user_id=user_id,
                group_code="xp_collector",
                progress_value=int(xp_row.total_xp or 0),
            )

        streak_row = await db.get(Streak, user_id)
        if streak_row:
            await cls.set_group_progress_at_least(
                db,
                user_id=user_id,
                group_code="daily_grinder",
                progress_value=int(streak_row.best_streak or streak_row.streak or 0),
            )

        rating = await db.get(UserDuelRating, user_id)
        if rating:
            await cls.set_group_progress_at_least(
                db,
                user_id=user_id,
                group_code="duel_wins",
                progress_value=int(rating.wins or 0),
            )

        duel_streak = await db.get(UserDuelWinStreakAchievement, user_id)
        if duel_streak:
            await cls.set_group_progress_at_least(
                db,
                user_id=user_id,
                group_code="duel_win_streak",
                progress_value=int(duel_streak.best_streak or 0),
            )

    @classmethod
    async def get_payload(cls, db: AsyncSession, user_id: int) -> dict:
        await cls.ensure_progress_rows(db, user_id)
        await cls.sync_derived_progress(db, user_id)

        result = await db.execute(
            select(UserAchievementProgress)
            .where(UserAchievementProgress.user_id == user_id)
            .order_by(UserAchievementProgress.group_code, UserAchievementProgress.tier)
        )
        rows = result.scalars().all()
        row_map = {row.achievement_code: row for row in rows}

        groups = []
        total_claimable = 0

        for group in cls.ACHIEVEMENT_GROUPS:
            group_code = group["group_code"]
            tier_payloads = []
            previous_claimed = True
            active_tier = None

            group_tiers = [t for t in cls._tiers() if t.group_code == group_code]
            for tier in group_tiers:
                row = row_map.get(tier.achievement_code)
                progress = int(row.progress or 0) if row else 0
                is_completed = bool(row.is_completed) if row else False
                is_claimed = bool(row.is_claimed) if row else False
                is_locked = not previous_claimed
                is_active = previous_claimed and not is_claimed
                is_claimable = is_active and is_completed and not is_claimed

                payload = {
                    "code": tier.achievement_code,
                    "group_code": tier.group_code,
                    "tier": tier.tier,
                    "title": tier.title,
                    "description": tier.description,
                    "icon": tier.icon,
                    "progress": progress,
                    "target": tier.target,
                    "reward_elo": tier.reward_elo,
                    "is_completed": is_completed,
                    "is_claimed": is_claimed,
                    "is_locked": is_locked,
                    "is_active": is_active,
                    "is_claimable": is_claimable,
                    "remaining": max(0, tier.target - progress),
                }

                if is_claimable:
                    total_claimable += 1

                if active_tier is None and is_active:
                    active_tier = payload

                tier_payloads.append(payload)
                previous_claimed = is_claimed

            if active_tier is None and tier_payloads:
                active_tier = tier_payloads[-1]

            groups.append(
                {
                    "group_code": group_code,
                    "title": group["title"],
                    "subtitle": group["subtitle"],
                    "icon": group["icon"],
                    "active_tier": active_tier,
                    "tiers": tier_payloads,
                }
            )

        return {
            "title": "Way to Legend 🔥",
            "referral_link": cls.referral_link(user_id),
            "referral_qualify_correct_answers": cls.REFERRAL_QUALIFY_CORRECT_ANSWERS,
            "total_claimable": total_claimable,
            "groups": groups,
        }

    @classmethod
    async def set_group_progress_at_least(
        cls,
        db: AsyncSession,
        user_id: int,
        group_code: str,
        progress_value: int,
    ) -> None:
        await cls.ensure_progress_rows(db, user_id)
        result = await db.execute(
            select(UserAchievementProgress)
            .where(
                UserAchievementProgress.user_id == user_id,
                UserAchievementProgress.group_code == group_code,
            )
            .with_for_update()
        )
        rows = result.scalars().all()

        for row in rows:
            row.progress = max(int(row.progress or 0), int(progress_value or 0))
            if row.progress >= int(row.target or 0):
                row.is_completed = True

        await db.flush()

    @classmethod
    async def increment_progress(
        cls,
        db: AsyncSession,
        user_id: int,
        group_code: str,
        amount: int = 1,
    ) -> None:
        if amount <= 0:
            return

        await cls.ensure_progress_rows(db, user_id)
        result = await db.execute(
            select(UserAchievementProgress)
            .where(
                UserAchievementProgress.user_id == user_id,
                UserAchievementProgress.group_code == group_code,
            )
            .with_for_update()
        )
        rows = result.scalars().all()
        current_total = max([int(row.progress or 0) for row in rows] or [0]) + int(amount)

        for row in rows:
            row.progress = current_total
            if row.progress >= int(row.target or 0):
                row.is_completed = True

        await db.flush()

        if group_code == "words_correct" and current_total >= cls.REFERRAL_QUALIFY_CORRECT_ANSWERS:
            await cls.qualify_referral_for_user(db, referred_user_id=user_id)

    @classmethod
    async def get_or_create_duel_win_streak(
        cls,
        db: AsyncSession,
        user_id: int,
    ) -> UserDuelWinStreakAchievement:
        await db.execute(
            insert(UserDuelWinStreakAchievement)
            .values(
                user_id=user_id,
                current_streak=0,
                best_streak=0,
            )
            .on_conflict_do_nothing(index_elements=["user_id"])
        )
        await db.flush()

        result = await db.execute(
            select(UserDuelWinStreakAchievement)
            .where(UserDuelWinStreakAchievement.user_id == user_id)
            .with_for_update()
        )
        return result.scalar_one()

    @classmethod
    async def update_duel_win_streak(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        won: bool,
    ) -> int:
        row = await cls.get_or_create_duel_win_streak(db, user_id)

        if won:
            row.current_streak = int(row.current_streak or 0) + 1
            row.best_streak = max(int(row.best_streak or 0), int(row.current_streak or 0))
        else:
            row.current_streak = 0

        await db.flush()

        if won:
            await cls.set_group_progress_at_least(
                db,
                user_id=user_id,
                group_code="duel_win_streak",
                progress_value=int(row.best_streak or 0),
            )

        return int(row.current_streak or 0)

    @classmethod
    async def record_duel_result(
        cls,
        db: AsyncSession,
        *,
        player1_id: int,
        player2_id: int,
        winner_id: int | None,
    ) -> None:
        if winner_id == player1_id:
            await cls.increment_progress(db, player1_id, "duel_wins", 1)
            await cls.update_duel_win_streak(db, user_id=player1_id, won=True)
            await cls.update_duel_win_streak(db, user_id=player2_id, won=False)
        elif winner_id == player2_id:
            await cls.increment_progress(db, player2_id, "duel_wins", 1)
            await cls.update_duel_win_streak(db, user_id=player2_id, won=True)
            await cls.update_duel_win_streak(db, user_id=player1_id, won=False)
        else:
            await cls.update_duel_win_streak(db, user_id=player1_id, won=False)
            await cls.update_duel_win_streak(db, user_id=player2_id, won=False)

    @classmethod
    async def mark_unit_completed_if_new(
        cls,
        db: AsyncSession,
        user_id: int,
        unit_id: int,
    ) -> bool:
        result = await db.execute(
            insert(UserCompletedUnitAchievement)
            .values(user_id=user_id, unit_id=unit_id)
            .on_conflict_do_nothing(index_elements=["user_id", "unit_id"])
            .returning(UserCompletedUnitAchievement.id)
        )
        inserted_id = result.scalar_one_or_none()
        if inserted_id is None:
            return False

        await cls.increment_progress(db, user_id, "units_completed", 1)
        return True

    @classmethod
    async def register_referral_start(
        cls,
        db: AsyncSession,
        *,
        referred_user_id: int,
        start_payload: str | None,
        is_new_bot_user: bool,
    ) -> None:
        if not is_new_bot_user:
            return

        payload = (start_payload or "").strip()
        if not payload.startswith("ref_"):
            return

        try:
            referrer_id = int(payload.replace("ref_", "", 1))
        except (TypeError, ValueError):
            return

        if referrer_id == referred_user_id:
            return

        referrer = await db.scalar(select(User.tg_id).where(User.tg_id == referrer_id))
        if not referrer:
            return

        await db.execute(
            insert(Referral)
            .values(
                referrer_id=referrer_id,
                referred_user_id=referred_user_id,
                status="pending",
            )
            .on_conflict_do_nothing(index_elements=["referred_user_id"])
        )
        await db.flush()

    @classmethod
    async def qualify_referral_for_user(cls, db: AsyncSession, referred_user_id: int) -> bool:
        result = await db.execute(
            select(Referral)
            .where(
                Referral.referred_user_id == referred_user_id,
                Referral.status == "pending",
            )
            .with_for_update()
        )
        referral = result.scalar_one_or_none()
        if not referral:
            return False

        referral.status = "qualified"
        referral.qualified_at = cls._now()
        await db.flush()

        await cls.increment_progress(db, int(referral.referrer_id), "invites_qualified", 1)
        return True

    @classmethod
    async def claim_reward(cls, db: AsyncSession, user_id: int, achievement_code: str) -> dict:
        await cls.ensure_progress_rows(db, user_id)
        await cls.sync_derived_progress(db, user_id)

        result = await db.execute(
            select(UserAchievementProgress)
            .where(
                UserAchievementProgress.user_id == user_id,
                UserAchievementProgress.achievement_code == achievement_code,
            )
            .with_for_update()
        )
        row = result.scalar_one_or_none()

        if not row:
            raise ValueError("Yutuq topilmadi")

        previous_result = await db.execute(
            select(UserAchievementProgress)
            .where(
                UserAchievementProgress.user_id == user_id,
                UserAchievementProgress.group_code == row.group_code,
                UserAchievementProgress.tier < row.tier,
                UserAchievementProgress.is_claimed.is_(False),
            )
            .limit(1)
        )
        if previous_result.scalar_one_or_none():
            raise ValueError("Avval oldingi bosqich mukofotini oling")

        if row.is_claimed:
            raise ValueError("Bu mukofot allaqachon olingan")

        if not row.is_completed or int(row.progress or 0) < int(row.target or 0):
            raise ValueError("Bu yutuq hali yakunlanmagan")

        rating = await DuelRatingService.get_or_create_rating(db, user_id)
        old_elo = int(rating.elo or DuelRatingService.DEFAULT_ELO)
        reward = int(row.reward_elo or 0)
        rating.elo = max(100, old_elo + reward)

        row.is_claimed = True
        row.claimed_at = cls._now()

        await db.flush()
        rank_info = DuelRatingService.rank_from_elo(rating.elo)

        return {
            "ok": True,
            "achievement_code": row.achievement_code,
            "group_code": row.group_code,
            "tier": row.tier,
            "reward_elo": reward,
            "old_elo": old_elo,
            "new_elo": int(rating.elo),
            **rank_info,
        }
