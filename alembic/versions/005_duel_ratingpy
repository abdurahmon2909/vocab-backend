"""duel rating, bot status, answer session

Revision ID: 005_duel_rating
Revises: 004_add_unit_is_active
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "005_duel_rating"
down_revision = "004_add_unit_is_active"
branch_labels = None
depends_on = None


def table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    if not table_exists(inspector, table_name):
        return False

    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def index_exists(inspector, table_name: str, index_name: str) -> bool:
    if not table_exists(inspector, table_name):
        return False

    indexes = inspector.get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not column_exists(inspector, "users", "is_bot_started"):
        op.add_column(
            "users",
            sa.Column(
                "is_bot_started",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    if not column_exists(inspector, "users", "bot_started_at"):
        op.add_column(
            "users",
            sa.Column("bot_started_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not column_exists(inspector, "users", "bot_blocked_at"):
        op.add_column(
            "users",
            sa.Column("bot_blocked_at", sa.DateTime(timezone=True), nullable=True),
        )

    inspector = inspect(bind)

    if not table_exists(inspector, "user_duel_ratings"):
        op.create_table(
            "user_duel_ratings",
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("elo", sa.Integer(), nullable=False, server_default="800"),
            sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("draws", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("games_played", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.tg_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id"),
        )

    inspector = inspect(bind)

    if not index_exists(inspector, "user_duel_ratings", "ix_user_duel_ratings_elo"):
        op.create_index(
            "ix_user_duel_ratings_elo",
            "user_duel_ratings",
            ["elo"],
            unique=False,
        )

    if not column_exists(inspector, "answers", "answer_session_id"):
        op.add_column(
            "answers",
            sa.Column(
                "answer_session_id",
                sa.String(length=120),
                nullable=False,
                server_default="legacy",
            ),
        )

    inspector = inspect(bind)

    if not index_exists(inspector, "answers", "ix_answers_xp_farm_guard"):
        op.create_index(
            "ix_answers_xp_farm_guard",
            "answers",
            ["user_id", "word_id", "mode", "answer_session_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if index_exists(inspector, "answers", "ix_answers_xp_farm_guard"):
        op.drop_index("ix_answers_xp_farm_guard", table_name="answers")

    inspector = inspect(bind)

    if column_exists(inspector, "answers", "answer_session_id"):
        op.drop_column("answers", "answer_session_id")

    inspector = inspect(bind)

    if index_exists(inspector, "user_duel_ratings", "ix_user_duel_ratings_elo"):
        op.drop_index("ix_user_duel_ratings_elo", table_name="user_duel_ratings")

    inspector = inspect(bind)

    if table_exists(inspector, "user_duel_ratings"):
        op.drop_table("user_duel_ratings")

    inspector = inspect(bind)

    if column_exists(inspector, "users", "bot_blocked_at"):
        op.drop_column("users", "bot_blocked_at")

    inspector = inspect(bind)

    if column_exists(inspector, "users", "bot_started_at"):
        op.drop_column("users", "bot_started_at")

    inspector = inspect(bind)

    if column_exists(inspector, "users", "is_bot_started"):
        op.drop_column("users", "is_bot_started")