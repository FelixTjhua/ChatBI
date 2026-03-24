"""cleanup unused tables

Remove legacy tables that are no longer used by any module:
- terms: replaced by terminology table
- sys_arg: no code references, never used
- license: replaced by in-memory ChatBILicenseUtil
- rsa: no longer needed
- audit_log: model exists but no code writes to it

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-02-10
"""
from alembic import op
import sqlalchemy as sa

revision = 'k1l2m3n4o5p6'
down_revision = 'j0k1l2m3n4o5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 所有操作使用 IF EXISTS，防止表已不存在时报错
    op.execute("DROP TABLE IF EXISTS terms CASCADE")
    op.execute("DROP TABLE IF EXISTS sys_arg CASCADE")
    op.execute("DROP TABLE IF EXISTS license CASCADE")
    op.execute("DROP TABLE IF EXISTS rsa CASCADE")
    op.execute("DROP TABLE IF EXISTS audit_log CASCADE")
    # 删除未使用的文档管理表（空表，代码无引用）
    op.execute("DROP TABLE IF EXISTS core_document_chunk CASCADE")
    op.execute("DROP TABLE IF EXISTS core_document CASCADE")


def downgrade() -> None:
    # 恢复 audit_log
    op.create_table('audit_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('user_name', sa.String(255), nullable=True),
        sa.Column('action', sa.String(255), nullable=False),
        sa.Column('resource_type', sa.String(255), nullable=True),
        sa.Column('resource_id', sa.BigInteger(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(255), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('oid', sa.BigInteger(), nullable=False, server_default='1'),
        sa.Column('create_time', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 恢复 rsa
    op.create_table('rsa',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('public_key', sa.Text(), nullable=True),
        sa.Column('private_key', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rsa_id'), 'rsa', ['id'], unique=False)

    # 恢复 license
    op.create_table('license',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('license', sa.Text(), nullable=True),
        sa.Column('update_time', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_license_id'), 'license', ['id'], unique=False)

    # 恢复 sys_arg
    op.create_table('sys_arg',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('pkey', sa.String(255), nullable=False),
        sa.Column('pval', sa.String(255), nullable=True),
        sa.Column('type', sa.String(255), nullable=True),
        sa.Column('sort_no', sa.Integer(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sys_arg_id'), 'sys_arg', ['id'], unique=False)

    # 恢复 terms
    op.create_table('terms',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('term', sa.String(255), nullable=False),
        sa.Column('definition', sa.String(255), nullable=False),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('create_time', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_terms_id'), 'terms', ['id'], unique=False)
