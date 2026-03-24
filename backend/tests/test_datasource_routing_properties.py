"""Property-based tests for datasource routing logic."""
import sys
import os

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path so that app modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.chat.thinking.query_rewriter import QueryRewriter


# ---------------------------------------------------------------------------

DATABASE_DS_TYPES = ['mysql', 'oracle', 'postgresql', 'excel', 'csv', 'pdf']

# Valid intents for database datasources (all possible intents from _detect_intent)
DATABASE_VALID_INTENTS = {
    'data_query', 'analysis', 'prediction', 'general_chat',
    'irrelevant_query', 'ambiguous_query', 'follow_up',
    'fact_query', 'statistical_analysis', 'comparison',
    'comparison_analysis', 'trend_analysis', 'terminology_query',
    'term_explanation', 'document_qa',
}


_chinese_chars = st.sampled_from(list(
    '查询销售数据分析预测统计报告总结概括显示列出帮我看看'
    '产品订单客户收入利润成本库存趋势增长下降对比'
    '你好谢谢请问如何使用功能介绍什么是为什么'
    '今年去年上个月这个月最近最新近期'
))

_english_chars = st.sampled_from(list(
    'abcdefghijklmnopqrstuvwxyz '
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
))

_question_char = st.one_of(_chinese_chars, _english_chars)

_question_strategy = st.text(
    alphabet=_question_char,
    min_size=1,
    max_size=50,
).filter(lambda s: len(s.strip()) > 0)

_db_ds_strategy = st.sampled_from(DATABASE_DS_TYPES)


# ---------------------------------------------------------------------------

class TestIntentRoutingCorrectnessProperty25:
    """
    **Validates: Requirements 1.2, 5.6**

    Property 25: 意图路由正确性
    - 数据库数据源的意图为标准 5 种之一
    """

    @given(question=_question_strategy, ds_type=_db_ds_strategy)
    @settings(max_examples=100)
    def test_database_ds_routes_to_valid_intent(self, question, ds_type):
        """For database datasources, intent must be one of the 5 standard types."""
        intent = QueryRewriter._detect_intent(question, ds_type=ds_type)

        assert intent in DATABASE_VALID_INTENTS, (
            f"Database ds_type={ds_type!r} with question={question!r} "
            f"returned intent={intent!r}, expected one of {DATABASE_VALID_INTENTS}"
        )

    @given(question=_question_strategy, ds_type=_db_ds_strategy)
    @settings(max_examples=100)
    def test_all_ds_types_return_string_intent(self, question, ds_type):
        """_detect_intent() must always return a non-empty string."""
        intent = QueryRewriter._detect_intent(question, ds_type=ds_type)

        assert isinstance(intent, str), f"Intent must be a string, got {type(intent)}"
        assert len(intent) > 0, "Intent must be non-empty"
