from alembic import op
import sqlalchemy as sa

revision = "008_word_difficulty"
down_revision = "007_nickname_once"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("words", sa.Column("total_answers", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("words", sa.Column("correct_answers", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("words", sa.Column("difficulty_score", sa.Float(), nullable=False, server_default="0.5"))

    op.create_index("ix_words_difficulty_score", "words", ["difficulty_score"])


def downgrade():
    op.drop_index("ix_words_difficulty_score", table_name="words")
    op.drop_column("words", "difficulty_score")
    op.drop_column("words", "correct_answers")
    op.drop_column("words", "total_answers")