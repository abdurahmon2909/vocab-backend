from datetime import datetime, timezone
import io

import edge_tts
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.models import (
    Book,
    Collection,
    Streak,
    Unit,
    User,
    UserWordProgress,
    UserXP,
    Word,
)
from app.schemas.schemas import AnswerIn, NicknameUpdateIn
from app.services.learning_service import LearningService
from app.services.leaderboard_service import LeaderboardService
from app.services.mission_service import MissionService
from app.services.progress_service import ProgressService
from app.services.test_service import TestService
from app.services.xp_service import XPService

router = APIRouter(prefix="/api")


def _display_name(user: User) -> str:
    return user.nickname or user.first_name or user.username or "Learner"


def _telegram_api_url() -> str:
    if not settings.BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN is required")
    return f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"


def _web_app_url() -> str:
    if not settings.WEB_APP_URL:
        raise HTTPException(status_code=500, detail="WEB_APP_URL is required")
    return settings.WEB_APP_URL


def _bot_start_link(sender_user_id: int | None = None) -> str | None:
    if not settings.BOT_USERNAME:
        return None

    payload = f"duel_from_{sender_user_id}" if sender_user_id else "duel"
    return f"https://t.me/{settings.BOT_USERNAME}?start={payload}"


def _bot_internal_secret() -> str:
    if not settings.BOT_INTERNAL_SECRET:
        raise HTTPException(status_code=500, detail="BOT_INTERNAL_SECRET is required")
    return settings.BOT_INTERNAL_SECRET


@router.post("/bot/start-user")
async def register_bot_start_user(
    data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if request.headers.get("x-bot-secret") != _bot_internal_secret():
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        tg_id = int(data.get("tg_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="tg_id noto‘g‘ri")

    result = await db.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if not user:
        user = User(
            tg_id=tg_id,
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            username=data.get("username"),
            language_code=data.get("language_code"),
            is_premium=bool(data.get("is_premium", False)),
            is_bot_started=True,
            bot_started_at=now,
            bot_blocked_at=None,
            last_seen_at=now,
        )
        db.add(user)
        await db.flush()

        xp = await db.get(UserXP, tg_id)
        if not xp:
            db.add(UserXP(user_id=tg_id, total_xp=0))

        streak = await db.get(Streak, tg_id)
        if not streak:
            db.add(Streak(user_id=tg_id, streak=0, best_streak=0, last_active_date=None))
    else:
        user.first_name = data.get("first_name")
        user.last_name = data.get("last_name")
        user.username = data.get("username")
        user.language_code = data.get("language_code")
        user.is_premium = bool(data.get("is_premium", False))
        user.is_bot_started = True
        if not user.bot_started_at:
            user.bot_started_at = now
        user.bot_blocked_at = None
        user.last_seen_at = now

    await db.commit()

    return {
        "ok": True,
        "user_id": tg_id,
        "start_payload": data.get("start_payload"),
    }


@router.get("/user")
async def get_user(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    xp_row = getattr(user, "xp", None)
    streak_row = getattr(user, "streak", None)

    if not xp_row:
        xp_row = await db.get(UserXP, user.tg_id)

    if not streak_row:
        streak_row = await db.get(Streak, user.tg_id)

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


@router.patch("/user/nickname")
async def update_nickname(
    data: NicknameUpdateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
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
    limit: int = Query(default=50, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await LeaderboardService.get_leaderboard(
        db=db,
        current_user_id=user.tg_id,
        limit=limit,
        offset=offset,
    )


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await ProgressService.get_stats(db, user.tg_id)


@router.get("/duel/challenge-users")
async def get_duel_challenge_users(
    q: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(User, UserXP.total_xp)
        .outerjoin(UserXP, UserXP.user_id == User.tg_id)
        .where(User.tg_id != user.tg_id)
    )

    if q:
        search = f"%{q.strip()}%"
        stmt = stmt.where(
            (User.nickname.ilike(search))
            | (User.first_name.ilike(search))
            | (User.last_name.ilike(search))
            | (User.username.ilike(search))
        )

    stmt = stmt.order_by(
        User.last_seen_at.desc().nullslast(),
        User.created_at.desc(),
    ).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    users = []
    for target_user, total_xp in rows:
        xp = int(total_xp or 0)
        level = XPService.level_from_xp(xp)

        is_bot_started = bool(getattr(target_user, "is_bot_started", False))
        bot_blocked = bool(getattr(target_user, "bot_blocked_at", None))

        users.append(
            {
                "user_id": target_user.tg_id,
                "display_name": _display_name(target_user),
                "username": target_user.username,
                "photo_url": target_user.photo_url,
                "xp": xp,
                "level": level,
                "is_bot_started": is_bot_started,
                "bot_blocked": bot_blocked,
                "challenge_available": is_bot_started and not bot_blocked,
                "bot_start_link": _bot_start_link(user.tg_id),
                "last_seen_at": target_user.last_seen_at.isoformat() if target_user.last_seen_at else None,
            }
        )

    return users


@router.post("/duel/challenge-user")
async def challenge_duel_user(
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    target_user_id = data.get("target_user_id")

    try:
        target_user_id = int(target_user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="target_user_id noto‘g‘ri")

    if target_user_id == user.tg_id:
        raise HTTPException(status_code=400, detail="O‘zingizni duelga chaqira olmaysiz")

    target_result = await db.execute(select(User).where(User.tg_id == target_user_id))
    target_user = target_result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="Raqib topilmadi")

    invite_link = _bot_start_link(user.tg_id)

    if not getattr(target_user, "is_bot_started", False):
        return {
            "ok": False,
            "reason": "user_not_started_bot",
            "message": "Bu foydalanuvchi botni hali ishga tushirmagan. Invite linkni unga yuboring.",
            "invite_link": invite_link,
            "target_user_id": target_user.tg_id,
            "target_display_name": _display_name(target_user),
        }

    if getattr(target_user, "bot_blocked_at", None):
        return {
            "ok": False,
            "reason": "bot_blocked",
            "message": "Bu foydalanuvchi botni bloklagan bo‘lishi mumkin. Invite linkni unga yuboring.",
            "invite_link": invite_link,
            "target_user_id": target_user.tg_id,
            "target_display_name": _display_name(target_user),
        }

    sender_name = _display_name(user)

    text = (
        f"⚔️ <b>{sender_name}</b> sizni duelga chorlamoqda!\n\n"
        "Qurollaning! WordLegends jang maydoni sizni kutmoqda."
    )

    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post(
            _telegram_api_url(),
            json={
                "chat_id": target_user.tg_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {
                                "text": "⚔️ DUEL",
                                "web_app": {"url": _web_app_url()},
                            }
                        ]
                    ]
                },
            },
        )

    result = response.json()

    if not response.is_success or not result.get("ok"):
        description = str(result.get("description", "Telegram xabar yuborilmadi"))
        now = datetime.now(timezone.utc)

        if (
            response.status_code in (400, 403)
            or "blocked" in description.lower()
            or "chat not found" in description.lower()
        ):
            target_user.is_bot_started = False
            target_user.bot_blocked_at = now
            await db.commit()

            return {
                "ok": False,
                "reason": "bot_blocked",
                "message": "Taklif yuborilmadi. Raqib botni bloklagan yoki botni start qilmagan bo‘lishi mumkin.",
                "invite_link": invite_link,
                "target_user_id": target_user.tg_id,
                "target_display_name": _display_name(target_user),
                "telegram_error": description,
            }

        raise HTTPException(status_code=400, detail=description)

    return {
        "ok": True,
        "message": "Duel taklifi yuborildi",
        "target_user_id": target_user.tg_id,
        "target_display_name": _display_name(target_user),
    }


@router.get("/collections")
async def get_collections(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await ProgressService.get_collections_with_progress(db, user.tg_id)


@router.get("/collections/{collection_id}/books")
async def get_collection_books(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
):
    return await ProgressService.get_books_with_progress(db, user.tg_id)


@router.get("/books/{book_id}/units")
async def get_units(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    return await ProgressService.get_units_with_progress(db, user.tg_id, book_id)


@router.get("/units/{unit_id}/access")
async def get_unit_access(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await ProgressService.can_access_unit(db, user.tg_id, unit_id)


@router.get("/units/{unit_id}/words")
async def get_words(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Word)
        .join(UserWordProgress, Word.id == UserWordProgress.word_id)
        .where(
            UserWordProgress.user_id == user.tg_id,
            UserWordProgress.mastery_score < 60,
        )
        .limit(200)
    )

    return result.scalars().all()


@router.get("/weak-words/test")
async def get_weak_test(
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Word)
        .join(UserWordProgress, Word.id == UserWordProgress.word_id)
        .where(
            UserWordProgress.user_id == user.tg_id,
            UserWordProgress.mastery_score < 60,
        )
        .order_by(func.random())
        .limit(limit)
    )

    words = result.scalars().all()
    return TestService._build_questions(words, limit)


@router.post("/answer")
async def answer(
    data: AnswerIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    word = await db.get(Word, data.word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    if not data.mode.startswith("weak_"):
        if word.unit_id != data.unit_id:
            raise HTTPException(status_code=400, detail="Word does not belong to this unit")

        access = await ProgressService.can_access_unit(db, user.tg_id, data.unit_id)
        if not access["allowed"]:
            raise HTTPException(status_code=403, detail=access["reason"])

    return await LearningService.process_answer(
        db=db,
        user_id=user.tg_id,
        word_id=data.word_id,
        unit_id=word.unit_id,
        mode=data.mode,
        is_correct=data.is_correct,
        user_answer=data.user_answer,
        correct_answer=data.correct_answer,
        answer_session_id=data.answer_session_id,
    )


@router.post("/mode-progress/best")
async def save_mode_best_progress(
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        unit_id = int(data.get("unit_id"))
        mode = str(data.get("mode"))
        total_questions = int(data.get("total_questions", 0))
        correct_answers = int(data.get("correct_answers", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid payload")

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
async def tts(
    text: str = Query(..., min_length=1, max_length=120),
    user: User = Depends(get_current_user),
):
    try:
        communicate = edge_tts.Communicate(
            text=text,
            voice="en-US-GuyNeural",
        )

        audio_stream = io.BytesIO()

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_stream.write(chunk["data"])

        audio_stream.seek(0)

        return StreamingResponse(audio_stream, media_type="audio/mpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))