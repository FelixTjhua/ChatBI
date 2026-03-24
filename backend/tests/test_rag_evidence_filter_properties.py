"""Property-based tests for RAG Evidence Quality Filter."""
import sys
import os

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.chat.thinking.rag_evidence_filter import filter_rag_evidence

# ---------------------------------------------------------------------------

_similarity = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

_evidence_item = st.fixed_dictionaries({
    "word": st.text(min_size=1, max_size=50),
    "similarity": _similarity,
    "source_type": st.sampled_from(["terminology", "sql_example"]),
})

_evidence_lists = st.lists(_evidence_item, min_size=0, max_size=20)

_thresholds = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


class TestFilterRagEvidence:
    """Tests for filter_rag_evidence function."""

    @given(evidence=_evidence_lists, threshold=_thresholds)
    @settings(max_examples=200)
    def test_filtered_plus_removed_equals_original(self, evidence, threshold):
        """filtered + removed should always equal the original list length."""
        filtered, removed = filter_rag_evidence(evidence, threshold=threshold)
        assert len(filtered) + len(removed) == len(evidence)

    @given(evidence=_evidence_lists, threshold=_thresholds)
    @settings(max_examples=200)
    def test_all_filtered_items_meet_threshold(self, evidence, threshold):
        """Every item in filtered should have score >= threshold."""
        filtered, _ = filter_rag_evidence(evidence, threshold=threshold)
        for item in filtered:
            score = item.get('rerank_score', 0) or item.get('similarity', 0)
            if score > 1:
                score = score / 100.0
            assert score >= threshold

    @given(evidence=_evidence_lists, threshold=_thresholds)
    @settings(max_examples=200)
    def test_all_removed_items_below_threshold(self, evidence, threshold):
        """Every item in removed should have score < threshold."""
        _, removed = filter_rag_evidence(evidence, threshold=threshold)
        for item in removed:
            score = item.get('rerank_score', 0) or item.get('similarity', 0)
            if score > 1:
                score = score / 100.0
            assert score < threshold

    def test_empty_input(self):
        """Empty input should return empty results."""
        filtered, removed = filter_rag_evidence([])
        assert filtered == []
        assert removed == []

    def test_all_high_quality(self):
        """All items above threshold should be kept."""
        items = [
            {"word": "a", "similarity": 0.9, "source_type": "terminology"},
            {"word": "b", "similarity": 0.8, "source_type": "sql_example"},
        ]
        filtered, removed = filter_rag_evidence(items, threshold=0.35)
        assert len(filtered) == 2
        assert len(removed) == 0

    def test_all_low_quality(self):
        """All items below threshold should be removed."""
        items = [
            {"word": "a", "similarity": 0.1, "source_type": "terminology"},
            {"word": "b", "similarity": 0.2, "source_type": "sql_example"},
        ]
        filtered, removed = filter_rag_evidence(items, threshold=0.35)
        assert len(filtered) == 0
        assert len(removed) == 2

    def test_rerank_score_preferred_over_similarity(self):
        """rerank_score should be used when present."""
        items = [
            {"word": "a", "similarity": 0.1, "rerank_score": 0.9, "source_type": "terminology"},
        ]
        filtered, removed = filter_rag_evidence(items, threshold=0.35)
        assert len(filtered) == 1

    def test_score_normalization_above_1(self):
        """Scores > 1 should be normalized by dividing by 100."""
        items = [
            {"word": "a", "similarity": 50, "source_type": "terminology"},  # 50/100 = 0.5
        ]
        filtered, removed = filter_rag_evidence(items, threshold=0.35)
        assert len(filtered) == 1
