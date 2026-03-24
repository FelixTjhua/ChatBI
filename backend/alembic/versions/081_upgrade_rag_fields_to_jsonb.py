"""081: 将 rag_results 和 thinking_process 从 Text 升级为 JSONB

设计理由：
这两个字段存储的是 JSON 结构数据（RAG检索结果、思考过程），
使用 JSONB 类型可以：
1. 利用 PostgreSQL 的 JSON 查询操作符（@>, ->, ?）进行结构化查询
2. 自动校验 JSON 格式，避免存入非法 JSON 字符串
3. 支持 GIN 索引加速 JSON 内部字段查询
4. 存储效率更高（JSONB 是二进制格式，解析更快）

迁移策略：
- 使用 USING 子句将现有 Text 数据原地转换为 JSONB
- 空字符串和 NULL 保持为 NULL
- 非法 JSON 字符串会导致迁移失败，需提前清理

Revision ID: 081_rag_jsonb
Revises: 080_restore_hnsw_idx
Create Date: 2025-03-16 00:00:00.000000
"""
from alembic import op


revision = '081_rag_jsonb'
down_revision = '080_restore_hnsw_idx'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 清理可能存在的非法 JSON 数据（空字符串 → NULL）
    op.execute("""
        UPDATE chat_record
        SET rag_results = NULL
        WHERE rag_results IS NOT NULL AND (rag_results = '' OR rag_results = 'null')
    """)
    op.execute("""
        UPDATE chat_record
        SET thinking_process = NULL
        WHERE thinking_process IS NOT NULL AND (thinking_process = '' OR thinking_process = 'null')
    """)

    # 2. 将 Text 列转换为 JSONB
    op.execute("""
        ALTER TABLE chat_record
        ALTER COLUMN rag_results TYPE JSONB USING rag_results::jsonb
    """)
    op.execute("""
        ALTER TABLE chat_record
        ALTER COLUMN thinking_process TYPE JSONB USING thinking_process::jsonb
    """)

    # 3. 添加 GIN 索引，支持 JSON 内部字段查询（如按意图类型筛选）
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_chat_record_rag_results_gin
        ON chat_record USING gin (rag_results jsonb_path_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chat_record_rag_results_gin")
    op.execute("""
        ALTER TABLE chat_record
        ALTER COLUMN rag_results TYPE TEXT USING rag_results::text
    """)
    op.execute("""
        ALTER TABLE chat_record
        ALTER COLUMN thinking_process TYPE TEXT USING thinking_process::text
    """)
