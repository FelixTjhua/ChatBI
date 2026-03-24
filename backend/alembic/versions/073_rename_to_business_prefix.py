"""073: 重命名表为 business_ 前缀，匹配论文规范

按照论文设计文档要求：
- sql_example → business_sql_example (商业SQL示例库)
- term_dict → business_term (商业术语库)
- prompt_sql → prompt_business_sql (商业SQL生成提示词)
- prompt_analysis → prompt_business_analysis (商业数据分析提示词)
- prompt_forecast → prompt_business_forecast (商业数据预测提示词)

这些表为系统辅助功能表，不参与向量化，不属于商业知识库。

Revision ID: 073_business_prefix
Revises: 072_restructure
"""
from alembic import op

revision = '073_business_prefix'
down_revision = '072_restructure'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table('sql_example', 'business_sql_example')
    op.rename_table('term_dict', 'business_term')
    op.rename_table('prompt_sql', 'prompt_business_sql')
    op.rename_table('prompt_analysis', 'prompt_business_analysis')
    op.rename_table('prompt_forecast', 'prompt_business_forecast')


def downgrade() -> None:
    op.rename_table('business_sql_example', 'sql_example')
    op.rename_table('business_term', 'term_dict')
    op.rename_table('prompt_business_sql', 'prompt_sql')
    op.rename_table('prompt_business_analysis', 'prompt_analysis')
    op.rename_table('prompt_business_forecast', 'prompt_forecast')
