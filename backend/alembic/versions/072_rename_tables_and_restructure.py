"""072: 重命名表结构，满足毕设论文规范

- data_training → sql_example (SQL示例库)
- terminology → term_dict (术语库)
- custom_prompt → 拆分为 prompt_sql, prompt_analysis, prompt_forecast
- 新增: document_source, db_config, think_process, parse_log
- 重构: core_document_chunk → 统一向量表结构

Revision ID: 072_restructure
Revises: 071_doc_knowledge
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '072_restructure'
down_revision = '071_doc_knowledge'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========== 1. 重命名 data_training → sql_example ==========
    op.rename_table('data_training', 'sql_example')
    
    # ========== 2. 重命名 terminology → term_dict ==========
    op.rename_table('terminology', 'term_dict')
    
    # ========== 3. 拆分 custom_prompt 为三张表 ==========
    # 3a. 创建 prompt_sql
    op.create_table(
        'prompt_sql',
        sa.Column('id', sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column('oid', sa.BigInteger, nullable=True, server_default='1'),
        sa.Column('name', sa.String(255), nullable=True, server_default=''),
        sa.Column('prompt', sa.Text, nullable=True),
        sa.Column('specific_ds', sa.Boolean, server_default='false'),
        sa.Column('datasource_ids', JSONB, nullable=True),
        sa.Column('always_inject', sa.Boolean, server_default='false'),
        sa.Column('create_time', sa.DateTime(timezone=False), nullable=True),
    )
    # 3b. 创建 prompt_analysis
    op.create_table(
        'prompt_analysis',
        sa.Column('id', sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column('oid', sa.BigInteger, nullable=True, server_default='1'),
        sa.Column('name', sa.String(255), nullable=True, server_default=''),
        sa.Column('prompt', sa.Text, nullable=True),
        sa.Column('specific_ds', sa.Boolean, server_default='false'),
        sa.Column('datasource_ids', JSONB, nullable=True),
        sa.Column('always_inject', sa.Boolean, server_default='false'),
        sa.Column('create_time', sa.DateTime(timezone=False), nullable=True),
    )
    # 3c. 创建 prompt_forecast
    op.create_table(
        'prompt_forecast',
        sa.Column('id', sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column('oid', sa.BigInteger, nullable=True, server_default='1'),
        sa.Column('name', sa.String(255), nullable=True, server_default=''),
        sa.Column('prompt', sa.Text, nullable=True),
        sa.Column('specific_ds', sa.Boolean, server_default='false'),
        sa.Column('datasource_ids', JSONB, nullable=True),
        sa.Column('always_inject', sa.Boolean, server_default='false'),
        sa.Column('create_time', sa.DateTime(timezone=False), nullable=True),
    )
    
    # 3d. 迁移数据从 custom_prompt 到三张新表
    op.execute("""
        INSERT INTO prompt_sql (oid, name, prompt, specific_ds, datasource_ids, always_inject, create_time)
        SELECT oid, name, prompt, specific_ds, datasource_ids, always_inject, create_time
        FROM custom_prompt WHERE type = 'GENERATE_SQL'
    """)
    op.execute("""
        INSERT INTO prompt_analysis (oid, name, prompt, specific_ds, datasource_ids, always_inject, create_time)
        SELECT oid, name, prompt, specific_ds, datasource_ids, always_inject, create_time
        FROM custom_prompt WHERE type = 'ANALYSIS'
    """)
    op.execute("""
        INSERT INTO prompt_forecast (oid, name, prompt, specific_ds, datasource_ids, always_inject, create_time)
        SELECT oid, name, prompt, specific_ds, datasource_ids, always_inject, create_time
        FROM custom_prompt WHERE type = 'PREDICT_DATA'
    """)
    
    # 3e. 删除旧表
    op.drop_table('custom_prompt')
    
    # ========== 4. 新增业务表 ==========
    # 4a. document_source (数据源元信息，替代 core_document)
    # 保留 core_document 不动，添加 source_type 字段
    op.add_column('core_document', sa.Column('source_type', sa.String(20), nullable=True, server_default='file'))
    op.add_column('core_document', sa.Column('source_name', sa.String(500), nullable=True))
    op.add_column('core_document', sa.Column('description', sa.Text, nullable=True))
    
    # 4b. db_config (数据库连接配置 - 复用 core_datasource，添加标记)
    # core_datasource 已有完整的数据库连接字段，不需要新表
    
    # 4c. think_process (思考过程持久化)
    op.create_table(
        'think_process',
        sa.Column('id', sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column('record_id', sa.BigInteger, nullable=False),
        sa.Column('chat_id', sa.BigInteger, nullable=True),
        sa.Column('user_id', sa.BigInteger, nullable=True),
        sa.Column('stages', JSONB, nullable=True),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('total_time_ms', sa.Integer, nullable=True),
        sa.Column('create_time', sa.DateTime(timezone=False), nullable=True),
    )
    op.create_index('ix_think_process_record_id', 'think_process', ['record_id'])
    op.create_index('ix_think_process_chat_id', 'think_process', ['chat_id'])
    
    # 4d. parse_log (解析日志)
    op.create_table(
        'parse_log',
        sa.Column('id', sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column('document_id', sa.BigInteger, nullable=True),
        sa.Column('source_type', sa.String(20), nullable=True),
        sa.Column('source_name', sa.String(500), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, server_default='success'),
        sa.Column('total_chunks', sa.Integer, nullable=True, server_default='0'),
        sa.Column('vectorized_count', sa.Integer, nullable=True, server_default='0'),
        sa.Column('processing_time', sa.Float, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('oid', sa.BigInteger, nullable=True, server_default='1'),
        sa.Column('user_id', sa.BigInteger, nullable=True),
        sa.Column('create_time', sa.DateTime(timezone=False), nullable=True),
    )
    
    # ========== 5. 重构向量表 core_document_chunk ==========
    # 添加论文要求的字段: source_type, source_name, info, library_id
    op.add_column('core_document_chunk', sa.Column('source_type', sa.String(20), nullable=True))
    op.add_column('core_document_chunk', sa.Column('source_name', sa.String(500), nullable=True))
    op.add_column('core_document_chunk', sa.Column('info', sa.Text, nullable=True))
    op.add_column('core_document_chunk', sa.Column('library_id', sa.BigInteger, nullable=True))
    # embedding 列已存在于 sql_example 和 term_dict 中，core_document_chunk 需要添加
    # 检查是否已有 embedding 列
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE core_document_chunk ADD COLUMN IF NOT EXISTS embedding vector;
        EXCEPTION WHEN others THEN NULL;
        END $$;
    """)
    op.create_index('ix_chunk_library_id', 'core_document_chunk', ['library_id'])
    op.create_index('ix_chunk_source_type', 'core_document_chunk', ['source_type'])


def downgrade() -> None:
    # 回滚：恢复原表名
    op.rename_table('sql_example', 'data_training')
    op.rename_table('term_dict', 'terminology')
    
    # 恢复 custom_prompt
    op.create_table(
        'custom_prompt',
        sa.Column('id', sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column('oid', sa.BigInteger, nullable=True),
        sa.Column('type', sa.String(50), nullable=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('prompt', sa.Text, nullable=True),
        sa.Column('specific_ds', sa.Boolean, server_default='false'),
        sa.Column('datasource_ids', JSONB, nullable=True),
        sa.Column('always_inject', sa.Boolean, server_default='false'),
        sa.Column('create_time', sa.DateTime(timezone=False), nullable=True),
    )
    
    # downgrade时需要将拆分表的数据迁移回custom_prompt
    op.execute("""
        INSERT INTO custom_prompt (oid, type, name, prompt, specific_ds, datasource_ids, always_inject, create_time)
        SELECT oid, 'GENERATE_SQL', name, prompt, specific_ds, datasource_ids, always_inject, create_time
        FROM prompt_sql
    """)
    op.execute("""
        INSERT INTO custom_prompt (oid, type, name, prompt, specific_ds, datasource_ids, always_inject, create_time)
        SELECT oid, 'ANALYSIS', name, prompt, specific_ds, datasource_ids, always_inject, create_time
        FROM prompt_analysis
    """)
    op.execute("""
        INSERT INTO custom_prompt (oid, type, name, prompt, specific_ds, datasource_ids, always_inject, create_time)
        SELECT oid, 'PREDICT_DATA', name, prompt, specific_ds, datasource_ids, always_inject, create_time
        FROM prompt_forecast
    """)
    
    op.drop_table('prompt_sql')
    op.drop_table('prompt_analysis')
    op.drop_table('prompt_forecast')
    op.drop_table('think_process')
    op.drop_table('parse_log')
    
    op.drop_column('core_document', 'source_type')
    op.drop_column('core_document', 'source_name')
    op.drop_column('core_document', 'description')
    op.drop_column('core_document_chunk', 'source_type')
    op.drop_column('core_document_chunk', 'source_name')
    op.drop_column('core_document_chunk', 'info')
    op.drop_column('core_document_chunk', 'library_id')
