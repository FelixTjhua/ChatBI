"""083: 为 chat_record 补充 chart_image 列（如果不存在）

修复缺陷：ChatRecord 模型缺少 chart_image 字段定义，
但数据库中可能已通过其他方式创建了该列。
使用 IF NOT EXISTS 防御性添加。

Revision ID: 083_add_chart_image
Revises: 082_thinking_gin
Create Date: 2025-03-18 00:00:00.000000
"""
from alembic import op


revision = '083_add_chart_image'
down_revision = '082_thinking_gin'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE chat_record ADD COLUMN IF NOT EXISTS chart_image TEXT
    """)


def downgrade() -> None:
    op.drop_column('chat_record', 'chart_image')
