from datetime import datetime, date

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 🔥 Relationship'lar olib tashlandi - xatolikni oldini olish uchun

    # Relationships with lazy="joined" to avoid extra queries
    xp = relationship("UserXP", back_populates="user", uselist=False, lazy="joined")
    streak = relationship("Streak", back_populates="user", uselist=False, lazy="joined")


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    books = relationship("Book", back_populates="collection", lazy="selectin")


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int | None] = mapped_column(
        ForeignKey("collections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    collection = relationship("Collection", back_populates="books", lazy="selectin")
    units = relationship("Unit", back_populates="book", cascade="all, delete-orphan", lazy="selectin")


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    unit_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    book = relationship("Book", back_populates="units", lazy="selectin")
    words = relationship("Word", back_populates="unit", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("book_id", "unit_number", name="uq_book_unit_number"),
    )


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    english: Mapped[str] = mapped_column(String(255), index=True)
    uzbek: Mapped[str] = mapped_column(String(255), index=True)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    example: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    unit = relationship("Unit", back_populates="words", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("unit_id", "english", name="uq_unit_english_word"),
    )


class ModeProgress(Base):
    __tablename__ = "mode_progress"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.tg_id", ondelete="CASCADE"),
        index=True,
    )

    unit_id: Mapped[int] = mapped_column(
        ForeignKey("units.id", ondelete="CASCADE"),
        index=True,
    )

    mode: Mapped[str] = mapped_column(String(40), index=True)

    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "unit_id", "mode", name="uq_user_unit_mode_progress"),
        Index("ix_mode_progress_user_unit", "user_id", "unit_id"),
    )


class UserWordProgress(Base):
    __tablename__ = "user_word_progress"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.tg_id", ondelete="CASCADE"), index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True)

    seen_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    last_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mastery_score: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uq_user_word_progress"),
        Index("ix_progress_user_wrong", "user_id", "wrong_count"),
    )


class UserXP(Base):
    __tablename__ = "user_xp"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.tg_id", ondelete="CASCADE"), primary_key=True)
    total_xp: Mapped[int] = mapped_column(Integer, default=0)

    user = relationship("User", back_populates="xp", lazy="joined")


class XPEvent(Base):
    __tablename__ = "xp_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.tg_id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Streak(Base):
    __tablename__ = "streaks"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.tg_id", ondelete="CASCADE"), primary_key=True)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    user = relationship("User", back_populates="streak", lazy="joined")


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    mission_type: Mapped[str] = mapped_column(String(80))
    target: Mapped[int] = mapped_column(Integer)
    xp_reward: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserMissionProgress(Base):
    __tablename__ = "user_mission_progress"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.tg_id", ondelete="CASCADE"), index=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    date_key: Mapped[date] = mapped_column(Date)

    __table_args__ = (
        UniqueConstraint("user_id", "mission_id", "date_key", name="uq_user_mission_day"),
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.tg_id", ondelete="CASCADE"), index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(40))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    user_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    correct_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int]
    slug: Mapped[str]
    title: Mapped[str]
    description: Mapped[str | None]

    # 🔥 MUHIM
    cover_url: Mapped[str | None] = mapped_column(String, nullable=True)