"""Add composite index on core_document(oid, ds_id)

Revision ID: 079_add_doc_oid_ds_idx
Revises: 078_fix_doc_col_types
Create Date: 2025-03-15 00:00:00.000000

修复说明：
search_document_chunks() 通过 JOIN core_document 使用 WHERE d.oid = :oid AND d.ds_id = :ds_id 过滤，
没有索引时大量文档场景下会导致全表扫描。添加复合索引加速检索。
"""
from alembic import op

revision = '079_add_doc_oid_ds_idx'
down_revision = '078_fix_doc_col_types'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        'ix_core_document_oid_ds_id',
        'core_document',
        ['oid', 'ds_id'],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index('ix_core_document_oid_ds_id', table_name='core_document')
