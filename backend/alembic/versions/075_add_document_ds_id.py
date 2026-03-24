"""075: 为 core_document 添加 ds_id 字段

建立文档与数据源的显式关联，解决PDF数据源详情页无法加载文档信息的问题。

Revision ID: 075_document_ds_id
Revises: 074_input_type
"""
from alembic import op
import sqlalchemy as sa

revision = '075_document_ds_id'
down_revision = '074_input_type'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('core_document', sa.Column('ds_id', sa.BigInteger(), nullable=True))
    op.create_index('ix_core_document_ds_id', 'core_document', ['ds_id'])


def downgrade() -> None:
    op.drop_index('ix_core_document_ds_id', table_name='core_document')
    op.drop_column('core_document', 'ds_id')
