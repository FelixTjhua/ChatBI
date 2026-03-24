"""add thinking process field

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TEXT

# revision identifiers, used by Alembic.
revision = 'f6g7h8i9j0k1'
down_revision = 'e5f6g7h8i9j0'
branch_labels = None
depends_on = None


def upgrade():
    # 添加 thinking_process 字段到 chat_record 表
    op.add_column('chat_record', sa.Column('thinking_process', TEXT, nullable=True))


def downgrade():
    # 删除 thinking_process 字段
    op.drop_column('chat_record', 'thinking_process')
