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
    DEFAULT_ELO = 1000
    K_FACTOR = 32

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
    def calculate_delta(cls, player_elo: int, opponent_elo: int, actual_score: float) -> int:
        expected = cls.expected_score(player_elo, opponent_elo)
        return round(cls.K_FACTOR * (actual_score - expected))

    @classmethod
    async def get_or_create_rating(cls, db: AsyncSession, user_id: int) -> UserDuelRating:
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
    async def get_rank_position(cls, db: AsyncSession, user_id: int) -> int | None:
        rating = await cls.get_or_create_rating(db, user_id)
        result = await db.execute(
            select(func.count(UserDuelRating.user_id)).where(UserDuelRating.elo > rating.elo)
        )
        better_count = int(result.scalar() or 0)
        return better_count + 1

    @classmethod
    async def get_user_rating_payload(cls, db: AsyncSession, user_id: int) -> dict:
        rating = await cls.get_or_create_rating(db, user_id)
        rank_pos = await cls.get_rank_position(db, user_id)
        rank_info = cls.rank_from_elo(rating.elo)
        return {
            "elo": int(rating.elo or cls.DEFAULT_ELO),
            "duel_rank": rank_pos,
            "wins": int(rating.wins or 0),
            "losses": int(rating.losses or 0),
            "draws": int(rating.draws or 0),
            "games_played": int(rating.games_played or 0),
            **rank_info,
        }

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
            p1_score, p2_score = 1.0, 0.0
            p1.wins += 1
            p2.losses += 1
        elif winner_id == player2_id:
            p1_score, p2_score = 0.0, 1.0
            p1.losses += 1
            p2.wins += 1
        else:
            p1_score, p2_score = 0.5, 0.5
            p1.draws += 1
            p2.draws += 1

        p1_delta = cls.calculate_delta(old_p1_elo, old_p2_elo, p1_score)
        p2_delta = cls.calculate_delta(old_p2_elo, old_p1_elo, p2_score)

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
