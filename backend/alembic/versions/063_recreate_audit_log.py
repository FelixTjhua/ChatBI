"""recreate audit_log table

审计日志表重建 - 支持完整的操作审计功能

Revision ID: m1n2o3p4q5r6
Revises: k1l2m3n4o5p6
Create Date: 2026-02-18
"""
from alembic import op
import sqlalchemy as sa

revision = 'm1n2o3p4q5r6'
down_revision = 'k1l2m3n4o5p6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('audit_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('user_name', sa.String(255), nullable=True),
        sa.Column('action', sa.String(128), nullable=False, comment='操作类型: LOGIN, QUERY, CREATE_DS, DELETE_DS, RAG_RETRIEVAL 等'),
        sa.Column('resource_type', sa.String(128), nullable=True, comment='资源类型: datasource, chat, terminology, training 等'),
        sa.Column('resource_id', sa.BigInteger(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True, comment='操作详情（JSON格式）'),
        sa.Column('ip_address', sa.String(64), nullable=True),
        sa.Column('user_agent', sa.String(512), nullable=True),
        sa.Column('oid', sa.BigInteger(), nullable=False, server_default='1'),
        sa.Column('create_time', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    # 添加索引以支持高效查询
    op.create_index('ix_audit_log_user_id', 'audit_log', ['user_id'])
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])
    op.create_index('ix_audit_log_create_time', 'audit_log', ['create_time'])
    op.create_index('ix_audit_log_oid', 'audit_log', ['oid'])


def downgrade() -> None:
    op.drop_index('ix_audit_log_oid', table_name='audit_log')
    op.drop_index('ix_audit_log_create_time', table_name='audit_log')
    op.drop_index('ix_audit_log_action', table_name='audit_log')
    op.drop_index('ix_audit_log_user_id', table_name='audit_log')
    op.drop_table('audit_log')
