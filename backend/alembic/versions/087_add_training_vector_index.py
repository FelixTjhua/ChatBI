"""087: 为 business_sql_example 和 business_term 添加 HNSW 向量索引

缺陷 DB-1/DB-2：这两张表的 embedding 列没有向量索引，
导致 RAG 检索术语和 SQL 示例时做全表顺序扫描。
数据量增长后检索延迟会显著增加。

同时修复 business_sql_example.embedding 列缺少维度约束的问题
（VECTOR() → VECTOR(768)），与 core_document_chunk 对齐。

Revision ID: 087_training_vector_idx
Revises: 086_drop_summarization_prompt
"""
from alembic import op

revision = '087_training_vector_idx'
down_revision = '086_drop_summarization_prompt'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 修复 business_sql_example.embedding 列维度（VECTOR() → VECTOR(768)）
    # ALTER COLUMN TYPE 会自动校验现有数据维度是否匹配
    op.execute(
        "ALTER TABLE business_sql_example "
        "ALTER COLUMN embedding TYPE vector(768) USING embedding::vector(768)"
    )

    # 2. 为 business_sql_example 创建 HNSW 向量索引
    # 与 core_document_chunk 的索引参数对齐（m=16, ef_construction=64）
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_biz_sql_example_embedding "
        "ON business_sql_example USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # 3. 为 business_term 创建 HNSW 向量索引（如果有 embedding 列）
    # business_term 表可能没有 embedding 列，用 DO 块安全处理
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'business_term' AND column_name = 'embedding'
            ) THEN
                -- 修复维度
                EXECUTE 'ALTER TABLE business_term ALTER COLUMN embedding TYPE vector(768) USING embedding::vector(768)';
                -- 创建 HNSW 索引
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_biz_term_embedding ON business_term USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_biz_sql_example_embedding")
    op.execute("DROP INDEX IF EXISTS idx_biz_term_embedding")
    # 恢复为无维度约束的 VECTOR 类型
    op.execute(
        "ALTER TABLE business_sql_example "
        "ALTER COLUMN embedding TYPE vector USING embedding::vector"
    )
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'business_term' AND column_name = 'embedding'
            ) THEN
                EXECUTE 'ALTER TABLE business_term ALTER COLUMN embedding TYPE vector USING embedding::vector';
            END IF;
        END $$;
    """)
