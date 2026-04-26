"""add unit is_active

Revision ID: 004_add_unit_is_active
Revises: 003_nickname_lb
Create Date: 2026-04-26
"""

from alembic import op
import sqlalchemy as sa


revision = '004_add_unit_is_active'
down_revision = '003_nickname_lb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # units jadvaliga is_active ustunini qo'shamiz
    op.add_column('units', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))


def downgrade() -> None:
    op.drop_column('units', 'is_active')