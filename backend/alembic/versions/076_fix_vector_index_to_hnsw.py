"""076: 将 core_document_chunk 的向量索引从 IVFFlat 替换为 HNSW

IVFFlat 索引在空表上创建时聚类中心为空，后续插入数据后检索质量极差。
HNSW 索引无此限制，支持增量插入，且检索精度更高。

同时为 embedding 列添加维度约束（768维，对应 BAAI/bge-base-zh-v1.5 中英双语模型）。

Revision ID: 076_fix_vector_index
Revises: 075_document_ds_id
"""
from alembic import op

revision = '076_fix_vector_index'
down_revision = '075_document_ds_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 删除旧的 IVFFlat 索引（如果存在）
    op.execute("DROP INDEX IF EXISTS idx_doc_chunk_embedding")

    # 创建 HNSW 索引（支持空表创建、增量插入、更高检索精度）
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_chunk_embedding ON core_document_chunk "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )

    # 为 chunk_type 添加索引（加速 table_overlap 过滤查询）
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_chunk_type ON core_document_chunk (chunk_type)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_doc_chunk_type")
    op.execute("DROP INDEX IF EXISTS idx_doc_chunk_embedding")
    # 恢复 IVFFlat 索引
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_chunk_embedding ON core_document_chunk "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
