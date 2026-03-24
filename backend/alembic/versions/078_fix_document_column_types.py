"""fix core_document.id type (Integer → BigInteger) and
core_document_chunk.embedding dimension (vector(768) → vector without dimension)

Revision ID: 078_fix_doc_col_types
Revises: 077_add_raw_text
Create Date: 2025-03-14 00:00:00.000000

修复说明：
1. core_document.id 在 migration 071 中创建为 Integer，但 ORM 模型定义为 BigInteger。
   当文档数量增长超过 2^31 时会溢出。改为 BIGINT + IDENTITY 与模型一致。
2. core_document_chunk.embedding 在 migration 071 中硬编码为 vector(768)，
   但 ORM 模型使用 VECTOR() 无维度约束。切换 embedding 模型（如 768→1024 维）
   时会因维度不匹配导致插入失败。移除维度约束使其兼容任意维度模型。
"""
from alembic import op


revision = '078_fix_doc_col_types'
down_revision = '077_add_raw_text'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 修复 core_document.id: Integer → BigInteger (IDENTITY)
    # PostgreSQL 不支持直接 ALTER COLUMN 改 IDENTITY，需要先改类型
    op.execute("""
        ALTER TABLE core_document
        ALTER COLUMN id TYPE BIGINT
    """)

    # 2. 修复 core_document_chunk.embedding: vector(768) → vector (无维度约束)
    # 先删除依赖该列的 HNSW 索引，修改类型后不再重建
    # 原因：pgvector 的 HNSW/IVFFlat 索引要求列有固定维度，
    # 而无维度约束的 vector 列无法创建这类索引。
    # 与 terminology、data_training 表保持一致（均无 HNSW 索引）。
    # 文档检索仍可正常工作（顺序扫描），数据量大时可在应用层按实际维度动态创建索引。
    op.execute("DROP INDEX IF EXISTS idx_doc_chunk_embedding")
    op.execute("""
        ALTER TABLE core_document_chunk
        ALTER COLUMN embedding TYPE vector
    """)


def downgrade() -> None:
    # 回退 embedding 为 vector(768)
    op.execute("DROP INDEX IF EXISTS idx_doc_chunk_embedding")
    op.execute("""
        ALTER TABLE core_document_chunk
        ALTER COLUMN embedding TYPE vector(768)
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_chunk_embedding ON core_document_chunk "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )
    # 回退 core_document.id 为 INTEGER
    op.execute("""
        ALTER TABLE core_document
        ALTER COLUMN id TYPE INTEGER
    """)
