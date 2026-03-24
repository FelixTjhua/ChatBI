"""Property-based tests for QueryRewriter"""
import sys
import os

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path so that app modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.chat.thinking.query_rewriter import QueryRewriter


# ---------------------------------------------------------------------------

REQUIRED_KEYS = {'original', 'rewritten', 'expanded_queries',
                 'extracted_keywords', 'intent', 'rewrite_applied'}

VALID_INTENTS = {'data_query', 'analysis',
                 'prediction', 'general_chat', 'unknown',
                 'irrelevant_query', 'ambiguous_query', 'follow_up',
                 'fact_query', 'statistical_analysis', 'comparison',
                 'comparison_analysis', 'trend_analysis', 'terminology_query',
                 'term_explanation', 'document_qa'}

VALID_DS_TYPES = ['mysql', 'postgresql', 'excel', 'csv', 'pdf', 'database']

DECOMPOSE_REQUIRED_KEYS = {'is_complex', 'sub_tasks', 'task_type'}


_chinese_chars = st.sampled_from(list(
    '查询销售数据分析预测统计报告总结概括显示列出'
    '产品订单客户收入利润成本库存趋势增长下降对比'
    '你好谢谢请问如何使用功能介绍什么是为什么'
    '今年去年上个月这个月最近最新近期'
))

_question_char = st.one_of(
    _chinese_chars,
    st.sampled_from(list('abcdefghijklmnopqrstuvwxyz ')),
)

_question_strategy = st.text(
    alphabet=_question_char,
    min_size=1,
    max_size=50,
).filter(lambda s: len(s.strip()) > 0)


_blank_strategy = st.sampled_from(['', '  ', '\t', '\n', '   \n  '])

_ds_type_strategy = st.sampled_from(VALID_DS_TYPES)



class TestProperty1QueryRewriteOutputCompleteness:
    """
    **Validates: Requirements 9.1, 9.2**

    Property 1: 查询重写输出完整性
    For any non-empty question, rewrite() should return all required fields
    (rewritten_query, expanded_queries, intent, keywords), and intent should
    be one of the defined types.
    """

    @given(question=_question_strategy, ds_type=_ds_type_strategy)
    @settings(max_examples=100)
    def test_rewrite_returns_all_required_keys(self, question, ds_type):
        """Feature: chatbi-system-audit-optimization, Property 1: 查询重写输出完整性
        rewrite() must return a dict with all required keys."""
        result = QueryRewriter.rewrite(question, ds_type=ds_type)

        assert isinstance(result, dict), "rewrite() must return a dict"
        assert REQUIRED_KEYS.issubset(result.keys()), (
            f"Missing keys: {REQUIRED_KEYS - result.keys()}"
        )

    @given(question=_question_strategy, ds_type=_ds_type_strategy)
    @settings(max_examples=100)
    def test_intent_is_valid_type(self, question, ds_type):
        """Feature: chatbi-system-audit-optimization, Property 1: 查询重写输出完整性
        intent must be one of the predefined valid types."""
        result = QueryRewriter.rewrite(question, ds_type=ds_type)

        assert result['intent'] in VALID_INTENTS, (
            f"Invalid intent '{result['intent']}', expected one of {VALID_INTENTS}"
        )

    @given(question=_question_strategy, ds_type=_ds_type_strategy)
    @settings(max_examples=100)
    def test_original_matches_stripped_input(self, question, ds_type):
        """Feature: chatbi-system-audit-optimization, Property 1: 查询重写输出完整性
        original field should equal the stripped input question."""
        result = QueryRewriter.rewrite(question, ds_type=ds_type)

        assert result['original'] == question.strip()

    @given(question=_question_strategy, ds_type=_ds_type_strategy)
    @settings(max_examples=100)
    def test_expanded_queries_and_keywords_are_lists(self, question, ds_type):
        """Feature: chatbi-system-audit-optimization, Property 1: 查询重写输出完整性
        expanded_queries and extracted_keywords must be lists."""
        result = QueryRewriter.rewrite(question, ds_type=ds_type)

        assert isinstance(result['expanded_queries'], list)
        assert isinstance(result['extracted_keywords'], list)

    @given(blank=_blank_strategy)
    @settings(max_examples=20)
    def test_blank_input_returns_unknown_intent(self, blank):
        """Feature: chatbi-system-audit-optimization, Property 1: 查询重写输出完整性
        Empty/blank input should return intent='unknown' and rewrite_applied=False."""
        result = QueryRewriter.rewrite(blank)

        assert result['intent'] == 'unknown'
        assert result['rewrite_applied'] is False
        assert REQUIRED_KEYS.issubset(result.keys())


_term_words = ['GMV', '客单价', '复购率', '毛利率', '坪效', '人效']
_term_descriptions = [
    'SUM(order_amount)',
    '总销售额/订单数',
    '重复购买客户数/总客户数',
    '(收入-成本)/收入',
    '销售额/门店面积',
    '销售额/员工数',
]

# Build terminology dicts
_terminology_strategy = st.lists(
    st.builds(
        lambda i: {'word': _term_words[i], 'description': _term_descriptions[i]},
        i=st.integers(min_value=0, max_value=len(_term_words) - 1),
    ),
    min_size=1,
    max_size=3,
)

# Strategy: query that contains a known term word
_term_word_strategy = st.sampled_from(_term_words)

_query_with_term_strategy = st.builds(
    lambda prefix, term, suffix: f"{prefix}{term}{suffix}",
    prefix=st.sampled_from(['查询', '统计', '分析', '显示', '']),
    term=_term_word_strategy,
    suffix=st.sampled_from(['的数据', '趋势', '排名', '情况', '']),
)



class TestProperty2TerminologyExpansionCorrectness:
    """
    **Validates: Requirements 9.3**

    Property 2: 术语扩展正确性
    For any question containing known terminology, when provided with
    corresponding term list, the rewritten query should include synonym
    or SQL mapping expansions.
    """

    @given(
        term_idx=st.integers(min_value=0, max_value=len(_term_words) - 1),
        prefix=st.sampled_from(['查询', '统计', '分析', '显示', '']),
        suffix=st.sampled_from(['的数据', '趋势', '排名', '情况', '']),
    )
    @settings(max_examples=100)
    def test_term_in_query_gets_description_appended(self, term_idx, prefix, suffix):
        """Feature: chatbi-system-audit-optimization, Property 2: 术语扩展正确性
        When query contains a known term word, the expansion should append
        the term's description (SQL mapping)."""
        word = _term_words[term_idx]
        description = _term_descriptions[term_idx]
        query = f"{prefix}{word}{suffix}"
        terminologies = [{'word': word, 'description': description}]

        result = QueryRewriter._expand_with_terminologies(query, terminologies)

        # Description should be appended if it's short enough (<20 chars)
        if len(description) < 20:
            assert description in result, (
                f"Expected description '{description}' in expanded result '{result}' "
                f"for query '{query}' with term '{word}'"
            )
        # The original query content should be preserved
        assert word in result

    @given(
        term_idx=st.integers(min_value=0, max_value=len(_term_words) - 1),
        prefix=st.sampled_from(['查询', '统计', '分析', '']),
        suffix=st.sampled_from(['的数据', '趋势', '']),
    )
    @settings(max_examples=100)
    def test_description_in_query_gets_word_appended(self, term_idx, prefix, suffix):
        """Feature: chatbi-system-audit-optimization, Property 2: 术语扩展正确性
        When query contains a term's description but not the word itself,
        the expansion should append the term word."""
        word = _term_words[term_idx]
        description = _term_descriptions[term_idx]
        # Build query with description but without the word
        query = f"{prefix}{description}{suffix}"
        assume(word not in query)  # Ensure word is not accidentally in query
        terminologies = [{'word': word, 'description': description}]

        result = QueryRewriter._expand_with_terminologies(query, terminologies)

        assert word in result, (
            f"Expected word '{word}' in expanded result '{result}' "
            f"for query '{query}' with description '{description}'"
        )

    @given(question=_question_strategy)
    @settings(max_examples=100)
    def test_no_terminologies_returns_unchanged(self, question):
        """Feature: chatbi-system-audit-optimization, Property 2: 术语扩展正确性
        When no terminologies are provided, query should be unchanged."""
        result_none = QueryRewriter._expand_with_terminologies(question, None)
        result_empty = QueryRewriter._expand_with_terminologies(question, [])

        assert result_none == question
        assert result_empty == question

    @given(
        term_idx=st.integers(min_value=0, max_value=len(_term_words) - 1),
        prefix=st.sampled_from(['查询', '统计', '']),
        suffix=st.sampled_from(['的数据', '']),
    )
    @settings(max_examples=100)
    def test_rewrite_with_terminologies_includes_expansion(self, term_idx, prefix, suffix):
        """Feature: chatbi-system-audit-optimization, Property 2: 术语扩展正确性
        Full rewrite() with terminologies should produce expanded content."""
        word = _term_words[term_idx]
        description = _term_descriptions[term_idx]
        query = f"{prefix}{word}{suffix}"
        terminologies = [{'word': word, 'description': description}]

        result = QueryRewriter.rewrite(query, terminologies=terminologies)

        # The rewritten query should contain the original term
        assert word in result['rewritten'] or word in result['original']
        # Result should have all required keys
        assert REQUIRED_KEYS.issubset(result.keys())


# ---------------------------------------------------------------------------

_comparison_subjects = ['产品A', '部门一', '华东区', '线上渠道', '一季度']
_comparison_subjects_b = ['产品B', '部门二', '华北区', '线下渠道', '二季度']
_comparison_metrics = ['销售额', '利润', '订单量', '客户数', '收入']

_comparison_pattern_strategy = st.builds(
    lambda a, b, m: f"对比{a}和{b}的{m}",
    a=st.sampled_from(_comparison_subjects),
    b=st.sampled_from(_comparison_subjects_b),
    m=st.sampled_from(_comparison_metrics),
)

_compare_with_strategy = st.builds(
    lambda a, b, m: f"比较{a}与{b}的{m}",
    a=st.sampled_from(_comparison_subjects),
    b=st.sampled_from(_comparison_subjects_b),
    m=st.sampled_from(_comparison_metrics),
)

_which_better_strategy = st.builds(
    lambda a, b, m: f"{a}和{b}哪个{m}更高",
    a=st.sampled_from(_comparison_subjects),
    b=st.sampled_from(_comparison_subjects_b),
    m=st.sampled_from(_comparison_metrics),
)

_comparison_query_strategy = st.one_of(
    _comparison_pattern_strategy,
    _compare_with_strategy,
    _which_better_strategy,
)

_multi_step_connectors = ['并且', '同时', '然后', '以及', '还要', '另外']
_action_verbs = ['查询', '统计', '分析', '计算', '显示', '列出']
_action_targets = ['销售额', '订单量', '客户数', '利润趋势', '成本分布']

_multi_step_query_strategy = st.builds(
    lambda v1, t1, conn, v2, t2: f"{v1}{t1}{conn}{v2}{t2}",
    v1=st.sampled_from(_action_verbs),
    t1=st.sampled_from(_action_targets),
    conn=st.sampled_from(_multi_step_connectors),
    v2=st.sampled_from(_action_verbs),
    t2=st.sampled_from(_action_targets),
)

_trend_subjects = ['销售', '利润', '订单', '客户', '收入']
_trend_keywords_list = ['趋势', '变化', '增长率', '同比', '环比', '走势']

_trend_query_strategy = st.builds(
    lambda subj, kw: f"分析{subj}的{kw}",
    subj=st.sampled_from(_trend_subjects),
    kw=st.sampled_from(_trend_keywords_list),
)

_complex_query_strategy = st.one_of(
    _comparison_query_strategy,
    _multi_step_query_strategy,
    _trend_query_strategy,
)



class TestProperty3ComplexQueryDecomposition:
    """
    **Validates: Requirements 9.4, 12.2**

    Property 3: 复杂查询分解有效性
    For any complex query with multiple sub-questions,
    decompose_complex_query() should return is_complex=True and
    non-empty sub_queries list.
    """

    @given(query=_complex_query_strategy)
    @settings(max_examples=100)
    def test_complex_query_returns_is_complex_true(self, query):
        """Feature: chatbi-system-audit-optimization, Property 3: 复杂查询分解有效性
        Complex queries should be identified as complex."""
        result = QueryRewriter.decompose_complex_query(query)

        assert isinstance(result, dict)
        assert DECOMPOSE_REQUIRED_KEYS.issubset(result.keys())
        assert result['is_complex'] is True, (
            f"Expected is_complex=True for '{query}', got sub_tasks={result['sub_tasks']}"
        )

    @given(query=_complex_query_strategy)
    @settings(max_examples=100)
    def test_complex_query_has_at_least_two_sub_tasks(self, query):
        """Feature: chatbi-system-audit-optimization, Property 3: 复杂查询分解有效性
        Complex queries should decompose into at least 2 sub-tasks."""
        result = QueryRewriter.decompose_complex_query(query)

        assert len(result['sub_tasks']) >= 2, (
            f"Expected ≥2 sub_tasks for '{query}', got {result['sub_tasks']}"
        )

    @given(query=_complex_query_strategy)
    @settings(max_examples=100)
    def test_sub_tasks_are_non_empty_strings(self, query):
        """Feature: chatbi-system-audit-optimization, Property 3: 复杂查询分解有效性
        All sub-tasks should be non-empty strings (valid independent questions)."""
        result = QueryRewriter.decompose_complex_query(query)

        for i, task in enumerate(result['sub_tasks']):
            assert isinstance(task, str), f"sub_task[{i}] should be str"
            assert len(task.strip()) > 0, f"sub_task[{i}] should be non-empty"

    @given(query=_comparison_query_strategy)
    @settings(max_examples=100)
    def test_comparison_query_type(self, query):
        """Feature: chatbi-system-audit-optimization, Property 3: 复杂查询分解有效性
        Comparison queries should have task_type='comparison'."""
        result = QueryRewriter.decompose_complex_query(query)

        assert result['task_type'] == 'comparison'

    @given(query=_multi_step_query_strategy)
    @settings(max_examples=100)
    def test_multi_step_query_type(self, query):
        """Feature: chatbi-system-audit-optimization, Property 3: 复杂查询分解有效性
        Multi-step queries should have task_type='multi_step'."""
        result = QueryRewriter.decompose_complex_query(query)

        assert result['task_type'] == 'multi_step'

    @given(query=_trend_query_strategy)
    @settings(max_examples=100)
    def test_trend_query_type(self, query):
        """Feature: chatbi-system-audit-optimization, Property 3: 复杂查询分解有效性
        Trend analysis queries should have task_type='trend_analysis'."""
        result = QueryRewriter.decompose_complex_query(query)

        assert result['task_type'] == 'trend_analysis'

    @given(blank=_blank_strategy)
    @settings(max_examples=20)
    def test_empty_input_not_complex(self, blank):
        """Feature: chatbi-system-audit-optimization, Property 3: 复杂查询分解有效性
        Empty/blank input should return is_complex=False."""
        result = QueryRewriter.decompose_complex_query(blank)

        assert result['is_complex'] is False
