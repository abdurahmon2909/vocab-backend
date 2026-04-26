from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.models import Book, Collection, Unit, Word
from app.schemas.schemas import AnswerIn, NicknameUpdateIn
from app.services.learning_service import LearningService
from app.services.leaderboard_service import LeaderboardService
from app.services.mission_service import MissionService
from app.services.progress_service import ProgressService
from app.services.test_service import TestService
from app.services.xp_service import XPService

# ✅ PREFIX "/api" bilan
router = APIRouter(prefix="/api")


@router.get("/user")
async def get_user(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    xp_row = user.xp
    streak_row = user.streak
    xp = xp_row.total_xp if xp_row else 0
    level = XPService.level_from_xp(xp)
    missions = await MissionService.get_daily_missions(db, user.tg_id)
    display_name = user.nickname or user.first_name or user.username or "Learner"

    return {
        "telegram": {
            "id": user.tg_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "photo_url": user.photo_url,
        },
        "nickname": user.nickname,
        "display_name": display_name,
        "xp": xp,
        "level": level,
        "level_progress": XPService.level_progress_percent(xp),
        "next_level_xp": XPService.next_level_xp(level),
        "streak": streak_row.streak if streak_row else 0,
        "best_streak": streak_row.best_streak if streak_row else 0,
        "missions": missions,
    }


@router.get("/collections")
async def get_collections(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    return await ProgressService.get_collections_with_progress(db, user.tg_id)


# 🔥 TEST endpoint - authorization talab qilmaydi
@router.get("/test")
async def test_endpoint():
    return {"message": "API is working!"}