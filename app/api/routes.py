from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.models import Book, Collection, Unit, Word, UserXP, Streak
from app.schemas.schemas import AnswerIn, NicknameUpdateIn
from app.services.learning_service import LearningService
from app.services.leaderboard_service import LeaderboardService
from app.services.mission_service import MissionService
from app.services.progress_service import ProgressService
from app.services.test_service import TestService
from app.services.xp_service import XPService
from fastapi.responses import StreamingResponse
import edge_tts
import io
# ✅ ROUTER aniqlanishi KERAK!
router = APIRouter(prefix="/api")


@router.get("/user")
async def get_user(
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    # XP va Streak ni alohida so'rab olish
    xp_result = await db.execute(
        select(UserXP).where(UserXP.user_id == user.tg_id)
    )
    xp_row = xp_result.scalar_one_or_none()

    streak_result = await db.execute(
        select(Streak).where(Streak.user_id == user.tg_id)
    )
    streak_row = streak_result.scalar_one_or_none()

    xp = xp_row.total_xp if xp_row else 0
    level = XPService.level_from_xp(xp)

    missions = await MissionService.get_daily_missions(db, user.tg_id)

    display_name = (
            user.nickname
            or user.first_name
            or user.username
            or "Learner"
    )

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


@router.patch("/user/nickname")
async def update_nickname(
        data: NicknameUpdateIn,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    nickname = data.nickname.strip()

    if len(nickname) < 2:
        raise HTTPException(status_code=400, detail="Nickname kamida 2 ta belgidan iborat bo‘lishi kerak")

    if len(nickname) > 32:
        raise HTTPException(status_code=400, detail="Nickname 32 ta belgidan oshmasligi kerak")

    user.nickname = nickname
    await db.commit()
    await db.refresh(user)

    return {
        "ok": True,
        "nickname": user.nickname,
        "display_name": user.nickname or user.first_name or user.username or "Learner",
    }


@router.get("/leaderboard")
async def get_leaderboard(
        limit: int = Query(default=50, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    return await LeaderboardService.get_leaderboard(
        db=db,
        current_user_id=user.tg_id,
        limit=limit,
    )


@router.get("/stats")
async def get_stats(
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    return await ProgressService.get_stats(db, user.tg_id)


@router.get("/collections")
async def get_collections(
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    return await ProgressService.get_collections_with_progress(db, user.tg_id)


@router.get("/collections/{collection_id}/books")
async def get_collection_books(
        collection_id: int,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    collection = await db.get(Collection, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    return await ProgressService.get_collection_books_with_progress(
        db,
        user.tg_id,
        collection_id,
    )


@router.get("/books")
async def get_books(
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    return await ProgressService.get_books_with_progress(db, user.tg_id)


@router.get("/books/{book_id}/units")
async def get_units(
        book_id: int,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    return await ProgressService.get_units_with_progress(db, user.tg_id, book_id)


@router.get("/units/{unit_id}/access")
async def get_unit_access(
        unit_id: int,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    return await ProgressService.can_access_unit(db, user.tg_id, unit_id)


@router.get("/units/{unit_id}/words")
async def get_words(
        unit_id: int,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    unit = await db.get(Unit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    access = await ProgressService.can_access_unit(db, user.tg_id, unit_id)
    if not access["allowed"]:
        raise HTTPException(status_code=403, detail=access["reason"])

    return await ProgressService.get_words_with_progress(db, user.tg_id, unit_id)


@router.get("/units/{unit_id}/test")
async def get_unit_test(
        unit_id: int,
        limit: int = Query(default=20, ge=1, le=50),
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    unit = await db.get(Unit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    access = await ProgressService.can_access_unit(db, user.tg_id, unit_id)
    if not access["allowed"]:
        raise HTTPException(status_code=403, detail=access["reason"])

    return await TestService.build_unit_questions(db, unit_id, limit)


@router.get("/weak-words")
async def get_weak_words(
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    words = await TestService.build_weak_questions(db, user.tg_id, 50)
    word_ids = [w["word_id"] for w in words]

    if not word_ids:
        return []

    result = await db.execute(select(Word).where(Word.id.in_(word_ids)))
    raw_words = result.scalars().all()

    return [
        {
            "id": word.id,
            "unit_id": word.unit_id,
            "english": word.english,
            "uzbek": word.uzbek,
            "definition": word.definition,
            "example": word.example,
        }
        for word in raw_words
    ]


@router.get("/weak-words/test")
async def get_weak_test(
        limit: int = Query(default=20, ge=1, le=50),
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    return await TestService.build_weak_questions(db, user.tg_id, limit)


@router.post("/answer")
async def answer(
        data: AnswerIn,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    word = await db.get(Word, data.word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    if word.unit_id != data.unit_id:
        raise HTTPException(status_code=400, detail="Word does not belong to this unit")

    access = await ProgressService.can_access_unit(db, user.tg_id, data.unit_id)
    if not access["allowed"]:
        raise HTTPException(status_code=403, detail=access["reason"])

    return await LearningService.process_answer(
        db=db,
        user_id=user.tg_id,
        word_id=data.word_id,
        unit_id=data.unit_id,
        mode=data.mode,
        is_correct=data.is_correct,
        user_answer=data.user_answer,
        correct_answer=data.correct_answer,
    )

@router.post("/mode-progress/best")
async def save_mode_best_progress(
        data: dict,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    unit_id = int(data.get("unit_id"))
    mode = str(data.get("mode"))
    total_questions = int(data.get("total_questions", 0))
    correct_answers = int(data.get("correct_answers", 0))

    if mode not in ["test", "writing", "listening", "weak_test", "weak_writing"]:
        raise HTTPException(status_code=400, detail="Invalid mode")

    progress = await LearningService.update_mode_best_progress(
        db=db,
        user_id=user.tg_id,
        unit_id=unit_id,
        mode=mode,
        total_questions=total_questions,
        correct_answers=correct_answers,
    )

    mission_updates = await MissionService.mark_unit_completed_if_needed(
        db=db,
        user_id=user.tg_id,
        unit_id=unit_id,
    )

    await db.commit()

    return {
        "ok": True,
        "mode": progress.mode,
        "unit_id": progress.unit_id,
        "total_questions": progress.total_questions,
        "correct_answers": progress.correct_answers,
        "progress_percent": progress.progress_percent,
        "is_completed": progress.is_completed,
        "unit_completed": await MissionService.is_unit_completed_by_modes(
            db=db,
            user_id=user.tg_id,
            unit_id=unit_id,
        ),
        "mission_updates": mission_updates,
    }

@router.get("/tts")
async def tts(text: str):
    try:
        communicate = edge_tts.Communicate(
            text=text,
            voice="en-US-GuyNeural"  # 🔥 juda yaxshi erkak ovoz
        )

        audio_stream = io.BytesIO()

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_stream.write(chunk["data"])

        audio_stream.seek(0)

        return StreamingResponse(audio_stream, media_type="audio/mpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))