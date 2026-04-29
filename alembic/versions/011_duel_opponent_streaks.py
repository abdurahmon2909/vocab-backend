"""add duel opponent streaks

Revision ID: 011_duel_opponent_streaks
Revises: 010_answer_unique_constraint
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa


revision = "011_duel_opponent_streaks"
down_revision = "010_answer_unique_constraint"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "duel_opponent_streaks",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("opponent_id", sa.BigInteger(), nullable=False),
        sa.Column("streak_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["opponent_id"], ["users.tg_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.tg_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(
        "ix_duel_opponent_streaks_opponent_id",
        "duel_opponent_streaks",
        ["opponent_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_duel_opponent_streaks_opponent_id",
        table_name="duel_opponent_streaks",
    )
    op.drop_table("duel_opponent_streaks")
