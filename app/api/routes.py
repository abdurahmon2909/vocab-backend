from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.models import Book, Collection, Unit, Word
from app.schemas.schemas import AnswerIn
from app.services.learning_service import LearningService
from app.services.mission_service import MissionService
from app.services.progress_service import ProgressService
from app.services.test_service import TestService
from app.services.xp_service import XPService

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

    return {
        "telegram": {
            "id": user.tg_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "photo_url": user.photo_url,
        },
        "xp": xp,
        "level": level,
        "level_progress": XPService.level_progress_percent(xp),
        "next_level_xp": XPService.next_level_xp(level),
        "streak": streak_row.streak if streak_row else 0,
        "best_streak": streak_row.best_streak if streak_row else 0,
        "missions": missions,
    }


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