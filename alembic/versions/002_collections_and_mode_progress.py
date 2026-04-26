from alembic import op
import sqlalchemy as sa


revision = "002_collections_mode"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_collections_slug", "collections", ["slug"], unique=True)

    op.add_column("books", sa.Column("collection_id", sa.Integer(), nullable=True))
    op.create_index("ix_books_collection_id", "books", ["collection_id"], unique=False)

    op.create_foreign_key(
        "fk_books_collection_id_collections",
        "books",
        "collections",
        ["collection_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "mode_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_answers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.tg_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "unit_id", "mode", name="uq_user_unit_mode_progress"),
    )

    op.create_index("ix_mode_progress_user_id", "mode_progress", ["user_id"], unique=False)
    op.create_index("ix_mode_progress_unit_id", "mode_progress", ["unit_id"], unique=False)
    op.create_index("ix_mode_progress_mode", "mode_progress", ["mode"], unique=False)
    op.create_index("ix_mode_progress_user_unit", "mode_progress", ["user_id", "unit_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mode_progress_user_unit", table_name="mode_progress")
    op.drop_index("ix_mode_progress_mode", table_name="mode_progress")
    op.drop_index("ix_mode_progress_unit_id", table_name="mode_progress")
    op.drop_index("ix_mode_progress_user_id", table_name="mode_progress")
    op.drop_table("mode_progress")

    op.drop_constraint("fk_books_collection_id_collections", "books", type_="foreignkey")
    op.drop_index("ix_books_collection_id", table_name="books")
    op.drop_column("books", "collection_id")

    op.drop_index("ix_collections_slug", table_name="collections")
    op.drop_table("collections")