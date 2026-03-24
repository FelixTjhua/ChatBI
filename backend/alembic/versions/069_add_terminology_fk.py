"""add foreign key constraint on terminology.pid

Revision ID: 069_add_terminology_fk
Revises: 068_add_knowledge_base_fields
Create Date: 2026-03-03 00:00:00.000000

 术语表 pid 字段缺少外键约束
- 添加 terminology.pid -> terminology.id 的自引用外键
- ON DELETE CASCADE：删除父术语时自动删除同义词子节点
- 先清理孤儿记录（pid 指向不存在的 id），避免约束添加失败
"""
from alembic import op
import sqlalchemy as sa


revision = '069_terminology_fk'
down_revision = 's7t8u9v0w1x2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 清理孤儿记录：pid 不为 NULL 但指向不存在的父术语
    op.execute("""
        DELETE FROM terminology 
        WHERE pid IS NOT NULL 
        AND pid NOT IN (SELECT id FROM terminology WHERE pid IS NULL)
    """)
    
    # 添加自引用外键约束
    op.create_foreign_key(
        'fk_terminology_pid',
        'terminology', 'terminology',
        ['pid'], ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('fk_terminology_pid', 'terminology', type_='foreignkey')
