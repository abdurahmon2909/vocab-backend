"""add nickname changed at

Revision ID: 007_nickname_once
Revises: 006_add_indexes
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "007_nickname_once"
down_revision = "006_add_indexes"
branch_labels = None
depends_on = None


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not column_exists(inspector, "users", "nickname_changed_at"):
        op.add_column(
            "users",
            sa.Column("nickname_changed_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if column_exists(inspector, "users", "nickname_changed_at"):
        op.drop_column("users", "nickname_changed_at")
