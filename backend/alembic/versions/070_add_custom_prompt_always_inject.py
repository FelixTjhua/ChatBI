"""add always_inject field to custom_prompt

Revision ID: 070_add_custom_prompt_always_inject
Revises: 069_add_terminology_fk
Create Date: 2026-03-03 00:00:00.000000

自定义提示词注入策略优化：
- 新增 always_inject 字段，区分"全局规则"和"条件规则"
- always_inject=True: 全局规则，无论用户问什么都注入（如"所有查询排除测试数据"）
- always_inject=False: 条件规则，仅在关键词匹配命中时注入
- 去掉原来的"保底注入"逻辑，未命中就不注入，避免注入不相关内容干扰LLM
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '070_always_inject'
down_revision = '069_terminology_fk'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('custom_prompt', sa.Column('always_inject', sa.Boolean(), nullable=True, server_default='false'))


def downgrade():
    op.drop_column('custom_prompt', 'always_inject')
