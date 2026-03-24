"""add document knowledge base tables for RAG document pipeline

Revision ID: 071_add_document_knowledge_base
Revises: 070_add_custom_prompt_always_inject
Create Date: 2025-01-01 00:00:00.000000

知识库文档管理（离线阶段）：
- core_document: 存储上传的文档元信息（文件名、格式、路径、上传时间）
- core_document_chunk: 存储文档分块及向量嵌入（文本块+向量+来源+页码）
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = '071_doc_knowledge'
down_revision = '070_always_inject'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 确保 pgvector 扩展存在
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 文档元信息表
    op.create_table(
        'core_document',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('file_type', sa.String(20), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(1000), nullable=True),
        sa.Column('total_chunks', sa.Integer(), default=0),
        sa.Column('vectorized_count', sa.Integer(), default=0),
        sa.Column('total_sections', sa.Integer(), default=0),
        sa.Column('total_tables', sa.Integer(), default=0),
        sa.Column('processing_time', sa.Float(), default=0),
        sa.Column('oid', sa.Integer(), default=1),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('create_time', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('update_time', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # 文档分块+向量表
    op.create_table(
        'core_document_chunk',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('core_document.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_index', sa.Integer(), default=0),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.Column('source_file', sa.String(500), nullable=True),
        sa.Column('section_title', sa.String(500), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('chunk_type', sa.String(50), nullable=True),
        sa.Column('create_time', sa.DateTime(), server_default=sa.func.now()),
    )

    # 为向量列创建 HNSW 索引（用于语义检索）
    # 注意：不使用 IVFFlat，因为 IVFFlat 在空表上创建索引会导致聚类中心为空，
    # 后续插入数据后检索质量极差。HNSW 索引无此限制，支持增量插入。
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_chunk_embedding ON core_document_chunk "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )
    op.create_index('idx_doc_chunk_document_id', 'core_document_chunk', ['document_id'])


def downgrade() -> None:
    op.drop_table('core_document_chunk')
    op.drop_table('core_document')
