"""Property-based tests for RAG quality metrics calculation."""
import sys
import os
import math
import re

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path so that app modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.chat.thinking.rag_thinking import RAGQualityMetrics
from apps.chat.thinking.rag_evaluator import RAGEvaluator, RetrievalMetrics


_similarity_01 = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Similarity score in percentage format (>1, up to 100)
_similarity_pct = st.floats(min_value=1.01, max_value=100.0, allow_nan=False, allow_infinity=False)

# Mixed similarity: either [0,1] or percentage format
_similarity_any = st.one_of(_similarity_01, _similarity_pct)

# A single retrieval item dict with a similarity field
_retrieval_item = _similarity_any.map(lambda s: {"similarity": s})

# Non-empty list of retrieval items (1 to 20 items)
_retrieval_items = st.lists(_retrieval_item, min_size=1, max_size=20)

# Threshold for high-quality determination
_threshold = st.floats(min_value=0.1, max_value=0.99, allow_nan=False, allow_infinity=False)

# Items with only [0,1] similarities (no percentage normalization needed)
_retrieval_item_01 = _similarity_01.map(lambda s: {"similarity": s})
_retrieval_items_01 = st.lists(_retrieval_item_01, min_size=1, max_size=20)


# ---------------------------------------------------------------------------

class TestRAGQualityMetricsProperty4:
    """
    **Validates: Requirements 3.4**

    Property 4: RAG 质量指标计算正确性
    验证 RAGQualityMetrics.calculate_retrieval_quality() 和
    RAGEvaluator.evaluate_retrieval() 的指标计算正确性。
    """

    # --- 4a: avg_similarity equals arithmetic mean ---

    @given(items=_retrieval_items)
    @settings(max_examples=100)
    def test_avg_similarity_equals_arithmetic_mean(self, items):
        """avg_similarity must equal the arithmetic mean of (normalized) similarity scores."""
        result = RAGQualityMetrics.calculate_retrieval_quality(items)

        # Manually compute expected mean with same normalization logic
        similarities = []
        for item in items:
            sim = item.get("similarity", 0)
            if sim > 1:
                sim = sim / 100.0
            similarities.append(sim)

        expected_mean = sum(similarities) / len(similarities)

        assert math.isclose(result["avg_similarity"], round(expected_mean, 3), abs_tol=1e-6), (
            f"avg_similarity {result['avg_similarity']} != expected mean {round(expected_mean, 3)} "
            f"for {len(items)} items"
        )

    @given(items=_retrieval_items)
    @settings(max_examples=100)
    def test_evaluator_avg_similarity_equals_arithmetic_mean(self, items):
        """RAGEvaluator.evaluate_retrieval avg_similarity must equal arithmetic mean."""
        metrics = RAGEvaluator.evaluate_retrieval(items)

        similarities = []
        for item in items:
            sim = item.get("similarity", 0) or 0
            if sim > 1:
                sim = sim / 100.0
            similarities.append(sim)

        expected_mean = sum(similarities) / len(similarities)

        assert math.isclose(metrics.avg_similarity, round(expected_mean, 4), abs_tol=1e-6), (
            f"RAGEvaluator avg_similarity {metrics.avg_similarity} != "
            f"expected mean {round(expected_mean, 4)}"
        )

    # --- 4b: quality_score in [0, 1] ---

    @given(items=_retrieval_items, threshold=_threshold)
    @settings(max_examples=100)
    def test_quality_score_in_unit_range(self, items, threshold):
        """quality_score must be in [0, 1] for any valid input."""
        result = RAGQualityMetrics.calculate_retrieval_quality(items, threshold=threshold)

        assert 0.0 <= result["quality_score"] <= 1.0, (
            f"quality_score {result['quality_score']} is outside [0, 1] "
            f"for {len(items)} items with threshold={threshold}"
        )

    @given(items=_retrieval_items_01, threshold=_threshold)
    @settings(max_examples=100)
    def test_quality_score_formula_correctness(self, items, threshold):
        """quality_score = median_sim * 0.5 + high_quality_ratio * 0.3 + consistency * 0.2 for [0,1] inputs."""
        result = RAGQualityMetrics.calculate_retrieval_quality(items, threshold=threshold)

        # Recompute expected quality_score with new formula
        similarities = [item.get("similarity", 0) for item in items]
        n = len(similarities)
        avg_sim = sum(similarities) / n
        sorted_sims = sorted(similarities)
        median_sim = sorted_sims[n // 2] if n % 2 == 1 else (sorted_sims[n // 2 - 1] + sorted_sims[n // 2]) / 2
        variance = sum((s - avg_sim) ** 2 for s in similarities) / n
        high_quality = sum(1 for s in similarities if s >= threshold)
        high_quality_ratio = high_quality / n
        consistency = max(0.0, 1.0 - min(variance * 4, 1.0))
        expected_qs = median_sim * 0.5 + high_quality_ratio * 0.3 + consistency * 0.2

        assert math.isclose(result["quality_score"], round(expected_qs, 3), abs_tol=1e-6), (
            f"quality_score {result['quality_score']} != expected {round(expected_qs, 3)}"
        )

    # --- 4c: quality metrics computed correctly from RAG retrieval results ---

    @given(items=_retrieval_items)
    @settings(max_examples=100)
    def test_empty_input_returns_zero_metrics(self, items):
        """Empty input must return all-zero metrics."""
        # This test always uses empty input regardless of generated items
        result = RAGQualityMetrics.calculate_retrieval_quality([])
        assert result["total_count"] == 0
        assert result["avg_similarity"] == 0.0
        assert result["quality_score"] == 0.0
        assert result["confidence"] == "none"

    @given(items=_retrieval_items, threshold=_threshold)
    @settings(max_examples=100)
    def test_high_quality_count_consistency(self, items, threshold):
        """high_quality_count must match the count of items with similarity >= threshold."""
        result = RAGQualityMetrics.calculate_retrieval_quality(items, threshold=threshold)

        similarities = []
        for item in items:
            sim = item.get("similarity", 0)
            if sim > 1:
                sim = sim / 100.0
            similarities.append(sim)

        expected_hq = sum(1 for s in similarities if s >= threshold)

        assert result["high_quality_count"] == expected_hq, (
            f"high_quality_count {result['high_quality_count']} != expected {expected_hq}"
        )
        assert result["total_count"] == len(items), (
            f"total_count {result['total_count']} != {len(items)}"
        )

    @given(items=_retrieval_items)
    @settings(max_examples=100)
    def test_confidence_level_matches_quality_score(self, items):
        """confidence level must correspond to quality_score thresholds.

        The new implementation determines confidence from quality_score
        (not raw avg_sim), using thresholds: >=0.75 high, >=0.55 medium,
        >=0.35 low, >0 very_low, else none.
        """
        result = RAGQualityMetrics.calculate_retrieval_quality(items)
        confidence = result["confidence"]

        # Recompute quality_score to match source logic
        similarities = []
        for item in items:
            sim = item.get("similarity", 0)
            if sim > 1:
                sim = sim / 100.0
            similarities.append(max(0.0, min(1.0, sim)))
        n = len(similarities)
        avg_sim = sum(similarities) / n
        sorted_sims = sorted(similarities)
        median_sim = sorted_sims[n // 2] if n % 2 == 1 else (sorted_sims[n // 2 - 1] + sorted_sims[n // 2]) / 2
        variance = sum((s - avg_sim) ** 2 for s in similarities) / n
        high_quality = sum(1 for s in similarities if s >= 0.7)
        high_quality_ratio = high_quality / n
        consistency = max(0.0, 1.0 - min(variance * 4, 1.0))
        qs = median_sim * 0.5 + high_quality_ratio * 0.3 + consistency * 0.2

        if qs >= 0.75:
            assert confidence == "high", f"quality_score={qs} should be 'high', got '{confidence}'"
        elif qs >= 0.55:
            assert confidence == "medium", f"quality_score={qs} should be 'medium', got '{confidence}'"
        elif qs >= 0.35:
            assert confidence == "low", f"quality_score={qs} should be 'low', got '{confidence}'"
        elif qs > 0:
            assert confidence == "very_low", f"quality_score={qs} should be 'very_low', got '{confidence}'"
        else:
            assert confidence == "none", f"quality_score={qs} should be 'none', got '{confidence}'"


# ---------------------------------------------------------------------------
from apps.chat.thinking.rag_evaluator import (
    GenerationMetrics,
    EndToEndMetrics,
    EvaluationReport,
)


_question_text = st.text(min_size=1, max_size=200).filter(lambda t: t.strip())

# Chat / record IDs
_positive_int = st.integers(min_value=1, max_value=10**9)

# Similarity scores strictly in [0, 1]
_sim_score = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Build a RetrievalMetrics with plausible values
_retrieval_metrics_st = st.builds(
    RetrievalMetrics,
    precision_at_k=st.just({1: 0.5, 3: 0.6, 5: 0.4}),
    recall_at_k=st.just({1: 0.3, 3: 0.5, 5: 0.7}),
    mrr=_sim_score,
    ndcg=_sim_score,
    avg_similarity=_sim_score,
    high_quality_ratio=_sim_score,
    total_retrieved=st.integers(min_value=0, max_value=100),
    relevant_count=st.integers(min_value=0, max_value=100),
)

# Build a GenerationMetrics with plausible values
_generation_metrics_st = st.builds(
    GenerationMetrics,
    sql_execution_success=st.booleans(),
    sql_syntax_valid=st.booleans(),
    response_length=st.integers(min_value=0, max_value=10000),
    generation_time=st.floats(min_value=0.0, max_value=60.0, allow_nan=False, allow_infinity=False),
    input_tokens=st.integers(min_value=0, max_value=5000),
    output_tokens=st.integers(min_value=0, max_value=5000),
    total_tokens=st.integers(min_value=0, max_value=10000),
    token_efficiency=_sim_score,
    hallucination_score=_sim_score,
    rag_context_used=st.booleans(),
    rag_utilization=_sim_score,
    contextual_relevance=_sim_score,
    specificity=_sim_score,
    completeness=_sim_score,
    missing_rate=_sim_score,
    align_score=_sim_score,
)

# Build an EndToEndMetrics with plausible values
_end_to_end_metrics_st = st.builds(
    EndToEndMetrics,
    task_completed=st.booleans(),
    steps_completed=st.integers(min_value=0, max_value=10),
    total_steps=st.integers(min_value=1, max_value=10),
    total_latency=st.floats(min_value=0.0, max_value=120.0, allow_nan=False, allow_infinity=False),
    stage_latencies=st.just({"rag_retrieval": 1.0, "sql_generation": 2.0}),
    retry_count=st.integers(min_value=0, max_value=5),
    error_count=st.integers(min_value=0, max_value=5),
)

# Optional metrics (may or may not be provided)
_optional_retrieval = st.one_of(st.none(), _retrieval_metrics_st)
_optional_generation = st.one_of(st.none(), _generation_metrics_st)
_optional_end_to_end = st.one_of(st.none(), _end_to_end_metrics_st)


# ---------------------------------------------------------------------------

class TestRAGEvaluationReportCompletenessProperty14:
    """
    **Validates: Requirements 9.5**

    Property 14: RAG 评估报告完整性
    验证 generate_report() 返回的报告包含非空的各项指标且评分在 [0, 1] 范围内。
    """

    # --- 14a: Report contains all required fields ---

    @given(
        question=_question_text,
        chat_id=_positive_int,
        record_id=_positive_int,
        retrieval=_optional_retrieval,
        generation=_optional_generation,
        end_to_end=_optional_end_to_end,
    )
    @settings(max_examples=100)
    def test_report_contains_all_required_fields(
        self, question, chat_id, record_id, retrieval, generation, end_to_end
    ):
        """generate_report() must return a report with all required top-level fields."""
        report = RAGEvaluator.generate_report(
            question=question,
            chat_id=chat_id,
            record_id=record_id,
            retrieval_metrics=retrieval,
            generation_metrics=generation,
            end_to_end_metrics=end_to_end,
        )

        # Must be an EvaluationReport instance
        assert isinstance(report, EvaluationReport)

        # Required top-level fields
        assert report.timestamp != "", "timestamp must be non-empty"
        assert report.chat_id == chat_id
        assert report.record_id == record_id
        assert report.question == question

        # Grade must be one of the valid grades
        assert report.grade in ("A", "B", "C", "D", "F"), (
            f"grade '{report.grade}' is not a valid grade"
        )

        # overall_score is on a 0-100 scale
        assert 0.0 <= report.overall_score <= 100.0, (
            f"overall_score {report.overall_score} is outside [0, 100]"
        )

        # recommendations must be a non-empty list
        assert isinstance(report.recommendations, list)
        assert len(report.recommendations) > 0, "recommendations must not be empty"

        # to_dict must work and return a dict
        report_dict = report.to_dict()
        assert isinstance(report_dict, dict)
        for key in ("timestamp", "chat_id", "record_id", "question",
                     "overall_score", "grade", "recommendations"):
            assert key in report_dict, f"report dict missing key '{key}'"

    # --- 14b: All score/rating fields in [0, 1] range ---

    @given(
        question=_question_text,
        retrieval=_retrieval_metrics_st,
        generation=_generation_metrics_st,
        end_to_end=_end_to_end_metrics_st,
    )
    @settings(max_examples=100)
    def test_all_metric_scores_in_valid_range(
        self, question, retrieval, generation, end_to_end
    ):
        """All individual metric scores/ratings must be in [0, 1] range."""
        report = RAGEvaluator.generate_report(
            question=question,
            retrieval_metrics=retrieval,
            generation_metrics=generation,
            end_to_end_metrics=end_to_end,
        )

        # Check retrieval metrics scores are in [0, 1]
        r = report.retrieval
        assert 0.0 <= r.mrr <= 1.0, f"mrr {r.mrr} outside [0,1]"
        assert 0.0 <= r.ndcg <= 1.0, f"ndcg {r.ndcg} outside [0,1]"
        assert 0.0 <= r.avg_similarity <= 1.0, f"avg_similarity {r.avg_similarity} outside [0,1]"
        assert 0.0 <= r.high_quality_ratio <= 1.0, f"high_quality_ratio {r.high_quality_ratio} outside [0,1]"
        for k, v in r.precision_at_k.items():
            assert 0.0 <= v <= 1.0, f"precision_at_{k} {v} outside [0,1]"
        for k, v in r.recall_at_k.items():
            assert 0.0 <= v <= 1.0, f"recall_at_{k} {v} outside [0,1]"

        # Check generation metrics scores are in [0, 1]
        g = report.generation
        assert 0.0 <= g.token_efficiency <= 1.0, f"token_efficiency {g.token_efficiency} outside [0,1]"
        assert 0.0 <= g.hallucination_score <= 1.0, f"hallucination_score {g.hallucination_score} outside [0,1]"
        assert 0.0 <= g.rag_utilization <= 1.0, f"rag_utilization {g.rag_utilization} outside [0,1]"
        assert 0.0 <= g.contextual_relevance <= 1.0, f"contextual_relevance {g.contextual_relevance} outside [0,1]"
        assert 0.0 <= g.specificity <= 1.0, f"specificity {g.specificity} outside [0,1]"
        assert 0.0 <= g.completeness <= 1.0, f"completeness {g.completeness} outside [0,1]"
        assert 0.0 <= g.missing_rate <= 1.0, f"missing_rate {g.missing_rate} outside [0,1]"
        assert 0.0 <= g.align_score <= 1.0, f"align_score {g.align_score} outside [0,1]"

    # --- 14c: Report contains non-empty metric values when metrics provided ---

    @given(
        question=_question_text,
        chat_id=_positive_int,
        record_id=_positive_int,
        retrieval=_retrieval_metrics_st,
        generation=_generation_metrics_st,
        end_to_end=_end_to_end_metrics_st,
    )
    @settings(max_examples=100)
    def test_report_contains_nonempty_metrics_when_provided(
        self, question, chat_id, record_id, retrieval, generation, end_to_end
    ):
        """When all three metric objects are provided, the report must contain them (non-None)."""
        report = RAGEvaluator.generate_report(
            question=question,
            chat_id=chat_id,
            record_id=record_id,
            retrieval_metrics=retrieval,
            generation_metrics=generation,
            end_to_end_metrics=end_to_end,
        )

        # All metric sections must be present (not None)
        assert report.retrieval is not None, "retrieval metrics must not be None"
        assert report.generation is not None, "generation metrics must not be None"
        assert report.end_to_end is not None, "end_to_end metrics must not be None"

        # Grade must be consistent with overall_score
        score = report.overall_score
        if score >= 90:
            assert report.grade == "A"
        elif score >= 75:
            assert report.grade == "B"
        elif score >= 60:
            assert report.grade == "C"
        elif score >= 40:
            assert report.grade == "D"
        else:
            assert report.grade == "F"

        # The report dict must serialize all metric sections
        d = report.to_dict()
        assert d["retrieval_metrics"] is not None
        assert d["generation_metrics"] is not None
        assert d["end_to_end_metrics"] is not None


_sql_keyword = st.sampled_from(['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'JOIN', 'LEFT JOIN'])
_table_name = st.sampled_from(['orders', 'products', 'customers', 'sales', 'inventory', 'users'])
_column_name = st.sampled_from(['id', 'name', 'price', 'quantity', 'total', 'date', 'status', 'amount', 'category'])
_agg_func = st.sampled_from(['COUNT', 'SUM', 'AVG', 'MAX', 'MIN'])


@st.composite
def valid_sql_query(draw):
    """Generate a valid-looking SQL query using known table/column names."""
    table = draw(_table_name)
    col1 = draw(_column_name)
    col2 = draw(_column_name)
    use_agg = draw(st.booleans())
    use_where = draw(st.booleans())

    if use_agg:
        agg = draw(_agg_func)
        select_clause = f"{agg}({col1})"
    else:
        select_clause = f"{col1}, {col2}"

    sql = f"SELECT {select_clause} FROM {table}"
    if use_where:
        sql += f" WHERE {col1} IS NOT NULL"
    return sql


@st.composite
def valid_schema_for_tables(draw, tables=None):
    """Generate a schema string that contains the given table and column names."""
    if tables is None:
        tables = [draw(_table_name)]
    all_cols = ['id', 'name', 'price', 'quantity', 'total', 'date', 'status', 'amount', 'category']
    schema_parts = []
    for t in tables:
        cols = draw(st.lists(st.sampled_from(all_cols), min_size=2, max_size=6, unique=True))
        col_defs = ", ".join(f"{c} VARCHAR" for c in cols)
        schema_parts.append(f"CREATE TABLE {t} ({col_defs});")
    return "\n".join(schema_parts)


@st.composite
def valid_rag_context(draw):
    """Generate a valid RAG context with schema, terminologies, and sql_examples."""
    tables = draw(st.lists(_table_name, min_size=1, max_size=3, unique=True))
    schema = draw(valid_schema_for_tables(tables=tables))
    term_count = draw(st.integers(min_value=0, max_value=5))
    example_count = draw(st.integers(min_value=0, max_value=3))
    return {
        'schema': schema,
        'terminologies_used': term_count,
        'terminologies': [{'word': f'term_{i}', 'description': f'desc_{i}'} for i in range(term_count)],
        'sql_examples_used': example_count,
        'sql_examples': [{'sql': f'SELECT * FROM {tables[0]}', 'question': f'q_{i}'} for i in range(example_count)],
    }


@st.composite
def valid_retrieval_items(draw):
    """Generate a list of retrieval items with similarity scores."""
    n = draw(st.integers(min_value=1, max_value=10))
    items = []
    for _ in range(n):
        sim = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
        items.append({'similarity': sim})
    return items


class TestEvaluationReportCompletenessProperty16:
    """Feature: chatbi-system-audit-optimization, Property 16: 评估报告完整性"""

    @given(
        question=_question_text,
        sql=valid_sql_query(),
        rag_context=valid_rag_context(),
        retrieval_items=valid_retrieval_items(),
        sql_executed=st.booleans(),
    )
    @settings(max_examples=100)
    def test_report_has_all_required_fields_with_evaluation_inputs(
        self, question, sql, rag_context, retrieval_items, sql_executed
    ):
        """
        For any valid evaluation input, generate_report() returns a complete report.

        **Validates: Requirements 7.3, 13.2**
        """
        # Evaluate retrieval
        retrieval_metrics = RAGEvaluator.evaluate_retrieval(retrieval_items)

        # Evaluate generation
        generation_metrics = RAGEvaluator.evaluate_generation(
            generated_content=question,
            sql=sql,
            sql_executed=sql_executed,
            rag_context=rag_context,
        )

        # Generate report
        report = RAGEvaluator.generate_report(
            question=question,
            retrieval_metrics=retrieval_metrics,
            generation_metrics=generation_metrics,
        )

        # Property 16: overall_score in [0, 100]
        assert 0.0 <= report.overall_score <= 100.0, (
            f"overall_score {report.overall_score} outside [0, 100]"
        )

        # Property 16: grade is one of A/B/C/D/F
        assert report.grade in ('A', 'B', 'C', 'D', 'F'), (
            f"grade '{report.grade}' is not valid"
        )

        # Property 16: retrieval_metrics present
        assert report.retrieval is not None, "retrieval_metrics must not be None"

        # Property 16: generation_metrics present
        assert report.generation is not None, "generation_metrics must not be None"

        # Property 16: recommendations is a non-empty list
        assert isinstance(report.recommendations, list), "recommendations must be a list"
        assert len(report.recommendations) > 0, "recommendations must not be empty"

    @given(
        question=_question_text,
        sql=valid_sql_query(),
        rag_context=valid_rag_context(),
        retrieval_items=valid_retrieval_items(),
    )
    @settings(max_examples=100)
    def test_report_to_dict_contains_mapped_field_names(
        self, question, sql, rag_context, retrieval_items
    ):
        """
        to_dict() must map internal field names to API-compatible names.

        **Validates: Requirements 7.3, 13.2**
        """
        retrieval_metrics = RAGEvaluator.evaluate_retrieval(retrieval_items)
        generation_metrics = RAGEvaluator.evaluate_generation(
            generated_content=question, sql=sql, rag_context=rag_context,
        )
        report = RAGEvaluator.generate_report(
            question=question,
            retrieval_metrics=retrieval_metrics,
            generation_metrics=generation_metrics,
        )

        d = report.to_dict()

        # Must contain the API-compatible field names
        assert 'overall_score' in d
        assert 'grade' in d
        assert 'retrieval_metrics' in d
        assert 'generation_metrics' in d
        assert 'recommendations' in d

        # overall_score in [0, 100]
        assert 0.0 <= d['overall_score'] <= 100.0

        # grade consistency with score
        score = d['overall_score']
        grade = d['grade']
        if score >= 90:
            assert grade == 'A'
        elif score >= 75:
            assert grade == 'B'
        elif score >= 60:
            assert grade == 'C'
        elif score >= 40:
            assert grade == 'D'
        else:
            assert grade == 'F'



_known_table = st.sampled_from(['orders', 'products', 'customers', 'sales'])
_known_column = st.sampled_from(['id', 'name', 'price', 'quantity', 'total', 'date', 'status'])
_unknown_table = st.sampled_from(['phantom_table', 'ghost_data', 'fake_records', 'nonexistent_tbl'])
_unknown_column = st.sampled_from(['phantom_col', 'ghost_field', 'fake_value', 'nonexistent_attr'])


@st.composite
def sql_with_hallucinated_table(draw):
    """Generate SQL that references a table NOT in the schema."""
    unknown = draw(_unknown_table)
    col = draw(_known_column)
    return f"SELECT {col} FROM {unknown}"


@st.composite
def sql_with_hallucinated_column(draw):
    """Generate SQL that references a column NOT in the schema."""
    table = draw(_known_table)
    unknown_col = draw(_unknown_column)
    known_col = draw(_known_column)
    return f"SELECT {unknown_col}, {known_col} FROM {table}"


@st.composite
def schema_with_known_tables(draw):
    """Generate a schema containing only known tables and columns."""
    tables = draw(st.lists(_known_table, min_size=1, max_size=4, unique=True))
    cols = ['id', 'name', 'price', 'quantity', 'total', 'date', 'status']
    parts = []
    for t in tables:
        selected_cols = draw(st.lists(st.sampled_from(cols), min_size=3, max_size=7, unique=True))
        col_defs = ", ".join(f"{c} VARCHAR" for c in selected_cols)
        parts.append(f"CREATE TABLE {t} ({col_defs});")
    return "\n".join(parts)


class TestHallucinationDetectionProperty17:
    """
    Feature: chatbi-system-audit-optimization, Property 17: 幻觉检测正确性

    **Validates: Requirements 13.3**

    For any SQL containing table/field names not in the RAG context,
    _detect_hallucination() should return a hallucination score > 0.
    """

    @given(
        sql=sql_with_hallucinated_table(),
        schema=schema_with_known_tables(),
    )
    @settings(max_examples=100)
    def test_hallucinated_table_detected(self, sql, schema):
        """
        SQL referencing a table not in schema must produce hallucination_score > 0.

        **Validates: Requirements 13.3**
        """
        rag_context = {'schema': schema}
        score = RAGEvaluator._detect_hallucination(sql, rag_context)

        assert score > 0, (
            f"Hallucination score should be > 0 for SQL with unknown table, "
            f"got {score}. SQL: {sql}, Schema: {schema[:200]}"
        )

    @given(
        sql=sql_with_hallucinated_column(),
        schema=schema_with_known_tables(),
    )
    @settings(max_examples=100)
    def test_hallucinated_column_detected(self, sql, schema):
        """
        SQL referencing a column not in schema must produce hallucination_score > 0.

        **Validates: Requirements 13.3**
        """
        rag_context = {'schema': schema}
        score = RAGEvaluator._detect_hallucination(sql, rag_context)

        assert score > 0, (
            f"Hallucination score should be > 0 for SQL with unknown column, "
            f"got {score}. SQL: {sql}, Schema: {schema[:200]}"
        )

    @given(schema=schema_with_known_tables())
    @settings(max_examples=100)
    def test_no_hallucination_for_known_references(self, schema):
        """
        SQL using only known table/column names should produce hallucination_score == 0.

        **Validates: Requirements 13.3**
        """
        # Build SQL using only names that exist in the schema
        # Parse schema to extract actual table and column names
        table_names = re.findall(r'CREATE TABLE (\w+)', schema, re.IGNORECASE)
        assume(len(table_names) > 0)

        # Extract columns for the first table
        table = table_names[0]
        col_match = re.search(
            rf'CREATE TABLE {table}\s*\(([^)]+)\)', schema, re.IGNORECASE
        )
        assume(col_match is not None)
        cols = [c.strip().split()[0] for c in col_match.group(1).split(',')]
        assume(len(cols) > 0)

        sql = f"SELECT {cols[0]} FROM {table}"
        rag_context = {'schema': schema}
        score = RAGEvaluator._detect_hallucination(sql, rag_context)

        assert score == 0.0, (
            f"Hallucination score should be 0 for SQL with only known references, "
            f"got {score}. SQL: {sql}"
        )

    @given(schema=schema_with_known_tables())
    @settings(max_examples=100)
    def test_empty_sql_returns_zero(self, schema):
        """
        Empty SQL should return hallucination_score == 0.

        **Validates: Requirements 13.3**
        """
        rag_context = {'schema': schema}
        score = RAGEvaluator._detect_hallucination("", rag_context)
        assert score == 0.0, f"Empty SQL should return 0, got {score}"

    @given(sql=sql_with_hallucinated_table())
    @settings(max_examples=100)
    def test_no_schema_returns_half(self, sql):
        """
        When no schema is available, hallucination detection returns 0.5 (uncertain).

        **Validates: Requirements 13.3**
        """
        rag_context = {'schema': ''}
        score = RAGEvaluator._detect_hallucination(sql, rag_context)
        assert score == 0.5, f"No schema should return 0.5, got {score}"
