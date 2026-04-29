"""add way to legend achievements and referrals

Revision ID: 012_way_to_legend_achievements
Revises: 011_duel_opponent_streaks
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa


revision = "012_way_to_legend_achievements"
down_revision = "011_duel_opponent_streaks"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referrer_id", sa.BigInteger(), nullable=False),
        sa.Column("referred_user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["referrer_id"], ["users.tg_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["referred_user_id"], ["users.tg_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("referrer_id", "referred_user_id", name="uq_referral_pair"),
        sa.UniqueConstraint("referred_user_id", name="uq_referrals_referred_user_id"),
    )
    op.create_index("ix_referrals_referrer_id", "referrals", ["referrer_id"])
    op.create_index("ix_referrals_referred_user_id", "referrals", ["referred_user_id"])

    op.create_table(
        "user_achievement_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("achievement_code", sa.String(length=120), nullable=False),
        sa.Column("group_code", sa.String(length=80), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("reward_elo", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_claimed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.tg_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "achievement_code", name="uq_user_achievement_code"),
    )
    op.create_index("ix_user_achievement_progress_user_id", "user_achievement_progress", ["user_id"])
    op.create_index("ix_user_achievement_progress_group_code", "user_achievement_progress", ["group_code"])
    op.create_index("ix_user_achievement_group", "user_achievement_progress", ["user_id", "group_code"])

    op.create_table(
        "user_completed_unit_achievements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.tg_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "unit_id", name="uq_user_completed_unit_achievement"),
    )
    op.create_index("ix_user_completed_unit_achievements_user_id", "user_completed_unit_achievements", ["user_id"])
    op.create_index("ix_user_completed_unit_achievements_unit_id", "user_completed_unit_achievements", ["unit_id"])


def downgrade():
    op.drop_index("ix_user_completed_unit_achievements_unit_id", table_name="user_completed_unit_achievements")
    op.drop_index("ix_user_completed_unit_achievements_user_id", table_name="user_completed_unit_achievements")
    op.drop_table("user_completed_unit_achievements")

    op.drop_index("ix_user_achievement_group", table_name="user_achievement_progress")
    op.drop_index("ix_user_achievement_progress_group_code", table_name="user_achievement_progress")
    op.drop_index("ix_user_achievement_progress_user_id", table_name="user_achievement_progress")
    op.drop_table("user_achievement_progress")

    op.drop_index("ix_referrals_referred_user_id", table_name="referrals")
    op.drop_index("ix_referrals_referrer_id", table_name="referrals")
    op.drop_table("referrals")
