import asyncio

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.models import Book, Collection


ESSENTIAL_COLLECTION_SLUG = "essential"
ESSENTIAL_COLLECTION_TITLE = "Essential English Words"


def is_essential_book(book: Book) -> bool:
    slug = (book.slug or "").lower()
    title = (book.title or "").lower()

    return "essential" in slug or "essential" in title


async def main():
    async with SessionLocal() as db:
        collection_result = await db.execute(
            select(Collection).where(Collection.slug == ESSENTIAL_COLLECTION_SLUG)
        )
        collection = collection_result.scalar_one_or_none()

        if not collection:
            collection = Collection(
                slug=ESSENTIAL_COLLECTION_SLUG,
                title=ESSENTIAL_COLLECTION_TITLE,
                description="Essential English Words 1-6 kitoblari",
                cover_url="",
                order_index=1,
                is_active=True,
            )
            db.add(collection)
            await db.flush()

        books_result = await db.execute(
            select(Book).order_by(Book.order_index, Book.id)
        )
        books = books_result.scalars().all()

        essential_books = [book for book in books if is_essential_book(book)]

        for index, book in enumerate(essential_books, start=1):
            book.collection_id = collection.id
            book.order_index = index
            book.is_active = True

        await db.commit()

        print("✅ Essential books grouped into collection")
        print(f"📚 Collection: {collection.title}")
        print(f"📦 Books updated: {len(essential_books)}")


if __name__ == "__main__":
    asyncio.run(main())