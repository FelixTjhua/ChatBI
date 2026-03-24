"""
添加性能优化索引

为高频查询列添加数据库索引，提升查询性能

Revision ID: n2o3p4q5r6s7
Revises: m1n2o3p4q5r6
Create Date: 2026-02-18
"""
import sqlalchemy as sa

revision = 'n2o3p4q5r6s7'
down_revision = 'm1n2o3p4q5r6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # chat_record 表：chat_id 是最常用的查询条件
    op_create_index_if_not_exists('ix_chat_record_chat_id', 'chat_record', ['chat_id'])
    # chat_record 表：create_by（用户ID）用于权限过滤
    op_create_index_if_not_exists('ix_chat_record_create_by', 'chat_record', ['create_by'])
    # chat_record 表：datasource 用于按数据源查询
    op_create_index_if_not_exists('ix_chat_record_datasource', 'chat_record', ['datasource'])
    # chat 表：create_by + oid 组合查询
    op_create_index_if_not_exists('ix_chat_create_by_oid', 'chat', ['create_by', 'oid'])
    # chat_log 表：pid + type + operate 组合查询
    op_create_index_if_not_exists('ix_chat_log_pid_type_op', 'chat_log', ['pid', 'type', 'operate'])
    # core_datasource 表：oid 用于按组织查询
    op_create_index_if_not_exists('ix_core_datasource_oid', 'core_datasource', ['oid'])
    # audit_log 表：oid + create_time 用于审计查询
    op_create_index_if_not_exists('ix_audit_log_oid_time', 'audit_log', ['oid', 'create_time'])


def downgrade() -> None:
    op_drop_index_if_exists('ix_audit_log_oid_time', 'audit_log')
    op_drop_index_if_exists('ix_core_datasource_oid', 'core_datasource')
    op_drop_index_if_exists('ix_chat_log_pid_type_op', 'chat_log')
    op_drop_index_if_exists('ix_chat_create_by_oid', 'chat')
    op_drop_index_if_exists('ix_chat_record_datasource', 'chat_record')
    op_drop_index_if_exists('ix_chat_record_create_by', 'chat_record')
    op_drop_index_if_exists('ix_chat_record_chat_id', 'chat_record')


def op_create_index_if_not_exists(index_name: str, table_name: str, columns: list):
    """安全创建索引（如果不存在）"""
    from alembic import op
    conn = op.get_bind()
    # 检查索引是否已存在
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_indexes WHERE indexname = :name"
    ), {"name": index_name})
    if result.fetchone() is None:
        op.create_index(index_name, table_name, columns)


def op_drop_index_if_exists(index_name: str, table_name: str):
    """安全删除索引（如果存在）"""
    from alembic import op
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_indexes WHERE indexname = :name"
    ), {"name": index_name})
    if result.fetchone() is not None:
        op.drop_index(index_name, table_name=table_name)
