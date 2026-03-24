"""086: 删除数据总结提示词表 prompt_business_summarization

data_summarization 意图已移除，总结类查询统一走 statistical_analysis。
不再需要独立的总结提示词表。

Revision ID: 086_drop_summarization_prompt
Revises: 085_seed_summarization
Create Date: 2026-03-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = '086_drop_summarization_prompt'
down_revision = '085_seed_summarization'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table('prompt_business_summarization')


def downgrade() -> None:
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
