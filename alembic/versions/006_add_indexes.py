"""add indexes

Revision ID: 006_add_indexes
Revises: 005_duel_rating
Create Date: 2026-04-28
"""

from alembic import op


revision = "006_add_indexes"
down_revision = "005_duel_rating"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_answers_user_mode",
        "answers",
        ["user_id", "mode"],
        unique=False,
    )

    op.create_index(
        "ix_user_word_progress_user_mastery",
        "user_word_progress",
        ["user_id", "mastery_score"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_word_progress_user_mastery", table_name="user_word_progress")
    op.drop_index("ix_answers_user_mode", table_name="answers")