"""duel rating, bot status, answer session

Revision ID: 005_duel_rating_bot_status_answer_session
Revises: 004_add_unit_is_active
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "005_duel_rating_bot_status_answer_session"
down_revision = "004_add_unit_is_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_bot_started",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("bot_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("bot_blocked_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "user_duel_ratings",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("elo", sa.Integer(), nullable=False, server_default="800"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("games_played", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.tg_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_user_duel_ratings_elo", "user_duel_ratings", ["elo"])

    op.add_column(
        "answers",
        sa.Column(
            "answer_session_id",
            sa.String(length=120),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.create_index(
        "ix_answers_xp_farm_guard",
        "answers",
        ["user_id", "word_id", "mode", "answer_session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_answers_xp_farm_guard", table_name="answers")
    op.drop_column("answers", "answer_session_id")

    op.drop_index("ix_user_duel_ratings_elo", table_name="user_duel_ratings")
    op.drop_table("user_duel_ratings")

    op.drop_column("users", "bot_blocked_at")
    op.drop_column("users", "bot_started_at")
    op.drop_column("users", "is_bot_started")