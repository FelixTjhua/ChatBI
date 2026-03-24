"""add performance indexes to chat_record

Revision ID: p4q5r6s7t8u9
Revises: o3p4q5r6s7t8
Create Date: 2026-02-23

Fix: ChatRecord表缺少索引，高频查询字段(chat_id, datasource, create_time, create_by)
随着数据量增长查询性能会显著下降。添加单列索引和复合索引。
"""
from alembic import op

revision = 'p4q5r6s7t8u9'
down_revision = 'o3p4q5r6s7t8'
branch_labels = None
depends_on = None


def upgrade():
    # 单列索引
    op.create_index('ix_chat_record_chat_id', 'chat_record', ['chat_id'], if_not_exists=True)
    op.create_index('ix_chat_record_datasource', 'chat_record', ['datasource'], if_not_exists=True)
    op.create_index('ix_chat_record_create_time', 'chat_record', ['create_time'], if_not_exists=True)
    op.create_index('ix_chat_record_create_by', 'chat_record', ['create_by'], if_not_exists=True)
    # 复合索引（按会话查询最近记录的高频场景）
    op.create_index('ix_chat_record_chat_id_create_time', 'chat_record', ['chat_id', 'create_time'], if_not_exists=True)


def downgrade():
    op.drop_index('ix_chat_record_chat_id_create_time', 'chat_record')
    op.drop_index('ix_chat_record_create_by', 'chat_record')
    op.drop_index('ix_chat_record_create_time', 'chat_record')
    op.drop_index('ix_chat_record_datasource', 'chat_record')
    op.drop_index('ix_chat_record_chat_id', 'chat_record')
