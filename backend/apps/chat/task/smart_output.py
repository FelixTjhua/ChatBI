"""智能输出格式决策器 — ChatBI核心智能模块"""
import math
import re
from decimal import Decimal
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, date

from common.utils.utils import ChatBILogUtil


class OutputFormat:
    """输出格式枚举"""
    NATURAL_LANGUAGE = 'natural_language'  # 自然语言句子
    TABLE = 'table'                        # 表格
    LINE_CHART = 'line'                    # 折线图
    BAR_CHART = 'bar'                      # 柱状图
    PIE_CHART = 'pie'                      # 饼图
    COLUMN_CHART = 'column'                # 柱状图（竖向）
    KPI = 'kpi'                            # KPI卡片
    KEEP_ORIGINAL = 'keep'                 # 保持LLM推荐


class SmartOutputDecision:
    """智能输出决策结果"""
    def __init__(self, format_type: str, reason: str,
                 natural_language_answer: str = '',
                 override_chart_type: str = '',
                 confidence: float = 0.0):
        self.format_type = format_type
        self.reason = reason
        self.natural_language_answer = natural_language_answer
        self.override_chart_type = override_chart_type
        self.confidence = confidence

    def should_skip_chart(self) -> bool:
        return self.format_type == OutputFormat.NATURAL_LANGUAGE

    def to_dict(self) -> dict:
        return {
            'format_type': self.format_type,
            'reason': self.reason,
            'confidence': self.confidence,
            'skip_chart': self.should_skip_chart(),
            'override_chart_type': self.override_chart_type,
        }


def analyze_output_format(
    question: str,
    sql: str,
    result: Dict[str, Any],
    chart_type_hint: str = '',
    intent: str = ''
) -> SmartOutputDecision:
    """核心决策函数：根据问题语义 + SQL结构 + 实际数据，决定最优输出格式。"""
    data = result.get('data', [])
    fields = result.get('fields', [])
    row_count = len(data)

    # 分析/预测意图不应被单行结果截断为自然语言
    # 这些意图需要完整的图表+分析报告流程，即使数据只有1行
    _analysis_intents = {
        'statistical_analysis', 'comparison_analysis', 'trend_analysis',
        'analysis', 'prediction',
    }

    # ========== 规则0：数据质量边界检查 ==========
    if not fields:
        return SmartOutputDecision(
            format_type=OutputFormat.KEEP_ORIGINAL,
            reason='字段列表为空，无法判断输出格式',
            confidence=1.0
        )
    if row_count > 0 and _all_values_null(fields, data):
        return SmartOutputDecision(
            format_type=OutputFormat.TABLE,
            reason='所有数据值均为空(NULL)，使用表格展示原始结果',
            override_chart_type='table',
            confidence=0.9
        )
    # 稀疏空值检查：超过80%的数值为NULL时，图表渲染效果差，降级为表格
    if row_count > 0 and _sparse_null_ratio(fields, data) > 0.8:
        return SmartOutputDecision(
            format_type=OutputFormat.TABLE,
            reason='超过80%的数据值为空(NULL)，图表展示效果差，使用表格',
            override_chart_type='table',
            confidence=0.85
        )

    # ========== 规则1：空结果 ==========
    if row_count == 0:
        return SmartOutputDecision(
            format_type=OutputFormat.KEEP_ORIGINAL,
            reason='查询结果为空',
            confidence=1.0
        )

    # ========== 规则2：单行结果 ==========
    if row_count == 1:
        # 分析/预测意图：单行结果也需要图表+分析报告，不走自然语言快捷路径
        if intent in _analysis_intents:
            return SmartOutputDecision(
                format_type=OutputFormat.KEEP_ORIGINAL,
                reason=f'单行结果但意图为{intent}，保持图表+分析报告流程',
                confidence=0.9
            )
        
        # 如果用户明确要求了图表类型（如"用表格展示"），尊重用户意图
        if _user_requested_chart_type(question):
            return SmartOutputDecision(
                format_type=OutputFormat.KEEP_ORIGINAL,
                reason='单行结果但用户明确要求了图表类型，保持LLM推荐',
                confidence=0.8
            )
        
        # 单行 + 单数值字段 → KPI 卡片（如"总销售额: 1,234,567"）
        row = data[0]
        numeric_fields = [f for f in fields if isinstance(row.get(f), (int, float, Decimal))]
        if len(fields) == 1 and len(numeric_fields) == 1:
            return SmartOutputDecision(
                format_type=OutputFormat.KPI,
                reason='单行单数值结果，使用KPI卡片展示',
                override_chart_type='kpi',
                confidence=0.9
            )
        # 单行 + 2字段（1个标签+1个数值）→ KPI 卡片
        if len(fields) == 2 and len(numeric_fields) == 1:
            return SmartOutputDecision(
                format_type=OutputFormat.KPI,
                reason='单行双字段（标签+数值）结果，使用KPI卡片展示',
                override_chart_type='kpi',
                confidence=0.85
            )
        
        # 其他单行结果 → 自然语言回答
        answer = _build_natural_language_answer(question, fields, data[0])
        return SmartOutputDecision(
            format_type=OutputFormat.NATURAL_LANGUAGE,
            reason=f'单行结果，使用自然语言直接回答',
            natural_language_answer=answer,
            confidence=0.95
        )

    # ========== 用户意图检测（规则3-5共用）==========
    user_wants_visual = _user_requested_chart_type(question)

    # ========== 规则3：少量行（2-5行）==========
    if 2 <= row_count <= 5:
        has_time = _has_time_column(fields, data)
        has_numeric = _has_numeric_column(fields, data)
        has_categorical = _has_categorical_column(fields, data)
        if not has_time and not has_numeric and not _user_requested_chart_type(question):
            # 纯文本数据（无数值列）→ 表格展示
            return SmartOutputDecision(
                format_type=OutputFormat.TABLE,
                reason=f'{row_count}行纯文本数据，表格展示更清晰',
                override_chart_type='table',
                confidence=0.8
            )

    # ========== 规则4：时序数据检测 → 折线图 ==========
    if row_count >= 3:
        has_time = _has_time_column(fields, data)
        has_numeric = _has_numeric_column(fields, data)
        if has_time and has_numeric:
            if user_wants_visual:
                # 用户要求了图表类型，保持LLM推荐（用户指定的类型优先）
                pass
            elif chart_type_hint == 'line':
                # LLM已经推荐了折线图，不需要覆盖
                pass
            else:
                # 用户没有要求图表，但数据有时序特征
                # 智能推荐：覆盖为折线图（时序数据用折线图是合理的默认行为）
                return SmartOutputDecision(
                    format_type=OutputFormat.LINE_CHART,
                    reason='检测到时序+数值数据，折线图更适合展示趋势',
                    override_chart_type='line',
                    confidence=0.75
                )

    # ========== 规则5：分类聚合数据 → 柱状图/饼图 ==========
    if 2 <= row_count <= 20:
        has_categorical = _has_categorical_column(fields, data)
        has_numeric = _has_numeric_column(fields, data)
        if has_categorical and has_numeric and not _has_time_column(fields, data):
            if user_wants_visual:
                pass  # 用户明确要求了图表类型，保持LLM推荐
            elif chart_type_hint in ('table', ''):
                if row_count <= 8:
                    # ≤8个分类 → 饼图展示占比更直观
                    return SmartOutputDecision(
                        format_type=OutputFormat.PIE_CHART,
                        reason=f'{row_count}个分类的聚合数据，饼图展示占比更直观',
                        override_chart_type='pie',
                        confidence=0.7
                    )
                else:
                    # >8个分类 → 柱状图展示对比
                    return SmartOutputDecision(
                        format_type=OutputFormat.COLUMN_CHART,
                        reason=f'{row_count}个分类的聚合数据，柱状图展示对比更直观',
                        override_chart_type='column',
                        confidence=0.7
                    )

    # ========== 规则5b：统计分析SQL检测 → 优先图表 ==========
    if chart_type_hint == 'table' and row_count >= 2 and not user_wants_visual:
        is_agg_sql = _is_aggregation_sql(sql)
        if is_agg_sql:
            has_time = _has_time_column(fields, data)
            has_numeric = _has_numeric_column(fields, data)
            has_categorical = _has_categorical_column(fields, data)
            if has_time and has_numeric:
                return SmartOutputDecision(
                    format_type=OutputFormat.LINE_CHART,
                    reason='统计分析SQL含时间维度聚合，折线图更适合展示趋势',
                    override_chart_type='line',
                    confidence=0.75
                )
            elif has_categorical and has_numeric:
                return SmartOutputDecision(
                    format_type=OutputFormat.COLUMN_CHART,
                    reason='统计分析SQL含分类聚合，柱状图展示对比更直观',
                    override_chart_type='column',
                    confidence=0.7
                )

    # ========== 规则6：图表类型-数据兼容性校验 ==========
    if chart_type_hint and chart_type_hint != 'table':
        has_time = _has_time_column(fields, data)
        has_numeric = _has_numeric_column(fields, data)
        has_categorical = _has_categorical_column(fields, data)
        
        # 饼图不能有负值
        if chart_type_hint == 'pie' and has_numeric:
            has_negative = _has_negative_values(fields, data)
            if has_negative:
                ChatBILogUtil.info(f"[smart-output] Pie chart incompatible: data has negative values, switching to bar")
                return SmartOutputDecision(
                    format_type=OutputFormat.BAR_CHART,
                    reason='数据包含负值，饼图无法展示，已切换为柱状图',
                    override_chart_type='bar',
                    confidence=0.85
                )
            # 饼图全零值检查：所有数值列的值都为0时，饼图无法渲染
            if _all_numeric_zero(fields, data):
                ChatBILogUtil.info(f"[smart-output] Pie chart incompatible: all numeric values are zero, switching to table")
                return SmartOutputDecision(
                    format_type=OutputFormat.TABLE,
                    reason='所有数值均为0，饼图无法展示，已切换为表格',
                    override_chart_type='table',
                    confidence=0.9
                )
            # 饼图单分类检查：只有1个分类时饼图无意义
            if row_count == 1:
                ChatBILogUtil.info(f"[smart-output] Pie chart incompatible: only 1 category, switching to table")
                return SmartOutputDecision(
                    format_type=OutputFormat.TABLE,
                    reason='仅有1个分类，饼图无意义，已切换为表格',
                    override_chart_type='table',
                    confidence=0.9
                )
            # 饼图数据过多（>10个分类）不适合
            if row_count > 10:
                return SmartOutputDecision(
                    format_type=OutputFormat.BAR_CHART,
                    reason=f'数据有{row_count}行，饼图分类过多不易阅读，已切换为柱状图',
                    override_chart_type='bar',
                    confidence=0.8
                )
        
        # 折线图需要时序数据
        if chart_type_hint == 'line' and not has_time and row_count >= 2:
            if has_categorical and has_numeric:
                return SmartOutputDecision(
                    format_type=OutputFormat.COLUMN_CHART,
                    reason='无时序数据，折线图不适合，已切换为柱状图',
                    override_chart_type='column',
                    confidence=0.75
                )
        
        # 折线图数据点不足：少于2个数据点无法画线
        if chart_type_hint == 'line' and row_count < 2:
            return SmartOutputDecision(
                format_type=OutputFormat.TABLE,
                reason=f'仅有{row_count}个数据点，折线图至少需要2个点，已切换为表格',
                override_chart_type='table',
                confidence=0.9
            )

        # 面积图与折线图相同约束（area = line + fill）
        # 面积图需要时序数据且至少2个数据点，否则无法渲染
        if chart_type_hint == 'area':
            if row_count < 2:
                return SmartOutputDecision(
                    format_type=OutputFormat.TABLE,
                    reason=f'仅有{row_count}个数据点，面积图至少需要2个点，已切换为表格',
                    override_chart_type='table',
                    confidence=0.9
                )
            if not has_time and has_categorical and has_numeric:
                return SmartOutputDecision(
                    format_type=OutputFormat.COLUMN_CHART,
                    reason='无时序数据，面积图不适合，已切换为柱状图',
                    override_chart_type='column',
                    confidence=0.75
                )

        # 双轴图需要至少2个数值列，否则两个轴展示同一字段无意义
        if chart_type_hint == 'dual_axis':
            numeric_field_count = sum(
                1 for f in fields
                if any(isinstance(row.get(f), (int, float)) for row in data[:3] if isinstance(row, dict))
            )
            if numeric_field_count < 2:
                ChatBILogUtil.info(f"[smart-output] DualAxis incompatible: only {numeric_field_count} numeric field(s), need >=2")
                fallback = 'line' if has_time else 'column'
                return SmartOutputDecision(
                    format_type=OutputFormat.LINE_CHART if has_time else OutputFormat.COLUMN_CHART,
                    reason=f'仅有{numeric_field_count}个数值列，双轴图需要至少2个，已切换为{"折线图" if has_time else "柱状图"}',
                    override_chart_type=fallback,
                    confidence=0.85
                )
            if row_count < 2:
                return SmartOutputDecision(
                    format_type=OutputFormat.TABLE,
                    reason=f'仅有{row_count}个数据点，双轴图无法展示趋势，已切换为表格',
                    override_chart_type='table',
                    confidence=0.9
                )

        # 箱线图需要足够的数据点才有统计意义（至少5个）
        if chart_type_hint == 'box' and row_count < 5:
            return SmartOutputDecision(
                format_type=OutputFormat.TABLE,
                reason=f'仅有{row_count}个数据点，箱线图至少需要5个点才有统计意义，已切换为表格',
                override_chart_type='table',
                confidence=0.85
            )

        # 热力图需要2个分类维度+1个数值维度
        if chart_type_hint == 'heatmap':
            if not has_categorical or not has_numeric:
                return SmartOutputDecision(
                    format_type=OutputFormat.TABLE,
                    reason='热力图需要分类维度和数值维度，数据不满足条件，已切换为表格',
                    override_chart_type='table',
                    confidence=0.85
                )
            # 热力图至少需要2个非数值字段作为x/y维度
            # 否则颜色编码和y轴使用同一字段，热力图退化为单色条无意义
            categorical_count = sum(
                1 for f in fields
                if any(
                    isinstance(row.get(f), str) and not re.match(r'^\d', str(row.get(f, '')))
                    for row in data[:3] if isinstance(row, dict)
                )
            )
            if categorical_count < 2:
                return SmartOutputDecision(
                    format_type=OutputFormat.COLUMN_CHART,
                    reason=f'仅有{categorical_count}个分类维度，热力图需要至少2个，已切换为柱状图',
                    override_chart_type='column',
                    confidence=0.85
                )

    # ========== 默认：保持LLM推荐 ==========
    return SmartOutputDecision(
        format_type=OutputFormat.KEEP_ORIGINAL,
        reason='数据特征无明显偏好，保持LLM推荐的图表类型',
        confidence=0.5
    )


def _is_extreme_value_query(question: str, sql: str) -> bool:
    """检测是否为极值查询（最高/最低/第一/最大/最小等）"""
    q_lower = question.lower()
    sql_upper = sql.upper()

    # 问题语义：极值关键词
    extreme_keywords = [
        '最高', '最低', '最大', '最小', '最多', '最少',
        '第一', '排名第一', '排第一', '最好', '最差',
        '最贵', '最便宜', '最热', '最冷', '最快', '最慢',
        '哪天', '哪个', '哪一', '是谁', '是哪',
        'max', 'min', 'top 1', 'highest', 'lowest',
    ]
    has_extreme_question = any(kw in q_lower for kw in extreme_keywords)

    # SQL结构：ORDER BY + LIMIT 1 或 MAX/MIN聚合
    has_limit_1 = bool(re.search(r'LIMIT\s+1\b', sql_upper))
    has_top_1 = bool(re.search(r'TOP\s+1\b', sql_upper))
    has_max_min = bool(re.search(r'\b(MAX|MIN)\s*\(', sql_upper))
    has_extreme_sql = has_limit_1 or has_top_1 or has_max_min

    return has_extreme_question or has_extreme_sql


def _is_aggregation_sql(sql: str) -> bool:
    """检测SQL是否为聚合统计查询（含GROUP BY + 聚合函数）"""
    if not sql:
        return False
    sql_upper = sql.upper()
    has_group_by = bool(re.search(r'\bGROUP\s+BY\b', sql_upper))
    has_agg_func = bool(re.search(r'\b(COUNT|SUM|AVG|AVERAGE)\s*\(', sql_upper))
    return has_group_by and has_agg_func


def _translate_field_name(field: str, question: str, is_chinese: bool = True) -> str:
    """
    将英文SQL字段名翻译为显示名。

    策略：
    1. 中文用户：查常见英文→中文词典，或从问题中提取中文词
    2. 英文用户：将下划线转空格，首字母大写
    3. 兜底：保留原始字段名（下划线转空格）
    """
    # 英文用户：直接格式化字段名为可读英文
    if not is_chinese:
        return field.replace('_', ' ').title()
    # 常见SQL字段名/聚合别名 → 中文映射
    _FIELD_CN_MAP = {
        # 聚合函数别名
        'total_sales': '总销售额', 'total_sales_amount': '总销售额',
        'total_amount': '总金额', 'total_revenue': '总收入',
        'total_cost': '总成本', 'total_profit': '总利润',
        'total_quantity': '总数量', 'total_count': '总数',
        'total_order': '总订单数', 'total_orders': '总订单数',
        'total_price': '总价格',
        'avg_price': '平均价格', 'average_price': '平均价格',
        'avg_amount': '平均金额', 'average_amount': '平均金额',
        'avg_sales': '平均销售额', 'average_sales': '平均销售额',
        'avg_order_value': '平均客单价', 'average_order_value': '平均客单价',
        'avg_cost': '平均成本', 'average_cost': '平均成本',
        'max_price': '最高价格', 'min_price': '最低价格',
        'max_amount': '最大金额', 'min_amount': '最小金额',
        'max_sales': '最高销售额', 'min_sales': '最低销售额',
        'order_count': '订单数', 'customer_count': '客户数',
        'product_count': '产品数', 'user_count': '用户数',
        'row_count': '记录数', 'record_count': '记录数',
        # 常见字段
        'sales': '销售额', 'sales_amount': '销售额',
        'amount': '金额', 'price': '价格', 'unit_price': '单价',
        'quantity': '数量', 'qty': '数量',
        'revenue': '收入', 'cost': '成本', 'profit': '利润',
        'discount': '折扣', 'tax': '税额',
        'name': '名称', 'product_name': '产品名称',
        'customer_name': '客户名称', 'category': '类别',
        'category_name': '类别名称', 'brand': '品牌',
        'region': '地区', 'city': '城市', 'country': '国家',
        'province': '省份', 'address': '地址',
        'date': '日期', 'order_date': '订单日期',
        'create_time': '创建时间', 'update_time': '更新时间',
        'year': '年份', 'month': '月份', 'day': '日',
        'status': '状态', 'type': '类型',
        'description': '描述', 'remark': '备注',
        'count': '数量', 'sum': '合计',
    }

    field_lower = field.lower().strip()

    # 1. 精确匹配词典
    if field_lower in _FIELD_CN_MAP:
        return _FIELD_CN_MAP[field_lower]

    # 2. 尝试从问题中提取中文关键词作为字段显示名
    _EN_TO_CN_KEYWORDS = {
        'sales': '销售', 'amount': '金额', 'price': '价格',
        'quantity': '数量', 'revenue': '收入', 'cost': '成本',
        'profit': '利润', 'order': '订单', 'customer': '客户',
        'product': '产品', 'count': '数量', 'total': '总',
        'average': '平均', 'avg': '平均', 'max': '最大', 'min': '最小',
    }
    field_words = field_lower.replace('_', ' ').split()
    # 检查问题中是否包含对应的中文词
    for fw in field_words:
        cn = _EN_TO_CN_KEYWORDS.get(fw)
        if cn and cn in question:
            # 从问题中提取包含该中文词的连续中文片段
            match = re.search(rf'[\u4e00-\u9fff]*{re.escape(cn)}[\u4e00-\u9fff]*', question)
            if match:
                extracted = match.group()
                # 限制长度，避免提取过长的片段
                if 2 <= len(extracted) <= 8:
                    return extracted

    # 3. 兜底：下划线转空格（保留原始英文）
    return field.replace('_', ' ')


def _build_natural_language_answer(question: str, fields: list, row: dict) -> str:
    """
    将单行查询结果构建为自然语言句子，自动适配中英文。

    例如：
    中文问题："总销售额是多少？" → "总销售额 为 550100"
    英文问题："What is the total sales?" → "total sales is 550100"
    """
    # 自动检测问题语言：如果中文字符占比 > 30% 则视为中文
    cn_chars = len(re.findall(r'[\u4e00-\u9fff]', question))
    is_chinese = cn_chars > len(question) * 0.3 if question else True

    parts = []
    for field in fields:
        val = row.get(field)
        if val is not None:
            # 智能翻译字段名
            display_name = _translate_field_name(field, question, is_chinese)
            # 格式化数值
            if isinstance(val, float):
                # NaN/Inf 保护
                # float('inf') 和 float('nan') 调用 int() 会抛出 OverflowError/ValueError
                if not math.isfinite(val):
                    formatted = str(val)
                else:
                    formatted = f'{val:g}' if val == int(val) else f'{val:,.2f}'
            elif isinstance(val, Decimal):
                float_val = float(val)
                if not math.isfinite(float_val):
                    formatted = str(float_val)
                else:
                    formatted = f'{float_val:g}' if float_val == int(float_val) else f'{float_val:,.2f}'
            elif isinstance(val, (datetime, date)):
                formatted = str(val)
            else:
                formatted = str(val)
            parts.append((display_name, formatted))

    if not parts:
        return ''

    # 单字段直接返回
    if len(parts) == 1:
        name, val = parts[0]
        if is_chinese:
            return f'{name} 为 {val}'
        else:
            return f'{name} is {val}'

    # 多字段：第一个字段作为主体，后续字段作为补充说明
    q = question.strip().rstrip('？?。.')
    
    # 检测问题中是否在问"哪个/哪天/是什么" 或 "which/what/who"
    question_words_cn = ['是哪', '是什么', '是谁', '哪天', '哪个', '哪一']
    question_words_en = ['which', 'what is', 'who is', 'when']
    if any(kw in q for kw in question_words_cn) or (not is_chinese and any(kw in q.lower() for kw in question_words_en)):
        # 第一个字段是答案，后续是补充
        primary_val = parts[0][1]
        if is_chinese:
            supplements = '，'.join(f'{name} 为 {val}' for name, val in parts[1:])
            return f'{primary_val}（{supplements}）'
        else:
            supplements = ', '.join(f'{name}: {val}' for name, val in parts[1:])
            return f'{primary_val} ({supplements})'

    # 默认：逗号分隔
    if is_chinese:
        return '，'.join(f'{name} 为 {val}' for name, val in parts)
    else:
        return ', '.join(f'{name}: {val}' for name, val in parts)


def _has_time_column(fields: list, data: list) -> bool:
    """检测是否包含时间/日期列"""
    if not data:
        return False
    # 检查多行样本而非仅第一行
    # 第一行的时间列可能为 NULL，导致时序数据被误判为非时序
    samples = data[:min(3, len(data))]
    for field in fields:
        # 字段名包含时间关键词
        field_lower = field.lower()
        # 'day' 匹配过于宽泛（birthday/weekday/holiday 等误判）
        # 使用更精确的匹配：'day' 只在作为独立词或常见时间字段后缀时匹配
        time_keywords = ['date', 'time', '日期', '时间', '月份', '年份', 'month', 'year', 'quarter', '季度']
        if any(kw in field_lower for kw in time_keywords):
            return True
        # 'day' 需要更精确的匹配：独立出现或作为 _day/日 后缀
        if re.search(r'\bday\b|_day$|^day_', field_lower) or field_lower in ('day', '日'):
            return True
        # 检查多行样本的值
        for sample in samples:
            val = sample.get(field)
            if val is None:
                continue
            if isinstance(val, (datetime, date)):
                return True
            if isinstance(val, str):
                # 常见日期格式
                if re.match(r'^\d{4}[-/]\d{1,2}([-/]\d{1,2})?', val):
                    return True
                if re.match(r'^\d{4}年\d{1,2}月', val):
                    return True
                # 检测季度格式（Q1/Q2/2024Q3/2024-Q1 等）
                if re.match(r'^(?:\d{4}[-/]?)?Q[1-4]$', val, re.IGNORECASE):
                    return True
                if re.match(r'^\d{4}年?第?[一二三四1-4]季度?', val):
                    return True
    return False


def _has_numeric_column(fields: list, data: list) -> bool:
    """检测是否包含数值列"""
    if not data:
        return False
    # 检查多行样本而非仅第一行
    # 第一行的数值列可能为 NULL
    samples = data[:min(3, len(data))]
    for field in fields:
        for sample in samples:
            val = sample.get(field)
            if isinstance(val, (int, float, Decimal)):
                return True
    return False


def _has_categorical_column(fields: list, data: list) -> bool:
    """检测是否包含分类文本列"""
    if not data:
        return False
    # 检查多行样本而非仅第一行
    # 第一行的分类列可能为 NULL
    samples = data[:min(3, len(data))]
    for field in fields:
        for sample in samples:
            val = sample.get(field)
            if isinstance(val, str) and not re.match(r'^\d{4}[-/]', val) and not re.match(r'^\d{4}年', val):
                # 排除纯数字字符串（如"123"、"45.6"），避免误判为分类列
                try:
                    float(val)
                    continue  # 可以转为数字的字符串不是分类值
                except (ValueError, TypeError):
                    pass
                return True
    return False


def _user_requested_chart_type(question: str) -> bool:
    """检测用户是否在问题中明确要求了特定图表类型"""
    q = question.lower()
    chart_keywords = [
        '表格', '柱状图', '条形图', '折线图', '饼图',
        '柱形图', '曲线图', '圆饼图', '环形图',
        '用表格', '用柱状', '用折线', '用饼图', '用条形',
        '展示为', '显示为', '画一个', '生成一个',
        # 英文关键词改为更精确的短语匹配
        'line chart', 'bar chart', 'pie chart', 'column chart',
        'as a table', 'in a table', 'as table', 'show as',
        'display as', 'draw a', 'generate a chart',
    ]
    return any(kw in q for kw in chart_keywords)


def _sparse_null_ratio(fields: list, data: list) -> float:
    """计算数值列中NULL/空值的比例（稀疏数据检测）"""
    if not data or not fields:
        return 0.0
    total = 0
    null_count = 0
    for row in data:
        if not isinstance(row, dict):
            continue
        for field in fields:
            val = row.get(field)
            total += 1
            if val is None or val == '' or val == 'null' or val == 'None':
                null_count += 1
    return null_count / total if total > 0 else 0.0


def _all_values_null(fields: list, data: list) -> bool:
    """检测所有数据值是否全为NULL/空"""
    if not data or not fields:
        return False
    for row in data:
        if not isinstance(row, dict):
            continue
        for field in fields:
            val = row.get(field)
            if val is not None and val != '' and val != 'null' and val != 'None':
                return False
    return True


def _all_numeric_zero(fields: list, data: list) -> bool:
    """检测所有数值列的值是否全为0（饼图兼容性检查）"""
    if not data:
        return True
    has_any_nonzero = False
    for row in data:
        if not isinstance(row, dict):
            continue
        for field in fields:
            val = row.get(field)
            if isinstance(val, (int, float)):
                if val != 0:
                    has_any_nonzero = True
                    return False
            elif isinstance(val, Decimal):
                if float(val) != 0:
                    has_any_nonzero = True
                    return False
    return True


def _has_negative_values(fields: list, data: list) -> bool:
    """检测数值列是否包含负值（饼图兼容性检查）"""
    if not data:
        return False
    for row in data:
        if not isinstance(row, dict):
            continue
        for field in fields:
            val = row.get(field)
            if isinstance(val, (int, float)):
                if val < 0:
                    return True
            elif isinstance(val, Decimal):
                if float(val) < 0:
                    return True
    return False
