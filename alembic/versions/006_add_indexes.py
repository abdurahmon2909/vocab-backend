from alembic import op


def upgrade():
    op.create_index(
        "ix_answers_user_mode",
        "answers",
        ["user_id", "mode"],
    )

    op.create_index(
        "ix_user_word_progress_user_mastery",
        "user_word_progress",
        ["user_id", "mastery_score"],
    )


def downgrade():
    op.drop_index("ix_answers_user_mode", table_name="answers")
    op.drop_index("ix_user_word_progress_user_mastery", table_name="user_word_progress")