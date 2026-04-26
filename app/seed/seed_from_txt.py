import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import async_session_maker
from app.models import Book, Unit, Word


FILE_PATH = "words.txt"  # txt fayl nomi


def parse_line(line: str):
    parts = line.strip().split("\t")

    if len(parts) < 6:
        return None

    english = parts[0].strip()
    uzbek = parts[1].strip()
    book_id = parts[-3].strip()
    book_name = parts[-2].strip()
    unit_name = parts[-1].strip()

    return {
        "english": english,
        "uzbek": uzbek,
        "book_id": book_id,
        "book_name": book_name,
        "unit_name": unit_name,
    }


async def seed():
    async with async_session_maker() as session:  # type: AsyncSession

        books_cache = {}
        units_cache = {}

        with open(FILE_PATH, encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            data = parse_line(line)
            if not data:
                continue

            # ===== BOOK =====
            if data["book_id"] not in books_cache:
                book = Book(
                    slug=data["book_id"],
                    title=data["book_name"]
                )
                session.add(book)
                await session.flush()
                books_cache[data["book_id"]] = book
            else:
                book = books_cache[data["book_id"]]

            # ===== UNIT =====
            unit_key = f"{data['book_id']}_{data['unit_name']}"

            if unit_key not in units_cache:
                unit = Unit(
                    title=data["unit_name"],
                    book_id=book.id
                )
                session.add(unit)
                await session.flush()
                units_cache[unit_key] = unit
            else:
                unit = units_cache[unit_key]

            # ===== WORD =====
            word = Word(
                word=data["english"],
                translation=data["uzbek"],
                unit_id=unit.id
            )

            session.add(word)

        await session.commit()
        print("✅ SEED DONE")


if __name__ == "__main__":
    asyncio.run(seed())