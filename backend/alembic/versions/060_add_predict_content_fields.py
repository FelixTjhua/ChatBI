"""add predict content fields

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i9j0k1l2m3n4'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加 predict_content 字段（预测报告内容）
    op.add_column('chat_record', sa.Column('predict_content', sa.Text(), nullable=True))
    
    # 添加 predict_reasoning_content 字段（预测推理内容）
    op.add_column('chat_record', sa.Column('predict_reasoning_content', sa.Text(), nullable=True))


def downgrade() -> None:
    # 删除字段
    op.drop_column('chat_record', 'predict_reasoning_content')
    op.drop_column('chat_record', 'predict_content')
