"""规则引擎图表配置生成器（替代 LLM 调用，从 ~150s → <1ms）"""
import re
from typing import Dict, Any, List, Optional
from decimal import Decimal

from common.utils.utils import ChatBILogUtil


def build_chart_config(
    chart_type: str,
    fields: List[str],
    data: List[Dict[str, Any]],
    question: str = '',
    sql: str = '',
    terminologies: str = '',
) -> Optional[Dict[str, Any]]:
    """规则引擎：根据数据特征自动生成图表配置 JSON。"""
    if not fields or not data:
        return None

    chart_type = (chart_type or '').lower().strip()
    
    # 分类字段 vs 数值字段
    numeric_fields = []
    text_fields = []
    
    # 从第一行数据推断类型
    sample_row = data[0] if data else {}
    for f in fields:
        val = sample_row.get(f)
        if isinstance(val, (int, float, Decimal)):
            numeric_fields.append(f)
        elif val is not None and _is_numeric_str(val):
            numeric_fields.append(f)
        else:
            text_fields.append(f)

    row_count = len(data)
    field_count = len(fields)

    # 生成标题
    title = _generate_title(question, chart_type, fields, terminologies)

    try:
        if chart_type == 'table':
            return _build_table(title, fields)
        elif chart_type == 'pie':
            return _build_pie(title, fields, numeric_fields, text_fields)
        elif chart_type in ('column', 'bar', 'line', 'area'):
            return _build_axis_chart(chart_type, title, fields, numeric_fields, text_fields, row_count)
        elif chart_type == 'kpi':
            return None  # KPI 已有快速路径
        elif chart_type in ('box', 'heatmap', 'dual_axis', 'sankey', 'funnel'):
            return None  # 复杂图表回退 LLM
        else:
            # 未知类型，尝试自动推断
            inferred = _infer_chart_type(numeric_fields, text_fields, row_count, question)
            if inferred == 'table':
                return _build_table(title, fields)
            elif inferred == 'pie':
                return _build_pie(title, fields, numeric_fields, text_fields)
            else:
                return _build_axis_chart(inferred, title, fields, numeric_fields, text_fields, row_count)
    except Exception as e:
        ChatBILogUtil.error(f"[chart-rule-engine] Failed to build config: {e}")
        return None


def _is_numeric_str(val) -> bool:
    """检查字符串是否为数值"""
    if not isinstance(val, str):
        return False
    try:
        float(val.replace(',', ''))
        return True
    except (ValueError, AttributeError):
        return False


def _generate_title(question: str, chart_type: str, fields: List[str], terminologies: str) -> str:
    """从问题中提取简洁标题"""
    if not question:
        return '数据查询结果'
    
    # 去掉常见前缀
    q = question.strip()
    for prefix in ['请帮我', '帮我', '请', '我想', '能不能', '可以', '用', '使用', '查询', '查看', '看看',
                    'please', 'can you', 'show me', 'help me', 'I want to']:
        if q.lower().startswith(prefix.lower()):
            q = q[len(prefix):].strip()
    
    # 去掉图表类型描述
    for ct in ['饼图展示', '柱状图展示', '折线图展示', '条形图展示', '表格展示',
                '用饼图', '用柱状图', '用折线图', '用条形图',
                'pie chart', 'bar chart', 'line chart']:
        q = q.replace(ct, '').strip()
    
    # 截断过长标题
    if len(q) > 30:
        q = q[:30]
    
    return q if q else '数据查询结果'


def _field_display_name(field: str) -> str:
    """将 SQL 别名转为显示名"""
    # 去掉常见的 SQL 别名后缀
    name = field
    # 如果是中文字段名，直接返回
    if any('\u4e00' <= c <= '\u9fff' for c in name):
        return name
    # snake_case → 空格分隔
    name = name.replace('_', ' ').strip()
    return name if name else field


def _build_table(title: str, fields: List[str]) -> Dict[str, Any]:
    """构建 table 类型配置"""
    columns = [{'name': _field_display_name(f), 'value': f} for f in fields]
    return {
        'type': 'table',
        'title': title,
        'columns': columns,
    }


def _build_pie(title: str, fields: List[str], numeric_fields: List[str], text_fields: List[str]) -> Optional[Dict[str, Any]]:
    """构建 pie 类型配置"""
    if not numeric_fields or not text_fields:
        # 饼图需要至少一个数值字段和一个分类字段
        if len(fields) == 2:
            # 两个字段时猜测：第一个是分类，第二个是数值
            return {
                'type': 'pie',
                'title': title,
                'axis': {
                    'y': {'name': _field_display_name(fields[1]), 'value': fields[1]},
                    'series': {'name': _field_display_name(fields[0]), 'value': fields[0]},
                },
            }
        return None
    
    # 选择最佳的数值字段（优先选名字中含"额"/"量"/"数"/"比"/"率"/"count"/"sum"/"total"/"amount"的）
    value_field = _pick_best_numeric(numeric_fields, text_fields)
    # 选择分类字段
    category_field = text_fields[0]
    
    return {
        'type': 'pie',
        'title': title,
        'axis': {
            'y': {'name': _field_display_name(value_field), 'value': value_field},
            'series': {'name': _field_display_name(category_field), 'value': category_field},
        },
    }


def _build_axis_chart(
    chart_type: str, title: str, fields: List[str],
    numeric_fields: List[str], text_fields: List[str], row_count: int,
) -> Optional[Dict[str, Any]]:
    """构建 column/bar/line/area 类型配置"""
    if not numeric_fields:
        return None
    
    value_field = _pick_best_numeric(numeric_fields, text_fields)
    
    if text_fields:
        # 有分类字段：x=分类, y=数值
        category_field = text_fields[0]
        axis: Dict[str, Any] = {
            'x': {'name': _field_display_name(category_field), 'value': category_field},
            'y': {'name': _field_display_name(value_field), 'value': value_field},
        }
        # 如果有第二个分类字段，作为 series
        if len(text_fields) > 1:
            axis['series'] = {'name': _field_display_name(text_fields[1]), 'value': text_fields[1]}
    elif len(numeric_fields) >= 2:
        # 全是数值字段：第一个作为 x，第二个作为 y
        axis = {
            'x': {'name': _field_display_name(numeric_fields[0]), 'value': numeric_fields[0]},
            'y': {'name': _field_display_name(numeric_fields[1]), 'value': numeric_fields[1]},
        }
    else:
        return None
    
    return {
        'type': chart_type,
        'title': title,
        'axis': axis,
    }


def _pick_best_numeric(numeric_fields: List[str], text_fields: List[str]) -> str:
    """选择最佳的数值字段"""
    if len(numeric_fields) == 1:
        return numeric_fields[0]
    
    # 优先级关键词
    priority_keywords = ['额', '量', '数', '比', '率', 'count', 'sum', 'total', 'amount', 'sales', 'revenue', 'percentage', 'ratio']
    for f in numeric_fields:
        fl = f.lower()
        for kw in priority_keywords:
            if kw in fl:
                return f
    
    return numeric_fields[0]


def _infer_chart_type(numeric_fields: List[str], text_fields: List[str], row_count: int, question: str) -> str:
    """根据数据特征推断图表类型"""
    q = question.lower()
    
    # 用户明确指定
    # 添加中文同义词，提升饼图/折线图等的自动推断准确率
    if '饼图' in q or 'pie' in q or '占比' in q or '比例' in q or '份额' in q or '百分比' in q or '构成' in q or '组成' in q:
        return 'pie'
    if '折线' in q or 'line' in q or '趋势' in q or 'trend' in q or '走势' in q or '变化' in q or '波动' in q:
        return 'line'
    if '条形' in q or 'bar' in q or '横向' in q:
        return 'bar'
    if '柱' in q or 'column' in q or '柱状' in q:
        return 'column'
    
    # 数据特征推断
    if not numeric_fields:
        return 'table'
    if row_count == 1:
        return 'table'
    if row_count <= 8 and text_fields:
        return 'column'
    if row_count > 20:
        return 'line'
    
    return 'column'
