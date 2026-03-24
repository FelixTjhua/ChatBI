"""add dashboard summary cache field

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-02-07
"""
from alembic import op
import sqlalchemy as sa

revision = 'j0k1l2m3n4o5'
down_revision = 'i9j0k1l2m3n4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('core_dashboard', sa.Column('ai_summary', sa.Text(), nullable=True))
    op.add_column('core_dashboard', sa.Column('summary_updated_at', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('core_dashboard', 'ai_summary')
    op.drop_column('core_dashboard', 'summary_updated_at')
