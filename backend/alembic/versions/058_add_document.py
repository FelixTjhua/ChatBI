"""add document tables (DEPRECATED - document management moved to datasource)

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-02-03

Note: This migration is deprecated. Document management (PDF等) is now handled
through the datasource module, where documents are uploaded as data sources.
The tables are kept for backward compatibility but are no longer used.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g7h8i9j0k1l2'
down_revision = 'f6g7h8i9j0k1'
branch_labels = None
depends_on = None


def upgrade():
    # DEPRECATED: Document management is now handled through datasource module
    # Tables are no longer created as they are not needed
    # PDF documents are uploaded as data sources instead
    pass


def downgrade():
    # Nothing to downgrade
    pass
