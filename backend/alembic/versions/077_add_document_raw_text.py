"""077: 为 core_document 添加 raw_text 字段

存储文档的完整原始文本，确保"零丢失解析"策略可验证。
分块过程中 table_overlap 类型的 chunk 不会被向量化，
但 raw_text 保留了 PDF/Excel/CSV 的全部原始文本，
支持全文溯源、完整性校验和全文搜索。

Revision ID: 077_add_raw_text
Revises: 076_fix_vector_index
"""
from alembic import op
import sqlalchemy as sa

revision = '077_add_raw_text'
down_revision = '076_fix_vector_index'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('core_document', sa.Column('raw_text', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('core_document', 'raw_text')
