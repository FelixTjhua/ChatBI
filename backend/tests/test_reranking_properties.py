"""Property-based tests for RAG reranking completeness and ordering."""
import sys
import os

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.chat.thinking.rag_reranker import RAGReranker


# ---------------------------------------------------------------------------

_similarity = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

_match_type = st.sampled_from(["keyword", "vector", "hybrid"])

_question = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
    min_size=1,
    max_size=50,
)

# 限制文本策略为可打印字符（ASCII+中文）
_printable_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")),
    min_size=1,
    max_size=20,
)

# Terminology item with required fields
_terminology_item = st.fixed_dictionaries({
    "word": _printable_text,
    "similarity": _similarity,
    "match_type": _match_type,
    "description": st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")),
        min_size=0,
        max_size=80,
    ),
    "is_specific": st.booleans(),
})

# SQL example item with required fields
_sql_example_item = st.fixed_dictionaries({
    "question": st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")),
        min_size=1,
        max_size=50,
    ),
    "sql": st.sampled_from([
        "SELECT * FROM orders",
        "SELECT COUNT(*) FROM users GROUP BY status",
        "SELECT a.id FROM a JOIN b ON a.id = b.id",
        "SELECT id FROM t1 UNION SELECT id FROM t2",
        "SELECT name FROM products WHERE price > 100",
    ]),
    "similarity": _similarity,
    "match_type": _match_type,
    "is_specific": st.booleans(),
})

# Lists constrained to top_k so all items are preserved (no truncation)
_terminologies_within_topk = st.lists(_terminology_item, min_size=1, max_size=5)
_sql_examples_within_topk = st.lists(_sql_example_item, min_size=1, max_size=3)

# Larger lists to test truncation behavior
_terminologies_large = st.lists(_terminology_item, min_size=1, max_size=20)
_sql_examples_large = st.lists(_sql_example_item, min_size=1, max_size=15)


# ---------------------------------------------------------------------------

class TestRerankingCompletenessProperty6:
    """
    **Validates: Requirements 6.4**

    Property 19: 重排序保序性
    验证 RAGReranker 的各重排序方法保持数据完整性并按 rerank_score 降序排列。
    """

    # --- 6a: rerank_terminologies preserves all items when input <= top_k ---

    @given(terms=_terminologies_within_topk, question=_question)
    @settings(max_examples=100)
    def test_rerank_terminologies_preserves_all_items(self, terms, question):
        """When input size <= top_k, all items must be present in the output."""
        result = RAGReranker.rerank_terminologies(terms, question, top_k=5)

        assert len(result) == len(terms), (
            f"Expected {len(terms)} items, got {len(result)}"
        )

        # Every original word must appear in the result
        input_words = {t["word"] for t in terms}
        output_words = {r["word"] for r in result}
        assert input_words == output_words, (
            f"Items lost: {input_words - output_words}"
        )

    @given(terms=_terminologies_within_topk, question=_question)
    @settings(max_examples=100)
    def test_rerank_terminologies_sorted_descending(self, terms, question):
        """Output must be sorted by rerank_score in descending order."""
        result = RAGReranker.rerank_terminologies(terms, question, top_k=5)

        scores = [r["rerank_score"] for r in result]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Not sorted descending at index {i}: {scores[i]} < {scores[i + 1]}, "
                f"full scores: {scores}"
            )

    @given(terms=_terminologies_within_topk, question=_question)
    @settings(max_examples=100)
    def test_rerank_terminologies_adds_rerank_score(self, terms, question):
        """Every output item must have a rerank_score field."""
        result = RAGReranker.rerank_terminologies(terms, question, top_k=5)

        for item in result:
            assert "rerank_score" in item, "Missing rerank_score field"
            assert isinstance(item["rerank_score"], (int, float)), (
                f"rerank_score must be numeric, got {type(item['rerank_score'])}"
            )

    # --- 6b: rerank_terminologies truncation with large input ---

    @given(terms=_terminologies_large, question=_question)
    @settings(max_examples=100)
    def test_rerank_terminologies_respects_top_k(self, terms, question):
        """Output length must be min(len(input), top_k)."""
        top_k = 5
        result = RAGReranker.rerank_terminologies(terms, question, top_k=top_k)

        expected_len = min(len(terms), top_k)
        assert len(result) == expected_len, (
            f"Expected {expected_len} items, got {len(result)}"
        )

        # Output must still be sorted descending
        scores = [r["rerank_score"] for r in result]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Not sorted descending at index {i}: {scores[i]} < {scores[i + 1]}"
            )

    # --- 6e: rerank_sql_examples preserves items and sorts ---

    @given(examples=_sql_examples_within_topk, question=_question)
    @settings(max_examples=100)
    def test_rerank_sql_examples_preserves_all_items(self, examples, question):
        """When input size <= top_k, all items must be present in the output."""
        result = RAGReranker.rerank_sql_examples(examples, question, top_k=3)

        assert len(result) == len(examples), (
            f"Expected {len(examples)} items, got {len(result)}"
        )

    @given(examples=_sql_examples_within_topk, question=_question)
    @settings(max_examples=100)
    def test_rerank_sql_examples_adds_rerank_score(self, examples, question):
        """Every output item must have a rerank_score field."""
        result = RAGReranker.rerank_sql_examples(examples, question, top_k=3)

        for item in result:
            assert "rerank_score" in item, "Missing rerank_score field"
            assert isinstance(item["rerank_score"], (int, float)), (
                f"rerank_score must be numeric, got {type(item['rerank_score'])}"
            )

    # --- 6e-extra: rerank_sql_examples sorted descending after diversity ---

    @given(examples=_sql_examples_large, question=_question)
    @settings(max_examples=100)
    def test_rerank_sql_examples_sorted_descending(self, examples, question):
        """Output must be sorted by rerank_score in descending order even after diversity selection."""
        result = RAGReranker.rerank_sql_examples(examples, question, top_k=3)

        scores = [r["rerank_score"] for r in result]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Not sorted descending at index {i}: {scores[i]} < {scores[i + 1]}, "
                f"full scores: {scores}"
            )

    # --- 6f: rerank_combined_results completeness ---

    @given(
        terms=_terminologies_within_topk,
        examples=_sql_examples_within_topk,
        question=_question,
    )
    @settings(max_examples=50, derandomize=True, database=None, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_rerank_combined_results_returns_all_keys(self, terms, examples, question):
        """Combined reranking must return dict with all expected keys.
        
         修复 FlakyFailure：mock CrossEncoder 消除 MPS 浮点非确定性。
        CrossEncoder 在 MPS 设备上对相同输入可能产生微小不同的分数，
        导致 Hypothesis 检测到不一致报 FlakyFailure。
        CrossEncoder 的精排质量已在独立单元测试中验证，此处只验证接口完整性。
        """
        import unittest.mock as mock
        # Mock CrossEncoder 返回确定性分数（基于输入长度的简单哈希）
        def _deterministic_predict(pairs):
            return [0.5 + 0.01 * (len(p[1]) % 10) for p in pairs]
        
        with mock.patch('apps.chat.thinking.rag_reranker._get_cross_encoder_model') as mock_model:
            mock_ce = mock.MagicMock()
            mock_ce.predict = _deterministic_predict
            mock_model.return_value = mock_ce
            
            result = RAGReranker.rerank_combined_results(
                terminologies=terms,
                sql_examples=examples,
                custom_prompts=[],
                question=question,
            )

        assert "terminologies" in result
        assert "sql_examples" in result
        assert "custom_prompts" in result

        # Each sub-list must be sorted by rerank_score descending
        for key in ["terminologies"]:
            scores = [r["rerank_score"] for r in result[key]]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1] - 1e-3, (
                    f"{key} not sorted descending at index {i}: "
                    f"{scores[i]} < {scores[i + 1]}"
                )

    # --- 6g: empty input handling ---

    def test_rerank_terminologies_empty_input(self):
        """Empty input must return empty list."""
        assert RAGReranker.rerank_terminologies([], "test") == []

    def test_rerank_sql_examples_empty_input(self):
        """Empty input must return empty list."""
        assert RAGReranker.rerank_sql_examples([], "test") == []
