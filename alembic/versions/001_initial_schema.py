"""initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-04-26
"""

from alembic import op
import sqlalchemy as sa


revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("language_code", sa.String(length=20), nullable=True),
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_tg_id", "users", ["tg_id"], unique=True)

    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_books_slug", "books", ["slug"], unique=True)

    op.create_table(
        "missions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("mission_type", sa.String(length=80), nullable=False),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("xp_reward", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_missions_code", "missions", ["code"], unique=True)

    op.create_table(
        "units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("book_id", "unit_number", name="uq_book_unit_number"),
    )
    op.create_index("ix_units_book_id", "units", ["book_id"])

    op.create_table(
        "words",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("english", sa.String(length=255), nullable=False),
        sa.Column("uzbek", sa.String(length=255), nullable=False),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("example", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("unit_id", "english", name="uq_unit_english_word"),
    )
    op.create_index("ix_words_unit_id", "words", ["unit_id"])
    op.create_index("ix_words_english", "words", ["english"])
    op.create_index("ix_words_uzbek", "words", ["uzbek"])

    op.create_table(
        "user_xp",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.tg_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("total_xp", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "streaks",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.tg_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_active_date", sa.Date(), nullable=True),
    )

    op.create_table(
        "user_word_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.tg_id", ondelete="CASCADE"), nullable=False),
        sa.Column("word_id", sa.Integer(), sa.ForeignKey("words.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seen_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wrong_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_result", sa.String(length=20), nullable=True),
        sa.Column("mastery_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "word_id", name="uq_user_word_progress"),
    )
    op.create_index("ix_user_word_progress_user_id", "user_word_progress", ["user_id"])
    op.create_index("ix_user_word_progress_word_id", "user_word_progress", ["word_id"])
    op.create_index("ix_progress_user_wrong", "user_word_progress", ["user_id", "wrong_count"])

    op.create_table(
        "xp_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.tg_id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_xp_events_user_id", "xp_events", ["user_id"])

    op.create_table(
        "user_mission_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.tg_id", ondelete="CASCADE"), nullable=False),
        sa.Column("mission_id", sa.Integer(), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("date_key", sa.Date(), nullable=False),
        sa.UniqueConstraint("user_id", "mission_id", "date_key", name="uq_user_mission_day"),
    )
    op.create_index("ix_user_mission_progress_user_id", "user_mission_progress", ["user_id"])
    op.create_index("ix_user_mission_progress_mission_id", "user_mission_progress", ["mission_id"])

    op.create_table(
        "answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.tg_id", ondelete="CASCADE"), nullable=False),
        sa.Column("word_id", sa.Integer(), sa.ForeignKey("words.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=True),
        sa.Column("correct_answer", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_answers_user_id", "answers", ["user_id"])
    op.create_index("ix_answers_word_id", "answers", ["word_id"])
    op.create_index("ix_answers_unit_id", "answers", ["unit_id"])


def downgrade():
    op.drop_table("answers")
    op.drop_table("user_mission_progress")
    op.drop_table("xp_events")
    op.drop_table("user_word_progress")
    op.drop_table("streaks")
    op.drop_table("user_xp")
    op.drop_table("words")
    op.drop_table("units")
    op.drop_table("missions")
    op.drop_table("books")
    op.drop_table("users")