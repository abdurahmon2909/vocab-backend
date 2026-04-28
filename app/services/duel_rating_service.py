from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import UserDuelRating


@dataclass(frozen=True)
class RankInfo:
    title: str
    icon: str
    min_elo: int


class DuelRatingService:
    DEFAULT_ELO = 800

    # Yumshoq ELO:
    # winner: +8 dan +28 gacha
    # loser: winner olganining taxminan yarmi yo‘qotadi
    MIN_WIN_GAIN = 8
    MAX_WIN_GAIN = 28
    MIN_LOSS = 4

    # Winner gain hisoblash uchun asosiy kuch.
    # Equal ELO bo‘lsa taxminan +18 beradi.
    K_WIN = 36

    RANKS: list[RankInfo] = [
        RankInfo("Bronze", "🥉", 0),
        RankInfo("Silver", "⚪", 1000),
        RankInfo("Gold", "🟡", 1200),
        RankInfo("Platinum", "💠", 1400),
        RankInfo("Diamond", "💎", 1600),
        RankInfo("Master", "👑", 1800),
        RankInfo("Legend", "🔥", 2000),
    ]

    @classmethod
    def rank_from_elo(cls, elo: int | None) -> dict:
        value = int(elo or cls.DEFAULT_ELO)
        current = cls.RANKS[0]

        for rank in cls.RANKS:
            if value >= rank.min_elo:
                current = rank
            else:
                break

        return {
            "rank_title": current.title,
            "rank_icon": current.icon,
            "rank_min_elo": current.min_elo,
        }

    @staticmethod
    def expected_score(player_elo: int, opponent_elo: int) -> float:
        return 1 / (1 + 10 ** ((opponent_elo - player_elo) / 400))

    @classmethod
    async def get_or_create_rating(
        cls,
        db: AsyncSession,
        user_id: int,
    ) -> UserDuelRating:
        result = await db.execute(
            select(UserDuelRating).where(UserDuelRating.user_id == user_id)
        )
        rating = result.scalar_one_or_none()

        if rating:
            return rating

        rating = UserDuelRating(
            user_id=user_id,
            elo=cls.DEFAULT_ELO,
            wins=0,
            losses=0,
            draws=0,
            games_played=0,
        )
        db.add(rating)
        await db.flush()
        return rating

    @classmethod
    async def get_rank_position(cls, db: AsyncSession, user_id: int) -> int:
        rating = await cls.get_or_create_rating(db, user_id)

        result = await db.execute(
            select(func.count(UserDuelRating.user_id)).where(
                UserDuelRating.elo > rating.elo
            )
        )
        better_count = int(result.scalar() or 0)
        return better_count + 1

    @classmethod
    async def get_user_rating_payload(cls, db: AsyncSession, user_id: int) -> dict:
        rating = await cls.get_or_create_rating(db, user_id)
        rank_position = await cls.get_rank_position(db, user_id)
        rank_info = cls.rank_from_elo(rating.elo)

        return {
            "elo": int(rating.elo or cls.DEFAULT_ELO),
            "duel_rank": rank_position,
            "wins": int(rating.wins or 0),
            "losses": int(rating.losses or 0),
            "draws": int(rating.draws or 0),
            "games_played": int(rating.games_played or 0),
            **rank_info,
        }

    @classmethod
    def _winner_gain(cls, winner_elo: int, loser_elo: int) -> int:
        expected = cls.expected_score(winner_elo, loser_elo)
        calculated_gain = round(cls.K_WIN * (1 - expected))

        return max(
            cls.MIN_WIN_GAIN,
            min(cls.MAX_WIN_GAIN, calculated_gain),
        )

    @classmethod
    def _loser_loss(cls, winner_gain: int) -> int:
        return max(cls.MIN_LOSS, round(winner_gain / 2))

    @classmethod
    async def apply_duel_result(
        cls,
        db: AsyncSession,
        *,
        player1_id: int,
        player2_id: int,
        winner_id: int | None,
    ) -> dict:
        p1 = await cls.get_or_create_rating(db, player1_id)
        p2 = await cls.get_or_create_rating(db, player2_id)

        old_p1_elo = int(p1.elo or cls.DEFAULT_ELO)
        old_p2_elo = int(p2.elo or cls.DEFAULT_ELO)

        if winner_id == player1_id:
            winner_gain = cls._winner_gain(old_p1_elo, old_p2_elo)
            loser_loss = cls._loser_loss(winner_gain)

            p1_delta = winner_gain
            p2_delta = -loser_loss

            p1.wins += 1
            p2.losses += 1

        elif winner_id == player2_id:
            winner_gain = cls._winner_gain(old_p2_elo, old_p1_elo)
            loser_loss = cls._loser_loss(winner_gain)

            p1_delta = -loser_loss
            p2_delta = winner_gain

            p1.losses += 1
            p2.wins += 1

        else:
            # Hozircha draw neytral: hech kim ELO yo‘qotmaydi/olmaydi.
            p1_delta = 0
            p2_delta = 0

            p1.draws += 1
            p2.draws += 1

        p1.elo = max(100, old_p1_elo + p1_delta)
        p2.elo = max(100, old_p2_elo + p2_delta)

        p1.games_played += 1
        p2.games_played += 1

        await db.flush()

        return {
            "player1": {
                "old_elo": old_p1_elo,
                "new_elo": int(p1.elo),
                "delta": int(p1_delta),
                **cls.rank_from_elo(p1.elo),
            },
            "player2": {
                "old_elo": old_p2_elo,
                "new_elo": int(p2.elo),
                "delta": int(p2_delta),
                **cls.rank_from_elo(p2.elo),
            },
        }