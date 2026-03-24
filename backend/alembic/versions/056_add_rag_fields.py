"""add rag fields to chat_record

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-01-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6g7h8i9j0'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade():
    # 添加 rag_enabled 字段（标识是否使用 RAG 模式）
    op.add_column('chat_record', 
        sa.Column('rag_enabled', sa.Boolean(), nullable=True, server_default='true'))
    
    # 添加 rag_results 字段（存储 RAG 检索结果的 JSON 数据）
    op.add_column('chat_record', 
        sa.Column('rag_results', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('chat_record', 'rag_results')
    op.drop_column('chat_record', 'rag_enabled')
