from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Collection, Book, Unit, ModeProgress


REQUIRED_MODES = ["writing", "test", "listening"]
REQUIRED_PERCENT = 80


async def get_collections(db: AsyncSession):
    result = await db.execute(
        select(Collection)
        .where(Collection.is_active == True)
        .order_by(Collection.order_index, Collection.id)
    )
    return result.scalars().all()


async def get_collection_books(db: AsyncSession, collection_id: int):
    result = await db.execute(
        select(Book)
        .where(Book.collection_id == collection_id, Book.is_active == True)
        .order_by(Book.order_index, Book.id)
    )
    return result.scalars().all()


async def get_book_units_with_access(db: AsyncSession, user_id: int, book_id: int):
    result = await db.execute(
        select(Unit)
        .where(Unit.book_id == book_id, Unit.is_active == True)
        .order_by(Unit.order_index, Unit.id)
    )
    units = result.scalars().all()

    response = []

    for index, unit in enumerate(units):
        if index == 0:
            response.append({
                "id": unit.id,
                "book_id": unit.book_id,
                "title": unit.title,
                "order_index": unit.order_index,
                "is_locked": False,
                "unlock_reason": None,
            })
            continue

        previous_unit = units[index - 1]
        unlocked = await is_previous_unit_completed(db, user_id, previous_unit.id)

        response.append({
            "id": unit.id,
            "book_id": unit.book_id,
            "title": unit.title,
            "order_index": unit.order_index,
            "is_locked": not unlocked,
            "unlock_reason": None if unlocked else "Oldingi unitda Writing, Test va Listening mode kamida 80% bo‘lishi kerak.",
        })

    return response


async def is_previous_unit_completed(db: AsyncSession, user_id: int, unit_id: int) -> bool:
    result = await db.execute(
        select(ModeProgress)
        .where(
            ModeProgress.user_id == user_id,
            ModeProgress.unit_id == unit_id,
            ModeProgress.mode.in_(REQUIRED_MODES),
        )
    )
    progresses = result.scalars().all()

    progress_map = {p.mode: p.progress_percent for p in progresses}

    for mode in REQUIRED_MODES:
        if progress_map.get(mode, 0) < REQUIRED_PERCENT:
            return False

    return True


async def can_access_unit(db: AsyncSession, user_id: int, unit_id: int):
    current_unit_result = await db.execute(
        select(Unit).where(Unit.id == unit_id)
    )
    current_unit = current_unit_result.scalar_one_or_none()

    if not current_unit:
        return {
            "allowed": False,
            "reason": "Unit topilmadi.",
        }

    units_result = await db.execute(
        select(Unit)
        .where(Unit.book_id == current_unit.book_id, Unit.is_active == True)
        .order_by(Unit.order_index, Unit.id)
    )
    units = units_result.scalars().all()

    current_index = next((i for i, u in enumerate(units) if u.id == unit_id), None)

    if current_index is None:
        return {
            "allowed": False,
            "reason": "Unit bu kitob ichida topilmadi.",
        }

    if current_index == 0:
        return {
            "allowed": True,
            "reason": None,
        }

    previous_unit = units[current_index - 1]
    unlocked = await is_previous_unit_completed(db, user_id, previous_unit.id)

    return {
        "allowed": unlocked,
        "reason": None if unlocked else "Oldingi unitda Writing, Test va Listening mode kamida 80% bajarilishi kerak.",
    }