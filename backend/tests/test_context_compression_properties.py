"""Property-based tests for ContextCompressor"""
import sys
import os
import re

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

# Ensure the backend root is on sys.path so that app modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.chat.thinking.context_compressor import ContextCompressor


# ---------------------------------------------------------------------------

def _build_schema(tables):
    """Build a schema string from a list of (table_name, columns) pairs."""
    parts = []
    for name, cols in tables:
        header = f"Table {name}"
        col_lines = [f"  - {c}" for c in cols]
        parts.append(header + "\n" + "\n".join(col_lines))
    return "\n\n".join(parts)


def _build_terminologies(terms):
    return "\n".join(f"<terminology>{t}</terminology>" for t in terms)


def _build_sql_examples(examples):
    return "\n".join(f"<example>{e}</example>" for e in examples)


# Table name strategy
_table_name = st.text(
    alphabet=st.sampled_from(list('abcdefghijklmnopqrstuvwxyz_')),
    min_size=3, max_size=15,
)

# Column name strategy
_col_name = st.text(
    alphabet=st.sampled_from(list('abcdefghijklmnopqrstuvwxyz_')),
    min_size=3, max_size=15,
)

# Table: (name, [columns])
_table_entry = st.tuples(
    _table_name,
    st.lists(_col_name, min_size=1, max_size=8),
)

_schema_strategy = st.lists(
    _table_entry, min_size=1, max_size=5,
).map(_build_schema)

# Terminology entries
_term_text = st.text(
    alphabet=st.sampled_from(list(
        '销售收入利润成本产品客户订单库存数据分析统计报告'
        'abcdefghijklmnopqrstuvwxyz '
    )),
    min_size=5, max_size=60,
)

_terminologies_strategy = st.lists(
    _term_text, min_size=1, max_size=10,
).map(_build_terminologies)

# SQL example entries
_sql_text = st.text(
    alphabet=st.sampled_from(list(
        'SELECT FROM WHERE GROUP BY ORDER LIMIT JOIN ON AND OR '
        'table_name column_name value 0123456789 * = > < '
    )),
    min_size=10, max_size=120,
)

_sql_examples_strategy = st.lists(
    _sql_text, min_size=1, max_size=8,
).map(_build_sql_examples)

# Question text
_question_strategy = st.text(
    alphabet=st.sampled_from(list(
        '查询销售数据分析预测统计报告总结显示列出'
        '产品订单客户收入利润成本库存趋势增长'
    )),
    min_size=2, max_size=30,
)

# Budget strategy — small enough to force compression
_budget_strategy = st.integers(min_value=200, max_value=2000)

# XML wrapper overhead tolerance
_XML_WRAPPER_OVERHEAD = 300



class TestProperty4BudgetConstraint:
    """
    **Validates: Requirements 2.2, 10.1**

    Property 4: 上下文压缩预算不超限
    For any inputs and positive token budget, compress() output total tokens
    should not exceed the budget (with reasonable XML wrapper overhead).
    """

    @given(
        schema=_schema_strategy,
        terminologies=_terminologies_strategy,
        sql_examples=_sql_examples_strategy,
        question=_question_strategy,
        max_total_tokens=_budget_strategy,
    )
    @settings(max_examples=50, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_compressed_length_within_budget(
        self, schema, terminologies, sql_examples,
        question, max_total_tokens,
    ):
        """After compression, total output length should respect the token budget.

        Feature: chatbi-system-audit-optimization, Property 4: 上下文压缩预算不超限
        """
        # 使用与 ContextCompressor 一致的 Token 估算判断是否需要压缩
        estimated_tokens = ContextCompressor._estimate_tokens(
            terminologies + sql_examples + schema
        )
        assume(estimated_tokens > max_total_tokens)

        result = ContextCompressor.compress(
            terminologies=terminologies,
            sql_examples=sql_examples,
            schema=schema,
            question=question,
            max_total_tokens=max_total_tokens,
        )

        compressed_length = (
            len(result['terminologies']) + len(result['sql_examples'])
            + len(result['schema'])
        )

        # 使用与 ContextCompressor 一致的动态 chars_per_token 转换
        # 压缩器内部基于实际内容的中英比例计算 char_budget
        import re as _re
        _all_text = terminologies + sql_examples + schema
        _cn = len(_re.findall(r'[\u4e00-\u9fff]', _all_text))
        _en = len(_re.findall(r'[a-zA-Z0-9]', _all_text))
        _other = len(_all_text) - _cn - _en
        _total_chars = len(_all_text) or 1
        _chars_per_token = (
            (_cn / _total_chars) * (1 / 1.5) +
            (_en / _total_chars) * (1 / 0.25) +
            (_other / _total_chars) * (1 / 0.5)
        ) if _total_chars > 0 else 1.2
        _chars_per_token = max(0.8, min(3.0, _chars_per_token))
        char_budget = int(max_total_tokens * _chars_per_token)
        assert compressed_length <= char_budget + _XML_WRAPPER_OVERHEAD, (
            f"Compressed length {compressed_length} exceeds char budget "
            f"{char_budget} + overhead {_XML_WRAPPER_OVERHEAD}"
        )

    @given(
        schema=_schema_strategy,
        terminologies=_terminologies_strategy,
        sql_examples=_sql_examples_strategy,
        question=_question_strategy,
        max_total_tokens=_budget_strategy,
    )
    @settings(max_examples=50, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_compression_applied_flag(
        self, schema, terminologies, sql_examples,
        question, max_total_tokens,
    ):
        """compression_applied should be True when estimated tokens exceed budget.

        Feature: chatbi-system-audit-optimization, Property 4: 上下文压缩预算不超限
        """
        # 使用与 ContextCompressor 一致的 Token 估算
        estimated_tokens = ContextCompressor._estimate_tokens(
            terminologies + sql_examples + schema
        )
        assume(estimated_tokens > max_total_tokens)

        result = ContextCompressor.compress(
            terminologies=terminologies,
            sql_examples=sql_examples,
            schema=schema,
            question=question,
            max_total_tokens=max_total_tokens,
        )

        assert result['compression_applied'] is True

    @given(
        schema=_schema_strategy,
        terminologies=_terminologies_strategy,
        sql_examples=_sql_examples_strategy,
        question=_question_strategy,
        max_total_tokens=st.integers(min_value=50000, max_value=100000),
    )
    @settings(max_examples=50, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_no_compression_when_within_budget(
        self, schema, terminologies, sql_examples,
        question, max_total_tokens,
    ):
        """When original fits in budget, content should be unchanged.

        Feature: chatbi-system-audit-optimization, Property 4: 上下文压缩预算不超限
        """
        estimated_tokens = ContextCompressor._estimate_tokens(
            terminologies + sql_examples + schema
        )
        assume(estimated_tokens <= max_total_tokens)

        result = ContextCompressor.compress(
            terminologies=terminologies,
            sql_examples=sql_examples,
            schema=schema,
            question=question,
            max_total_tokens=max_total_tokens,
        )

        assert result['compression_applied'] is False
        assert result['terminologies'] == terminologies
        assert result['sql_examples'] == sql_examples
        assert result['schema'] == schema

    @given(
        schema=_schema_strategy,
        terminologies=_terminologies_strategy,
        sql_examples=_sql_examples_strategy,
        question=_question_strategy,
        max_total_tokens=_budget_strategy,
    )
    @settings(max_examples=50, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_result_structure(
        self, schema, terminologies, sql_examples,
        question, max_total_tokens,
    ):
        """compress() must always return all required keys with valid stats.

        Feature: chatbi-system-audit-optimization, Property 4: 上下文压缩预算不超限
        """
        result = ContextCompressor.compress(
            terminologies=terminologies,
            sql_examples=sql_examples,
            schema=schema,
            question=question,
            max_total_tokens=max_total_tokens,
        )

        required_keys = {
            'terminologies', 'sql_examples', 'schema',
            'compression_applied', 'stats',
        }
        assert required_keys.issubset(result.keys())
        assert isinstance(result['stats'], dict)
        assert 'original_length' in result['stats']
        assert 'compressed_length' in result['stats']
        assert 'compression_ratio' in result['stats']
        assert result['stats']['compressed_length'] >= 0


_known_table_names = st.sampled_from([
    '销售', '订单', '客户', '产品', '库存', '收入', '利润',
    'sales', 'orders', 'customers', 'products', 'inventory',
])


@st.composite
def _schema_with_matching_question(draw):
    """Generate a schema and a question that references at least one table name."""
    # Pick 2-5 table names, ensure at least one is a known name
    known_name = draw(_known_table_names)
    other_names = draw(st.lists(
        st.text(
            alphabet=st.sampled_from(list('abcdefghijklmnopqrstuvwxyz_')),
            min_size=4, max_size=12,
        ),
        min_size=1, max_size=4,
    ))
    all_names = [known_name] + other_names

    # Build schema
    tables = []
    for name in all_names:
        cols = draw(st.lists(_col_name, min_size=2, max_size=6))
        tables.append((name, cols))
    schema = _build_schema(tables)

    # Build question that contains the known table name
    question = f"查询{known_name}的数据"

    return schema, question, known_name


class TestProperty5SchemaRelevancePreservation:
    """
    **Validates: Requirements 10.2**

    Property 5: Schema 压缩相关性保留
    For any schema and question, compressed schema should retain tables/fields
    matching question keywords.
    """

    @given(data=_schema_with_matching_question())
    @settings(max_examples=50, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_relevant_table_preserved_after_compression(self, data):
        """Tables matching question keywords should be retained in compressed schema.

        Feature: chatbi-system-audit-optimization, Property 5: Schema 压缩相关性保留
        """
        schema, question, known_name = data

        # Use a small budget to force compression
        budget = max(100, len(schema) // 3)
        assume(len(schema) > budget)
        # Ensure budget is large enough to retain at least the known table section
        assume(budget >= len(known_name) + 50)

        compressed = ContextCompressor._compress_schema(schema, budget, question)

        # The known table name should appear in the compressed output
        assert known_name.lower() in compressed.lower(), (
            f"Relevant table '{known_name}' was lost during schema compression.\n"
            f"Question: {question}\n"
            f"Compressed schema: {compressed[:200]}..."
        )

    @given(data=_schema_with_matching_question())
    @settings(max_examples=50, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_compressed_schema_not_longer_than_original(self, data):
        """Compressed schema should not be longer than the original.

        Feature: chatbi-system-audit-optimization, Property 5: Schema 压缩相关性保留
        """
        schema, question, _ = data

        budget = max(100, len(schema) // 3)
        assume(len(schema) > budget)

        compressed = ContextCompressor._compress_schema(schema, budget, question)

        assert len(compressed) <= len(schema), (
            f"Compressed schema ({len(compressed)}) is longer than "
            f"original ({len(schema)})"
        )

    @given(data=_schema_with_matching_question())
    @settings(max_examples=50, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_validate_schema_preservation_recovers_missing_tables(self, data):
        """_validate_schema_preservation should recover relevant tables if lost.

        When the compressed schema has enough room for recovery (10% of budget),
        relevant tables that were lost should be recovered as summaries.

        Feature: chatbi-system-audit-optimization, Property 5: Schema 压缩相关性保留
        """
        schema, question, known_name = data

        # Use a budget that forces compression but leaves enough room for recovery
        budget = max(150, len(schema) // 2)
        assume(len(schema) > budget)

        compressed = ContextCompressor._compress_schema(schema, budget, question)
        # Only test recovery when compressed schema is non-empty
        assume(len(compressed) > 0)

        validated = ContextCompressor._validate_schema_preservation(
            original_schema=schema,
            compressed_schema=compressed,
            question=question,
            budget=budget,
        )

        # After validation, the known table name should be present
        # (either already in compressed or recovered by validation)
        assert known_name.lower() in validated.lower(), (
            f"Relevant table '{known_name}' not recovered by validation.\n"
            f"Question: {question}\n"
            f"Budget: {budget}, Schema length: {len(schema)}\n"
            f"Validated schema: {validated[:200]}..."
        )


_term_word_dict = st.fixed_dictionaries(
    {'word': st.text(
        alphabet=st.sampled_from(list(
            '销售收入利润成本产品客户订单库存数据分析统计报告'
            'abcdefghijklmnopqrstuvwxyz'
        )),
        min_size=1, max_size=20,
    )},
    optional={'definition': st.text(min_size=0, max_size=50)},
)

# Strategy: term dicts with 'term' key (alternative format)
_term_term_dict = st.fixed_dictionaries(
    {'term': st.text(
        alphabet=st.sampled_from(list(
            '销售收入利润成本产品客户订单库存数据分析统计报告'
            'abcdefghijklmnopqrstuvwxyz'
        )),
        min_size=1, max_size=20,
    )},
    optional={'definition': st.text(min_size=0, max_size=50)},
)

# Mix both formats and allow duplicates in the input
_terms_with_duplicates = st.lists(
    st.one_of(_term_word_dict, _term_term_dict),
    min_size=0, max_size=30,
)

# Strategy: example dicts with 'question' key
_example_dict = st.fixed_dictionaries(
    {'question': st.text(
        alphabet=st.sampled_from(list(
            '查询销售数据分析预测统计报告总结显示列出'
            '产品订单客户收入利润成本库存趋势增长'
            'abcdefghijklmnopqrstuvwxyz '
        )),
        min_size=1, max_size=40,
    )},
    optional={'sql': st.text(min_size=0, max_size=100)},
)

_examples_with_duplicates = st.lists(
    _example_dict, min_size=0, max_size=30,
)


class TestProperty6DeduplicationIdempotency:
    """
    **Validates: Requirements 10.4**

    Property 6: 术语和SQL示例去重幂等性
    For any term/example list, dedup output length ≤ input length,
    no duplicates, and re-dedup gives same result (idempotency).
    """

    # --- _deduplicate_terms ---

    @given(terms=_terms_with_duplicates)
    @settings(max_examples=50, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_terms_dedup_idempotent(self, terms):
        """Applying _deduplicate_terms twice yields the same result as once.

        Feature: chatbi-system-audit-optimization, Property 6: 术语和SQL示例去重幂等性
        """
        once = ContextCompressor._deduplicate_terms(terms)
        twice = ContextCompressor._deduplicate_terms(once)
        assert once == twice, (
            f"Idempotency violated: first pass {len(once)} terms, "
            f"second pass {len(twice)} terms"
        )

    @given(terms=_terms_with_duplicates)
    @settings(max_examples=50, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_terms_dedup_no_duplicates(self, terms):
        """After deduplication, no two terms share the same word/term key.

        Feature: chatbi-system-audit-optimization, Property 6: 术语和SQL示例去重幂等性
        """
        result = ContextCompressor._deduplicate_terms(terms)
        seen = set()
        for term in result:
            word = term.get('word', '') or term.get('term', '')
            assert word not in seen, f"Duplicate word '{word}' after dedup"
            seen.add(word)

    @given(terms=_terms_with_duplicates)
    @settings(max_examples=50, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_terms_dedup_length_not_exceeds_input(self, terms):
        """Dedup output length should be ≤ input length.

        Feature: chatbi-system-audit-optimization, Property 6: 术语和SQL示例去重幂等性
        """
        result = ContextCompressor._deduplicate_terms(terms)
        assert len(result) <= len(terms)

    # --- _deduplicate_examples ---

    @given(examples=_examples_with_duplicates)
    @settings(max_examples=50, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_examples_dedup_idempotent(self, examples):
        """Applying _deduplicate_examples twice yields the same result as once.

        Feature: chatbi-system-audit-optimization, Property 6: 术语和SQL示例去重幂等性
        """
        once = ContextCompressor._deduplicate_examples(examples)
        twice = ContextCompressor._deduplicate_examples(once)
        assert once == twice, (
            f"Idempotency violated: first pass {len(once)} examples, "
            f"second pass {len(twice)} examples"
        )

    @given(examples=_examples_with_duplicates)
    @settings(max_examples=50, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_examples_dedup_no_duplicates(self, examples):
        """After deduplication, no two examples share the same question.

        Feature: chatbi-system-audit-optimization, Property 6: 术语和SQL示例去重幂等性
        """
        result = ContextCompressor._deduplicate_examples(examples)
        seen = set()
        for example in result:
            question = example.get('question', '')
            assert question not in seen, f"Duplicate question '{question}' after dedup"
            seen.add(question)

    @given(examples=_examples_with_duplicates)
    @settings(max_examples=50, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_examples_dedup_length_not_exceeds_input(self, examples):
        """Dedup output length should be ≤ input length.

        Feature: chatbi-system-audit-optimization, Property 6: 术语和SQL示例去重幂等性
        """
        result = ContextCompressor._deduplicate_examples(examples)
        assert len(result) <= len(examples)
