"""088: 删除术语库、SQL示例库、自定义提示词三个模块的 specific_ds 和 datasource_ids 字段

简化设计：移除"指定数据源"功能，所有知识库条目统一为全局生效。
涉及表：business_term、business_sql_example、prompt_business_sql、
        prompt_business_analysis、prompt_business_forecast

Revision ID: 088_drop_specific_ds
Revises: 087_training_vector_idx
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '088_drop_specific_ds'
down_revision = '087_training_vector_idx'
branch_labels = None
depends_on = None

# 需要删除字段的表
_TABLES = [
    'business_term',
    'business_sql_example',
    'prompt_business_sql',
    'prompt_business_analysis',
    'prompt_business_forecast',
]


def upgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, 'specific_ds')
        op.drop_column(table, 'datasource_ids')


def downgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column('specific_ds', sa.Boolean(), nullable=True, server_default='false'))
        op.add_column(table, sa.Column('datasource_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'))
