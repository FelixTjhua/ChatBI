"""数据源组件路由器 - 基于数据源类型的RAG组件路由矩阵"""

from typing import Dict, List, Set, Optional


# ========== 数据源类型分类 ==========

# 原生数据库类型（标准化后的名称）：支持SQL生成的数据源
DATABASE_TYPES: Set[str] = {'pg', 'mysql', 'oracle'}

# 文件类数据源（注意：PDF 虽然是文件，但处理路径完全不同）
FILE_TYPES: Set[str] = {'excel', 'csv', 'pdf'}

# 结构化文件类型：支持数据分析和预测（数据已导入PG，SQL路径统一）
STRUCTURED_FILE_TYPES: Set[str] = {'excel', 'csv'}

# 文档类型：仅支持文档问答，表格数据走分析提示词
DOCUMENT_TYPES: Set[str] = {'pdf'}


def normalize_ds_type(ds_type: str) -> str:
    """标准化数据源类型名称，将各种变体统一为标准名称，对未知类型记录警告日志。"""
    if not ds_type:
        return 'database'
    ds_lower = ds_type.lower().strip()
    # PostgreSQL 变体
    if ds_lower in ('pg', 'postgresql', 'postgres'):
        return 'pg'
    # 其他直接返回
    if ds_lower in ('mysql', 'oracle', 'excel', 'csv', 'pdf', 'database'):
        return ds_lower
    # 未知类型：记录警告并默认为数据库（防御性处理）
    import logging
    logging.getLogger(__name__).warning(
        f"normalize_ds_type: 未知数据源类型 '{ds_type}'，默认路由到 'database'。"
        f"请检查数据源配置是否正确。支持的类型: pg/postgresql/postgres, mysql, oracle, excel, csv, pdf"
    )
    return 'database'


def is_database_type(ds_type: str) -> bool:
    """判断是否为原生数据库类型（唯一支持SQL生成组件的类型）"""
    normalized = normalize_ds_type(ds_type)
    return normalized in ('pg', 'mysql', 'oracle')


def is_file_type(ds_type: str) -> bool:
    """判断是否为文件类数据源"""
    normalized = normalize_ds_type(ds_type)
    return normalized in ('excel', 'csv', 'pdf')


def is_structured_file_type(ds_type: str) -> bool:
    """判断是否为结构化文件类型（Excel/CSV，数据已导入PG）"""
    normalized = normalize_ds_type(ds_type)
    return normalized in ('excel', 'csv')


def is_document_type(ds_type: str) -> bool:
    """判断是否为文档类型（PDF）"""
    normalized = normalize_ds_type(ds_type)
    return normalized == 'pdf'


def is_single_table_mode(ds_type: str) -> bool:
    """判断数据源是否为单表模式（Excel/CSV 导入 PG 后通常为单表）
    
    单表模式下应过滤含 JOIN、子查询等多表操作的 SQL 示例，
    避免误导 LLM 生成不可执行的复杂 SQL。
    """
    return is_structured_file_type(ds_type)


def is_sql_allowed(ds_type: str) -> bool:
    """判断数据源是否允许使用SQL生成组件"""
    normalized = normalize_ds_type(ds_type)
    if normalized == 'pdf':
        return False
    return True


def is_analysis_allowed(ds_type: str, has_table_data: bool = True) -> bool:
    """判断数据源是否允许使用数据分析提示词"""
    normalized = normalize_ds_type(ds_type)
    if normalized == 'pdf':
        return False  # PDF不支持数据分析
    return True  # Database/Excel/CSV都支持


def is_prediction_allowed(ds_type: str, has_table_data: bool = True) -> bool:
    """判断数据源是否允许使用数据预测提示词"""
    normalized = normalize_ds_type(ds_type)
    if normalized == 'pdf':
        return False  # PDF不支持数据预测
    return True


def is_document_qa_allowed(ds_type: str) -> bool:
    """判断数据源是否支持文档问答
    
    仅 PDF 支持文档问答路径（向量语义检索 + LLM 生成回答）。
    Database/Excel/CSV 走 NL2SQL 路径，不走文档问答。
    """
    return is_document_type(ds_type)


def is_chart_allowed(ds_type: str) -> bool:
    """判断数据源是否支持图表生成（AntV G2 可视化）
    
    仅结构化数据源（Database/Excel/CSV）支持图表生成。
    PDF 是非结构化文档，不生成图表。
    """
    normalized = normalize_ds_type(ds_type)
    if normalized == 'pdf':
        return False
    return True


def should_skip_sql_examples(ds_type: str, intent_route: str) -> bool:
    """判断是否应跳过SQL示例库检索"""
    if not is_sql_allowed(ds_type):
        return True  # PDF不走SQL路径
    return intent_route == 'general_chat'  # 仅在general_chat时跳过


def should_skip_sql_custom_prompts(ds_type: str, intent_route: str) -> bool:
    """判断是否应跳过SQL生成自定义提示词检索
    
    与should_skip_sql_examples逻辑一致。
    """
    return should_skip_sql_examples(ds_type, intent_route)


def should_skip_init_messages(ds_type: str, intent_route: str) -> bool:
    """判断是否应跳过init_messages()（SQL消息列表初始化）
    
    init_messages()构建SQL生成的消息列表，非数据库类型不需要。
    """
    return should_skip_sql_examples(ds_type, intent_route)


def get_allowed_components(ds_type: str, intent: str = '', has_table_data: bool = True) -> Dict[str, bool]:
    """获取指定数据源类型和意图下允许使用的组件列表"""
    sql_allowed = is_sql_allowed(ds_type)
    
    return {
        'terminology': not is_document_type(ds_type),  # 商业术语库：Database/Excel/CSV启用，PDF不需要
        'sql_generation_prompt': sql_allowed,  # SQL生成提示词：仅SQL路径
        'sql_example_library': sql_allowed,  # SQL示例库：仅SQL路径
        'data_analysis_prompt': is_analysis_allowed(ds_type),
        'data_prediction_prompt': is_prediction_allowed(ds_type),
        'visualization': is_chart_allowed(ds_type),  # 使用 is_chart_allowed 而非 sql_allowed
        'recommendation': True,  # 推荐问题：所有类型都支持
        'document_qa': is_document_qa_allowed(ds_type),  # 文档问答：仅PDF
        'batch_processing': normalize_ds_type(ds_type) == 'csv',  # 批量处理：仅CSV
        'realtime_refresh': is_database_type(ds_type),  # 实时刷新：仅数据库
        'chart_drilldown': is_database_type(ds_type),  # 图表钻取：仅数据库
        'query_cache': is_database_type(ds_type),  # 查询缓存：仅数据库
    }


def get_ds_type_label(ds_type: str) -> str:
    """获取数据源类型的中文标签（用于日志和前端展示）"""
    labels = {
        'pg': 'PostgreSQL数据库',
        'mysql': 'MySQL数据库',
        'oracle': 'Oracle数据库',
        'excel': 'Excel文件',
        'csv': 'CSV文件',
        'pdf': 'PDF文档',
    }
    normalized = normalize_ds_type(ds_type)
    return labels.get(normalized, f'未知类型({ds_type})')


def get_routing_reason(ds_type: str, component: str) -> str:
    """获取路由决策的原因说明（用于日志和调试）"""
    normalized = normalize_ds_type(ds_type)
    label = get_ds_type_label(ds_type)
    
    if component in ('sql_generation', 'sql_examples', 'sql_generation_prompt', 'sql_example_library'):
        if is_database_type(ds_type):
            return f'{label}支持SQL生成组件（原生数据库）'
        elif is_structured_file_type(ds_type):
            return f'{label}数据已导入PG，SQL路径统一，示例按ds_id隔离'
        elif is_document_type(ds_type):
            return f'{label}为非结构化文档，不支持SQL路径，走RAG文档问答'
        else:
            return f'{label}统一启用SQL生成组件'
    
    if component in ('analysis', 'data_analysis_prompt'):
        if normalized == 'pdf':
            return f'{label}为非结构化文档，不支持数据分析'
        return f'{label}支持数据分析'
    
    if component in ('prediction', 'data_prediction_prompt'):
        if normalized == 'pdf':
            return f'{label}为非结构化文档，不支持数据预测'
        return f'{label}支持数据预测'
    
    return f'{label}支持{component}组件'
