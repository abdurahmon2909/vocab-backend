from datetime import date, datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Mission,
    UserMissionProgress,
    UserXP,
    XPEvent,
    ModeProgress,
)
from app.services.xp_service import XPService


REQUIRED_UNIT_UNLOCK_MODES = ["writing", "test", "listening"]
REQUIRED_UNIT_UNLOCK_PERCENT = 80


class MissionService:
    _missions_cache: list[dict] | None = None
    _missions_cache_until: datetime | None = None

    # user_id:unit_id:date cache — bitta unit qayta-qayta sanalib ketmasin
    _completed_unit_cache: set[str] = set()

    @staticmethod
    async def _get_active_missions_cached(db: AsyncSession) -> list[dict]:
        now = datetime.utcnow()

        if (
            MissionService._missions_cache is not None
            and MissionService._missions_cache_until is not None
            and MissionService._missions_cache_until > now
        ):
            return MissionService._missions_cache

        result = await db.execute(
            select(Mission)
            .where(Mission.is_active == True)
            .order_by(Mission.id)
        )
        missions = result.scalars().all()

        MissionService._missions_cache = [
            {
                "id": mission.id,
                "code": mission.code,
                "title": mission.title,
                "mission_type": mission.mission_type,
                "target": mission.target,
                "xp_reward": mission.xp_reward,
            }
            for mission in missions
        ]

        MissionService._missions_cache_until = now + timedelta(seconds=60)
        return MissionService._missions_cache

    @staticmethod
    def clear_cache():
        MissionService._missions_cache = None
        MissionService._missions_cache_until = None
        MissionService._completed_unit_cache.clear()

    @staticmethod
    async def get_daily_missions(db: AsyncSession, user_id: int):
        today = date.today()
        missions = await MissionService._get_active_missions_cached(db)

        output = []

        mission_ids = [m["id"] for m in missions]

        existing_map = {}

        if mission_ids:
            progress_result = await db.execute(
                select(UserMissionProgress).where(
                    UserMissionProgress.user_id == user_id,
                    UserMissionProgress.mission_id.in_(mission_ids),
                    UserMissionProgress.date_key == today,
                )
            )
            progresses = progress_result.scalars().all()
            existing_map = {p.mission_id: p for p in progresses}

        for mission in missions:
            progress = existing_map.get(mission["id"])

            if not progress:
                progress = UserMissionProgress(
                    user_id=user_id,
                    mission_id=mission["id"],
                    progress=0,
                    is_completed=False,
                    date_key=today,
                )
                db.add(progress)
                await db.flush()

            output.append({
                "id": mission["id"],
                "code": mission["code"],
                "title": mission["title"],
                "mission_type": mission["mission_type"],
                "target": mission["target"],
                "progress": progress.progress,
                "xp_reward": mission["xp_reward"],
                "is_completed": progress.is_completed,
            })

        await db.commit()
        return output

    @staticmethod
    async def increment_many(
        db: AsyncSession,
        user_id: int,
        increments: dict[str, int],
    ):
        """
        Batch mission increment.

        increments example:
        {
            "questions": 1,
            "weak_words": 1,
            "complete_unit": 1
        }

        Mission match qiladi:
        - mission.mission_type
        - yoki mission.code
        """

        today = date.today()

        if not increments:
            return []

        missions = await MissionService._get_active_missions_cached(db)

        matched_missions = []

        for mission in missions:
            amount = 0

            if mission["mission_type"] in increments:
                amount += int(increments.get(mission["mission_type"], 0) or 0)

            if mission["code"] in increments and mission["code"] != mission["mission_type"]:
                amount += int(increments.get(mission["code"], 0) or 0)

            if amount > 0:
                matched_missions.append((mission, amount))

        if not matched_missions:
            return []

        mission_ids = [m["id"] for m, _ in matched_missions]

        progress_result = await db.execute(
            select(UserMissionProgress).where(
                UserMissionProgress.user_id == user_id,
                UserMissionProgress.mission_id.in_(mission_ids),
                UserMissionProgress.date_key == today,
            )
        )
        progresses = progress_result.scalars().all()
        progress_map = {p.mission_id: p for p in progresses}

        xp_to_add = 0
        xp_events = []
        updated = []

        for mission, amount in matched_missions:
            progress = progress_map.get(mission["id"])

            if not progress:
                progress = UserMissionProgress(
                    user_id=user_id,
                    mission_id=mission["id"],
                    progress=0,
                    is_completed=False,
                    date_key=today,
                )
                db.add(progress)
                await db.flush()
                progress_map[mission["id"]] = progress

            if progress.is_completed:
                updated.append((mission, progress))
                continue

            progress.progress = min(
                int(mission["target"] or 0),
                int(progress.progress or 0) + amount,
            )

            if progress.progress >= mission["target"]:
                progress.is_completed = True
                xp_to_add += int(mission["xp_reward"] or 0)

                xp_events.append(
                    XPEvent(
                        user_id=user_id,
                        amount=int(mission["xp_reward"] or 0),
                        reason=f"mission:{mission['code']}",
                    )
                )

            updated.append((mission, progress))

        if xp_to_add > 0:
            xp_row = await db.get(UserXP, user_id)

            if not xp_row:
                xp_row = UserXP(user_id=user_id, total_xp=0)
                db.add(xp_row)
                await db.flush()

            xp_row.total_xp += xp_to_add

            for event in xp_events:
                db.add(event)

        return [
            {
                "id": mission["id"],
                "code": mission["code"],
                "title": mission["title"],
                "mission_type": mission["mission_type"],
                "target": mission["target"],
                "progress": progress.progress,
                "xp_reward": mission["xp_reward"],
                "is_completed": progress.is_completed,
            }
            for mission, progress in updated
        ]

    @staticmethod
    async def increment(
        db: AsyncSession,
        user_id: int,
        mission_type: str,
        amount: int = 1,
    ):
        return await MissionService.increment_many(
            db=db,
            user_id=user_id,
            increments={mission_type: amount},
        )

    @staticmethod
    async def is_unit_completed_by_modes(
        db: AsyncSession,
        user_id: int,
        unit_id: int,
    ) -> bool:
        result = await db.execute(
            select(ModeProgress).where(
                ModeProgress.user_id == user_id,
                ModeProgress.unit_id == unit_id,
                ModeProgress.mode.in_(REQUIRED_UNIT_UNLOCK_MODES),
            )
        )

        rows = result.scalars().all()
        progress_map = {row.mode: int(row.progress_percent or 0) for row in rows}

        return all(
            progress_map.get(mode, 0) >= REQUIRED_UNIT_UNLOCK_PERCENT
            for mode in REQUIRED_UNIT_UNLOCK_MODES
        )

    @staticmethod
    async def mark_unit_completed_if_needed(
        db: AsyncSession,
        user_id: int,
        unit_id: int,
    ):
        today = date.today()
        cache_key = f"{user_id}:{unit_id}:{today.isoformat()}"

        if cache_key in MissionService._completed_unit_cache:
            return []

        is_completed = await MissionService.is_unit_completed_by_modes(
            db=db,
            user_id=user_id,
            unit_id=unit_id,
        )

        if not is_completed:
            return []

        MissionService._completed_unit_cache.add(cache_key)

        return await MissionService.increment_many(
            db=db,
            user_id=user_id,
            increments={
                "complete_unit": 1,
                "unit_completed": 1,
                "units": 1,
            },
        )