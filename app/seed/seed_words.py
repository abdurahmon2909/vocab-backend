import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.models import Book, Unit, Word, Mission


DATA_PATH = Path(__file__).parent / "words.json"


async def seed_missions(db):
    default_missions = [
        {
            "code": "complete_10_questions",
            "title": "10 ta savolni yakunlash",
            "mission_type": "questions",
            "target": 10,
            "xp_reward": 30,
        },
        {
            "code": "review_5_weak_words",
            "title": "5 ta qiyin so‘zni takrorlash",
            "mission_type": "weak_words",
            "target": 5,
            "xp_reward": 40,
        },
        {
            "code": "finish_1_unit",
            "title": "1 ta unit tugatish",
            "mission_type": "unit_finish",
            "target": 1,
            "xp_reward": 60,
        },
    ]

    for item in default_missions:
        exists = await db.execute(select(Mission).where(Mission.code == item["code"]))
        if exists.scalar_one_or_none():
            continue

        db.add(Mission(**item))


async def seed_words():
    async with SessionLocal() as db:
        await seed_missions(db)

        with open(DATA_PATH, "r", encoding="utf-8") as f:
            books_data = json.load(f)

        for book_index, book_data in enumerate(books_data, start=1):
            slug = book_data["slug"]

            result = await db.execute(select(Book).where(Book.slug == slug))
            book = result.scalar_one_or_none()

            if not book:
                book = Book(
                    slug=slug,
                    title=book_data["title"],
                    description=book_data.get("description"),
                    cover_url=book_data.get("cover_url"),
                    order_index=book_index,
                )
                db.add(book)
                await db.flush()

            for unit_index, unit_data in enumerate(book_data["units"], start=1):
                result = await db.execute(
                    select(Unit).where(
                        Unit.book_id == book.id,
                        Unit.unit_number == unit_data["unit_number"],
                    )
                )
                unit = result.scalar_one_or_none()

                if not unit:
                    unit = Unit(
                        book_id=book.id,
                        unit_number=unit_data["unit_number"],
                        title=unit_data.get("title", f"Unit {unit_data['unit_number']}"),
                        description=unit_data.get("description"),
                        order_index=unit_index,
                    )
                    db.add(unit)
                    await db.flush()

                for word_index, word_data in enumerate(unit_data["words"], start=1):
                    result = await db.execute(
                        select(Word).where(
                            Word.unit_id == unit.id,
                            Word.english == word_data["english"],
                        )
                    )
                    word = result.scalar_one_or_none()

                    if word:
                        word.uzbek = word_data["uzbek"]
                        word.definition = word_data.get("definition")
                        word.example = word_data.get("example")
                        word.order_index = word_index
                    else:
                        db.add(
                            Word(
                                unit_id=unit.id,
                                english=word_data["english"],
                                uzbek=word_data["uzbek"],
                                definition=word_data.get("definition"),
                                example=word_data.get("example"),
                                order_index=word_index,
                            )
                        )

        await db.commit()

    print("✅ Seed completed successfully")


if __name__ == "__main__":
    asyncio.run(seed_words())