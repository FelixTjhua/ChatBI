"""074: 为 chat_record 添加 input_type 字段

记录用户提问方式：
- manual: 自然语言手动输入
- recommend: 系统推荐问题点击

支持双模式提问的数据追踪。

Revision ID: 074_input_type
Revises: 073_business_prefix
"""
from alembic import op
import sqlalchemy as sa

revision = '074_input_type'
down_revision = '073_business_prefix'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('chat_record', sa.Column('input_type', sa.String(16), nullable=True, server_default='manual'))


def downgrade() -> None:
    op.drop_column('chat_record', 'input_type')
