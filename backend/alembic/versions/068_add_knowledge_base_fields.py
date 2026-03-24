"""add sql_mapping to terminology and ddl/doc to data_training

Revision ID: 068_add_knowledge_base_fields
Revises: 067_drop_chat_feedback
Create Date: 2025-01-01 00:00:00.000000

知识库数据模型完善（导师要求1-3）：
- Terminology 表新增 sql_mapping 字段（SQL映射表达式）
- DataTraining 表新增 ddl 字段（DDL定义语句）
- DataTraining 表新增 doc 字段（文档片段/半结构化知识）
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 's7t8u9v0w1x2'
down_revision = 'r6s7t8u9v0w1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Terminology: 新增 sql_mapping 字段（SQL映射）
    op.add_column('terminology', sa.Column('sql_mapping', sa.Text(), nullable=True))

    # DataTraining: 新增 ddl 字段（DDL定义）
    op.add_column('data_training', sa.Column('ddl', sa.Text(), nullable=True))

    # DataTraining: 新增 doc 字段（文档片段）
    op.add_column('data_training', sa.Column('doc', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('data_training', 'doc')
    op.drop_column('data_training', 'ddl')
    op.drop_column('terminology', 'sql_mapping')
