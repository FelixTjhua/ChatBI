"""add intent field to chat_record

Revision ID: o3p4q5r6s7t8
Revises: n2o3p4q5r6s7
Create Date: 2026-02-20

"""
from alembic import op
import sqlalchemy as sa

revision = 'o3p4q5r6s7t8'
down_revision = 'n2o3p4q5r6s7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('chat_record', sa.Column('intent', sa.String(32), nullable=True))


def downgrade():
    op.drop_column('chat_record', 'intent')
