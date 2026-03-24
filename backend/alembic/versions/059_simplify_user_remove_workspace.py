"""simplify user and remove workspace

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-02-03

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h8i9j0k1l2m3'
down_revision = 'g7h8i9j0k1l2'
branch_labels = None
depends_on = None


def upgrade():
    # 1. 添加role字段到用户表
    op.add_column('sys_user', sa.Column('role', sa.String(length=50), nullable=False, server_default='member'))
    
    # 2. 将admin账户的role设置为admin
    op.execute("UPDATE sys_user SET role = 'admin' WHERE account = 'admin'")
    
    # 3. 将所有用户的oid设置为1（默认工作空间）
    op.execute("UPDATE sys_user SET oid = 1 WHERE oid IS NULL OR oid = 0")
    
    # 4. 删除origin字段（保留oid字段用于向后兼容）
    op.drop_column('sys_user', 'origin')
    
    # 5. 删除工作空间相关表
    op.drop_table('sys_user_ws')
    op.drop_table('sys_workspace')
    
    # 6. 删除用户平台关联表（如果不需要第三方登录）
    op.drop_table('sys_user_platform')


def downgrade():
    # 恢复工作空间表
    op.create_table('sys_workspace',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('create_time', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 恢复用户工作空间关联表
    op.create_table('sys_user_ws',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('uid', sa.BigInteger(), nullable=False),
        sa.Column('oid', sa.BigInteger(), nullable=False),
        sa.Column('weight', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 恢复用户平台表
    op.create_table('sys_user_platform',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('uid', sa.BigInteger(), nullable=False),
        sa.Column('origin', sa.Integer(), nullable=False),
        sa.Column('platform_uid', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 恢复origin字段
    op.add_column('sys_user', sa.Column('origin', sa.Integer(), nullable=False, server_default='0'))
    
    # 删除role字段
    op.drop_column('sys_user', 'role')
