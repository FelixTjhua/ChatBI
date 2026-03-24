"""drop chat_feedback table (module removed)

Revision ID: r6s7t8u9v0w1
Revises: p4q5r6s7t8u9
Create Date: 2026-02-25

移除不需要的 feedback 模块，删除 chat_feedback 表。
"""
from alembic import op
import sqlalchemy as sa

revision = 'r6s7t8u9v0w1'
down_revision = 'p4q5r6s7t8u9'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'chat_feedback')"
        )
    )
    if result.scalar():
        op.drop_table('chat_feedback')


def downgrade():
    # 不再恢复 — 该模块已被移除
    pass
