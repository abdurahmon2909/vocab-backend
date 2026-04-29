"""add Way to Legend duel win streak storage

Revision ID: 013_way_to_legend_more_achievements
Revises: 012_way_to_legend_achievements
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa


revision = "013_way_to_legend_more_achievements"
down_revision = "012_way_to_legend_achievements"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_duel_win_streak_achievements",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.tg_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.execute("""
        INSERT INTO user_duel_win_streak_achievements (user_id, current_streak, best_streak)
        SELECT user_id, 0, 0
        FROM user_duel_ratings
        ON CONFLICT (user_id) DO NOTHING;
    """)


def downgrade():
    op.drop_table("user_duel_win_streak_achievements")
