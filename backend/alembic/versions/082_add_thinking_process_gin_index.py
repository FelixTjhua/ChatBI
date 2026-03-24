"""082: 为 thinking_process JSONB 列添加 GIN 索引

设计理由：
迁移 081 将 rag_results 和 thinking_process 都升级为 JSONB，
但只为 rag_results 创建了 GIN 索引，遗漏了 thinking_process。

thinking_process 存储完整的 RAG 思考链路数据（各阶段耗时、状态、质量指标），
缺少 GIN 索引时，按阶段状态筛选（如查找失败的阶段）或按耗时排序
都会退化为全表顺序扫描，随着对话记录增长性能会急剧下降。

Revision ID: 082_thinking_gin
Revises: 081_rag_jsonb
Create Date: 2025-03-18 00:00:00.000000
"""
from alembic import op


revision = '082_thinking_gin'
down_revision = '081_rag_jsonb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_chat_record_thinking_process_gin
        ON chat_record USING gin (thinking_process jsonb_path_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chat_record_thinking_process_gin")
