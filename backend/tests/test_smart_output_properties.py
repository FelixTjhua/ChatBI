"""Property-based tests for SmartOutput decision engine"""
import sys
import os

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path so that app modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.chat.task.smart_output import (
    analyze_output_format,
    OutputFormat,
    SmartOutputDecision,
    _has_time_column,
    _has_numeric_column,
    _has_categorical_column,
    _build_natural_language_answer,
)


PLAIN_QUESTIONS = [
    "总销售额是多少",
    "客单价最高的日期是哪天",
    "上个月的收入",
    "哪个产品卖得最好",
    "今年的利润",
    "查询所有订单",
    "统计各部门人数",
]

# Chart-requesting questions (should be excluded from certain property checks)
CHART_QUESTIONS = [
    "用表格展示销售数据",
    "画一个折线图",
    "用柱状图展示",
    "生成一个饼图",
]

plain_question_st = st.sampled_from(PLAIN_QUESTIONS)
any_question_st = st.sampled_from(PLAIN_QUESTIONS + CHART_QUESTIONS)


# Field name strategies
numeric_field_names = st.sampled_from(["销售额", "数量", "金额", "利润", "价格", "count", "total"])
categorical_field_names = st.sampled_from(["产品", "部门", "类别", "品牌", "城市", "name", "category"])
time_field_names = st.sampled_from(["日期", "date", "时间", "月份", "year"])

# Value strategies
numeric_values = st.one_of(
    st.integers(min_value=0, max_value=1000000),
    st.floats(min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False),
)
categorical_values = st.sampled_from(["电子产品", "服装", "食品", "家居", "运动", "图书", "玩具", "办公"])
time_values = st.sampled_from([
    "2024-01-01", "2024-02-15", "2024-03-20", "2024-04-10",
    "2024-05-05", "2024-06-18", "2024-07-22", "2024-08-30",
    "2024-09-12", "2024-10-25", "2024-11-08", "2024-12-31",
])


def build_result(fields: list, rows: list) -> dict:
    """Build a SQL result dict from fields and row data."""
    return {"fields": fields, "data": rows}


def build_empty_result(fields: list = None) -> dict:
    """Build an empty SQL result."""
    return {"fields": fields or [], "data": []}


def build_single_row_numeric(field_name: str, value) -> dict:
    """Build a single-row result with one numeric field."""
    return {"fields": [field_name], "data": [{field_name: value}]}


def build_time_numeric_rows(time_field: str, num_field: str,
                            time_vals: list, num_vals: list) -> dict:
    """Build rows with time + numeric columns."""
    fields = [time_field, num_field]
    data = [{time_field: tv, num_field: nv} for tv, nv in zip(time_vals, num_vals)]
    return {"fields": fields, "data": data}


def build_categorical_numeric_rows(cat_field: str, num_field: str,
                                   cat_vals: list, num_vals: list) -> dict:
    """Build rows with categorical + numeric columns (no time)."""
    fields = [cat_field, num_field]
    data = [{cat_field: cv, num_field: nv} for cv, nv in zip(cat_vals, num_vals)]
    return {"fields": fields, "data": data}


# ---------------------------------------------------------------------------

class TestSmartOutputDecisionDeterminismProperty10:
    """
    Feature: chatbi-system-audit-optimization, Property 10: 智能输出决策确定性

    For any SQL result (fields + data), analyze_output_format() returns a
    deterministic result satisfying the documented decision rules.
    """

    # --- Sub-property 10a: Determinism ---
    @settings(max_examples=100)
    @given(
        question=plain_question_st,
        num_field=numeric_field_names,
        value=numeric_values,
    )
    def test_deterministic_same_input_same_output(self, question, num_field, value):
        """
        Calling analyze_output_format twice with identical inputs must produce
        the same format_type.

        **Validates: Requirements 1.5, 2.6**
        """
        result = build_single_row_numeric(num_field, value)
        sql = f"SELECT {num_field} FROM t"

        decision1 = analyze_output_format(question, sql, result)
        decision2 = analyze_output_format(question, sql, result)

        assert decision1.format_type == decision2.format_type
        assert decision1.reason == decision2.reason

    # --- Sub-property 10b: Empty result → keep original ---
    @settings(max_examples=100)
    @given(question=any_question_st)
    def test_empty_result_returns_keep_original(self, question):
        """
        Empty data must always produce KEEP_ORIGINAL.

        **Validates: Requirements 1.5, 2.6**
        """
        result = build_empty_result(["col1"])
        decision = analyze_output_format(question, "SELECT 1", result)

        assert decision.format_type == OutputFormat.KEEP_ORIGINAL

    @settings(max_examples=100)
    @given(question=any_question_st)
    def test_empty_result_no_fields_returns_keep_original(self, question):
        """
        Completely empty result (no fields, no data) → KEEP_ORIGINAL.

        **Validates: Requirements 1.5, 2.6**
        """
        result = {"fields": [], "data": []}
        decision = analyze_output_format(question, "SELECT 1", result)

        assert decision.format_type == OutputFormat.KEEP_ORIGINAL

    # --- Sub-property 10c: Single row → natural language or keep original ---
    @settings(max_examples=100)
    @given(
        question=plain_question_st,
        num_field=numeric_field_names,
        value=numeric_values,
    )
    def test_single_row_plain_question_returns_kpi_or_natural_language(self, question, num_field, value):
        """
        Single row with a plain question (no chart request):
        - 单字段数值 → KPI 卡片
        - 双字段（1标签+1数值）→ KPI 卡片
        - 其他 → NATURAL_LANGUAGE

        **Validates: Requirements 1.5, 2.6**
        """
        result = build_single_row_numeric(num_field, value)
        decision = analyze_output_format(question, "SELECT x FROM t", result)

        # 单行单数值字段 → KPI；单行双字段（1标签+1数值）→ KPI
        assert decision.format_type in (OutputFormat.KPI, OutputFormat.NATURAL_LANGUAGE)

    @settings(max_examples=100)
    @given(
        question=st.sampled_from(CHART_QUESTIONS),
        num_field=numeric_field_names,
        value=numeric_values,
    )
    def test_single_row_chart_question_returns_keep_original(self, question, num_field, value):
        """
        Single row with a chart-requesting question → KEEP_ORIGINAL
        (respects user intent).

        **Validates: Requirements 1.5, 2.6**
        """
        result = build_single_row_numeric(num_field, value)
        decision = analyze_output_format(question, "SELECT x FROM t", result)

        assert decision.format_type == OutputFormat.KEEP_ORIGINAL

    # --- Sub-property 10d: Few rows (2-5) categorical + numeric → chart (pie/column) ---
    @settings(max_examples=100)
    @given(
        question=plain_question_st,
        cat_field=categorical_field_names,
        num_field=numeric_field_names,
        row_count=st.integers(min_value=2, max_value=5),
    )
    def test_few_rows_no_time_returns_chart(self, question, cat_field, num_field, row_count):
        """
        2-5 rows with categorical + numeric data (no time column) → PIE or COLUMN chart.
        少量行的分类+数值数据应优先生成图表而非表格。

        **Validates: Requirements 1.5, 2.6**
        """
        cat_vals = categorical_values.filter(lambda _: True)
        num_vals = numeric_values.filter(lambda _: True)

        # Build deterministic rows
        cats = ["电子产品", "服装", "食品", "家居", "运动"][:row_count]
        nums = [100 * (i + 1) for i in range(row_count)]

        result = build_categorical_numeric_rows(cat_field, num_field, cats, nums)
        decision = analyze_output_format(question, "SELECT x FROM t", result)

        # 分类+数值数据应优先图表展示（≤8个分类→饼图，>8→柱状图）
        assert decision.format_type in (OutputFormat.PIE_CHART, OutputFormat.COLUMN_CHART)

    # --- Sub-property 10e: Time + numeric (≥3 rows) → line chart ---
    @settings(max_examples=100)
    @given(
        question=plain_question_st,
        time_field=time_field_names,
        num_field=numeric_field_names,
        row_count=st.integers(min_value=3, max_value=12),
    )
    def test_time_numeric_data_returns_line_chart(self, question, time_field, num_field, row_count):
        """
        ≥3 rows with time + numeric columns, plain question, no line hint
        → LINE_CHART.

        **Validates: Requirements 1.5, 2.6**
        """
        all_times = [
            "2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01",
            "2024-05-01", "2024-06-01", "2024-07-01", "2024-08-01",
            "2024-09-01", "2024-10-01", "2024-11-01", "2024-12-01",
        ]
        times = all_times[:row_count]
        nums = [100 * (i + 1) for i in range(row_count)]

        result = build_time_numeric_rows(time_field, num_field, times, nums)
        # No chart_type_hint, no user chart request → should get LINE_CHART
        decision = analyze_output_format(question, "SELECT x FROM t", result, chart_type_hint='')

        assert decision.format_type == OutputFormat.LINE_CHART

    # --- Sub-property 10f: Decision always returns SmartOutputDecision ---
    @settings(max_examples=100)
    @given(
        question=any_question_st,
        row_count=st.integers(min_value=0, max_value=20),
        num_field=numeric_field_names,
    )
    def test_always_returns_smart_output_decision(self, question, row_count, num_field):
        """
        For any input, the function always returns a SmartOutputDecision
        with valid format_type and non-empty reason.

        **Validates: Requirements 1.5, 2.6**
        """
        data = [{num_field: i * 10} for i in range(row_count)]
        result = {"fields": [num_field], "data": data}

        decision = analyze_output_format(question, "SELECT x FROM t", result)

        assert isinstance(decision, SmartOutputDecision)
        assert decision.format_type in (
            OutputFormat.NATURAL_LANGUAGE,
            OutputFormat.TABLE,
            OutputFormat.LINE_CHART,
            OutputFormat.BAR_CHART,
            OutputFormat.PIE_CHART,
            OutputFormat.COLUMN_CHART,
            OutputFormat.KPI,
            OutputFormat.KEEP_ORIGINAL,
        )
        assert len(decision.reason) > 0
        assert 0.0 <= decision.confidence <= 1.0

    # --- Sub-property 10g: to_dict structure ---
    @settings(max_examples=100)
    @given(
        question=plain_question_st,
        num_field=numeric_field_names,
        value=numeric_values,
    )
    def test_to_dict_has_required_keys(self, question, num_field, value):
        """
        SmartOutputDecision.to_dict() must contain format_type, reason,
        confidence, skip_chart, and override_chart_type.

        **Validates: Requirements 1.5, 2.6**
        """
        result = build_single_row_numeric(num_field, value)
        decision = analyze_output_format(question, "SELECT x FROM t", result)
        d = decision.to_dict()

        assert "format_type" in d
        assert "reason" in d
        assert "confidence" in d
        assert "skip_chart" in d
        assert "override_chart_type" in d
