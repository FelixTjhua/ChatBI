"""080: 恢复 embedding 列维度约束并重建 HNSW 向量索引

Migration 078 将 embedding 列从 vector(768) 改为无维度约束的 vector，
同时删除了 HNSW 索引。当前 pgvector 版本不支持在无维度约束的 vector 列上
创建 HNSW 索引（报错: column does not have dimensions）。

本项目统一使用 BAAI/bge-base-zh-v1.5（768维），不存在多维度混用场景，
因此将 embedding 列恢复为 vector(768) 并重建 HNSW 索引。

缺少索引时，search_document_chunks 的每次语义检索都退化为全表顺序扫描，
文档数量增长后性能急剧下降（O(n) vs O(log n)）。

Revision ID: 080_restore_hnsw_idx
Revises: 079_add_doc_oid_ds_idx
Create Date: 2025-03-16 00:00:00.000000
"""
from alembic import op


revision = '080_restore_hnsw_idx'
down_revision = '079_add_doc_oid_ds_idx'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 将 embedding 列恢复为 vector(768)，与 bge-base-zh-v1.5 模型维度一致
    #    这样 HNSW 索引才能正常创建
    op.execute("DROP INDEX IF EXISTS idx_doc_chunk_embedding")
    op.execute("""
        ALTER TABLE core_document_chunk
        ALTER COLUMN embedding TYPE vector(768)
    """)

    # 2. 重建 HNSW 索引（余弦距离）
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_chunk_embedding ON core_document_chunk "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    # 回退：删除索引，恢复为无维度约束的 vector
    op.execute("DROP INDEX IF EXISTS idx_doc_chunk_embedding")
    op.execute("""
        ALTER TABLE core_document_chunk
        ALTER COLUMN embedding TYPE vector
    """)
