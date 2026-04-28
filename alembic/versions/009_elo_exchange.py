"""add elo exchanges

Revision ID: 009_elo_exchange
Revises: 008_word_difficulty
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "009_elo_exchange"
down_revision = "008_word_difficulty"
branch_labels = None
depends_on = None


def table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def index_exists(inspector, table_name: str, index_name: str) -> bool:
    indexes = inspector.get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not table_exists(inspector, "elo_exchanges"):
        op.create_table(
            "elo_exchanges",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("xp_amount", sa.Integer(), nullable=False),
            sa.Column("elo_amount", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.tg_id"], ondelete="CASCADE"),
        )

    inspector = inspect(bind)

    if not index_exists(inspector, "elo_exchanges", "ix_elo_exchanges_user_created"):
        op.create_index(
            "ix_elo_exchanges_user_created",
            "elo_exchanges",
            ["user_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if table_exists(inspector, "elo_exchanges"):
        if index_exists(inspector, "elo_exchanges", "ix_elo_exchanges_user_created"):
            op.drop_index("ix_elo_exchanges_user_created", table_name="elo_exchanges")

        op.drop_table("elo_exchanges")
