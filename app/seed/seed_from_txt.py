import asyncio
from pathlib import Path

from sqlalchemy import select, delete

from app.db.session import SessionLocal
from app.models.models import Book, Unit, Word, Mission


FILE_PATH = Path(__file__).resolve().parent / "words.txt"


def extract_unit_number(unit_title: str) -> int:
    digits = "".join(ch for ch in str(unit_title) if ch.isdigit())
    return int(digits) if digits else 1


def parse_line(line: str):
    parts = line.rstrip("\n").split("\t")

    if len(parts) < 6:
        return None

    english = parts[0].strip()
    uzbek = parts[1].strip()

    book_marker_index = None
    for i, part in enumerate(parts):
        if part.strip().lower() == "book":
            book_marker_index = i
            break

    if book_marker_index is None:
        return None

    try:
        book_slug = parts[book_marker_index + 1].strip()
        book_title = parts[book_marker_index + 2].strip()
        unit_title = parts[book_marker_index + 3].strip()
    except IndexError:
        return None

    if not english or not uzbek or not book_slug or not book_title or not unit_title:
        return None

    return {
        "english": english,
        "uzbek": uzbek,
        "book_slug": book_slug,
        "book_title": book_title,
        "unit_title": unit_title,
        "unit_number": extract_unit_number(unit_title),
    }


async def seed_missions(db):
    missions = [
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

    for item in missions:
        result = await db.execute(
            select(Mission).where(Mission.code == item["code"])
        )
        exists = result.scalar_one_or_none()

        if not exists:
            db.add(Mission(**item))


async def seed():
    if not FILE_PATH.exists():
        raise FileNotFoundError(f"words.txt topilmadi: {FILE_PATH}")

    async with SessionLocal() as db:
        await seed_missions(db)

        with open(FILE_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

        books_cache = {}
        units_cache = {}

        created_books = 0
        created_units = 0
        created_words = 0
        updated_words = 0
        skipped = 0

        total = len(lines)

        for index, line in enumerate(lines, start=1):
            if index % 25 == 0:
                print(f"Processing line {index}/{total}...")

            data = parse_line(line)

            if not data:
                skipped += 1
                continue

            book = books_cache.get(data["book_slug"])

            if not book:
                result = await db.execute(
                    select(Book).where(Book.slug == data["book_slug"])
                )
                book = result.scalar_one_or_none()

                if not book:
                    book = Book(
                        slug=data["book_slug"],
                        title=data["book_title"],
                        description=f"{data['book_title']} vocabulary units",
                        cover_url="",
                        order_index=1,
                        is_active=True,
                    )
                    db.add(book)
                    await db.flush()
                    created_books += 1

                books_cache[data["book_slug"]] = book

            unit_key = f"{book.id}:{data['unit_number']}"

            unit = units_cache.get(unit_key)

            if not unit:
                result = await db.execute(
                    select(Unit).where(
                        Unit.book_id == book.id,
                        Unit.unit_number == data["unit_number"],
                    )
                )
                unit = result.scalar_one_or_none()

                if not unit:
                    unit = Unit(
                        book_id=book.id,
                        unit_number=data["unit_number"],
                        title=data["unit_title"],
                        description=f"{data['book_title']} - {data['unit_title']}",
                        order_index=data["unit_number"],
                    )
                    db.add(unit)
                    await db.flush()
                    created_units += 1

                units_cache[unit_key] = unit

            result = await db.execute(
                select(Word).where(
                    Word.unit_id == unit.id,
                    Word.english == data["english"],
                )
            )
            word = result.scalar_one_or_none()

            if word:
                word.uzbek = data["uzbek"]
                word.order_index = index
                updated_words += 1
            else:
                db.add(
                    Word(
                        unit_id=unit.id,
                        english=data["english"],
                        uzbek=data["uzbek"],
                        definition=None,
                        example=None,
                        order_index=index,
                    )
                )
                created_words += 1

            if index % 100 == 0:
                await db.commit()
                print(f"Saved {index}/{total} lines...")

        await db.commit()

    print("✅ SEED DONE")
    print(f"📚 Books created: {created_books}")
    print(f"📦 Units created: {created_units}")
    print(f"🧠 Words created: {created_words}")
    print(f"♻️ Words updated: {updated_words}")
    print(f"⏭️ Skipped lines: {skipped}")


if __name__ == "__main__":
    asyncio.run(seed())