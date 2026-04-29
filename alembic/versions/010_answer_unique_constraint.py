"""add unique constraint to answer table

Revision ID: 010_answer_unique_constraint
Revises: 009_elo_exchange
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "010_answer_unique_constraint"
down_revision = "009_elo_exchange"
branch_labels = None
depends_on = None


def upgrade():
    # 🔥 old duplicate datalarni tozalaymiz
    op.execute("""
        DELETE FROM answers a
        USING answers b
        WHERE a.id < b.id
        AND a.user_id = b.user_id
        AND a.word_id = b.word_id
        AND a.mode = b.mode
        AND a.answer_session_id = b.answer_session_id;
    """)

    # 🔒 unique constraint qo‘shamiz
    op.create_unique_constraint(
        "uq_answer_once_per_session_word_mode",
        "answers",
        ["user_id", "word_id", "mode", "answer_session_id"],
    )


def downgrade():
    op.drop_constraint(
        "uq_answer_once_per_session_word_mode",
        "answers",
        type_="unique",
    )