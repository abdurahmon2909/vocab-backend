"""add indexes

Revision ID: 006_add_indexes
Revises: 005_duel_rating
Create Date: 2026-04-28
"""

from alembic import op
from sqlalchemy import inspect


revision = "006_add_indexes"
down_revision = "005_duel_rating"
branch_labels = None
depends_on = None


def index_exists(inspector, table_name: str, index_name: str) -> bool:
    indexes = inspector.get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not index_exists(inspector, "answers", "ix_answers_user_mode"):
        op.create_index(
            "ix_answers_user_mode",
            "answers",
            ["user_id", "mode"],
            unique=False,
        )

    inspector = inspect(bind)

    if not index_exists(
        inspector,
        "user_word_progress",
        "ix_user_word_progress_user_mastery",
    ):
        op.create_index(
            "ix_user_word_progress_user_mastery",
            "user_word_progress",
            ["user_id", "mastery_score"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if index_exists(
        inspector,
        "user_word_progress",
        "ix_user_word_progress_user_mastery",
    ):
        op.drop_index(
            "ix_user_word_progress_user_mastery",
            table_name="user_word_progress",
        )

    inspector = inspect(bind)

    if index_exists(inspector, "answers", "ix_answers_user_mode"):
        op.drop_index("ix_answers_user_mode", table_name="answers")