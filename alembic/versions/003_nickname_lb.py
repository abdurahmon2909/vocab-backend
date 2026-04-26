from alembic import op
import sqlalchemy as sa


revision = "003_nickname_lb"
down_revision = "002_collections_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("nickname", sa.String(length=64), nullable=True),
    )

    op.create_index(
        "ix_users_nickname",
        "users",
        ["nickname"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_users_nickname", table_name="users")
    op.drop_column("users", "nickname")