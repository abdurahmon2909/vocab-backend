from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Mission, UserMissionProgress, UserXP, XPEvent
from app.services.xp_service import XPService


class MissionService:
    @staticmethod
    async def get_daily_missions(db: AsyncSession, user_id: int):
        today = date.today()

        missions_result = await db.execute(
            select(Mission).where(Mission.is_active == True).order_by(Mission.id)
        )
        missions = missions_result.scalars().all()

        output = []

        for mission in missions:
            progress_result = await db.execute(
                select(UserMissionProgress).where(
                    UserMissionProgress.user_id == user_id,
                    UserMissionProgress.mission_id == mission.id,
                    UserMissionProgress.date_key == today,
                )
            )
            progress = progress_result.scalar_one_or_none()

            if not progress:
                progress = UserMissionProgress(
                    user_id=user_id,
                    mission_id=mission.id,
                    progress=0,
                    is_completed=False,
                    date_key=today,
                )
                db.add(progress)
                await db.flush()

            output.append({
                "id": mission.id,
                "code": mission.code,
                "title": mission.title,
                "mission_type": mission.mission_type,
                "target": mission.target,
                "progress": progress.progress,
                "xp_reward": mission.xp_reward,
                "is_completed": progress.is_completed,
            })

        await db.commit()
        return output

    @staticmethod
    async def increment(
        db: AsyncSession,
        user_id: int,
        mission_type: str,
        amount: int = 1,
    ):
        today = date.today()

        missions_result = await db.execute(
            select(Mission).where(
                Mission.is_active == True,
                Mission.mission_type == mission_type,
            )
        )
        missions = missions_result.scalars().all()

        updated = []

        for mission in missions:
            progress_result = await db.execute(
                select(UserMissionProgress).where(
                    UserMissionProgress.user_id == user_id,
                    UserMissionProgress.mission_id == mission.id,
                    UserMissionProgress.date_key == today,
                )
            )
            progress = progress_result.scalar_one_or_none()

            if not progress:
                progress = UserMissionProgress(
                    user_id=user_id,
                    mission_id=mission.id,
                    progress=0,
                    is_completed=False,
                    date_key=today,
                )
                db.add(progress)
                await db.flush()

            if progress.is_completed:
                updated.append((mission, progress))
                continue

            progress.progress = min(mission.target, progress.progress + amount)

            if progress.progress >= mission.target:
                progress.is_completed = True

                xp_row = await db.get(UserXP, user_id)
                if not xp_row:
                    xp_row = UserXP(user_id=user_id, total_xp=0)
                    db.add(xp_row)
                    await db.flush()

                xp_row.total_xp += mission.xp_reward

                db.add(XPEvent(
                    user_id=user_id,
                    amount=mission.xp_reward,
                    reason=f"mission:{mission.code}",
                ))

            updated.append((mission, progress))

        return [
            {
                "id": mission.id,
                "code": mission.code,
                "title": mission.title,
                "mission_type": mission.mission_type,
                "target": mission.target,
                "progress": progress.progress,
                "xp_reward": mission.xp_reward,
                "is_completed": progress.is_completed,
            }
            for mission, progress in updated
        ]