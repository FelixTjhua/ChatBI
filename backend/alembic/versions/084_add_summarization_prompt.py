"""084: 添加数据总结提示词表 prompt_business_summarization

新增 SUMMARIZATION 类型的自定义提示词表，用于 data_summarization 意图。
数据总结场景走 SQL 路径生成明细表后，在延迟分析阶段注入总结提示词。

Revision ID: 084_summarization_prompt
Revises: 083_add_chart_image
Create Date: 2026-03-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = '084_summarization_prompt'
down_revision = '083_add_chart_image'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS prompt_business_summarization (
            id SERIAL PRIMARY KEY,
            oid INTEGER DEFAULT 1,
            name VARCHAR DEFAULT '',
            prompt TEXT DEFAULT '',
            specific_ds BOOLEAN DEFAULT FALSE,
            datasource_ids JSONB,
            always_inject BOOLEAN DEFAULT FALSE,
            create_time TIMESTAMP
        )
    """)


def downgrade() -> None:
    op.drop_table('prompt_business_summarization')
