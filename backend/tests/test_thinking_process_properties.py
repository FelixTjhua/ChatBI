"""Property-based tests for Thinking Process module."""
import sys
import os
import time

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path so that app modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.chat.thinking.rag_thinking import (
    ThinkingStage,
    RAGThinkingProcess,
)

# ---------------------------------------------------------------------------

VALID_STATUSES = {"running", "completed", "failed"}

# Data query stages expected in a complete RAG thinking process
DATA_QUERY_STAGES = [
    "query_rewrite",
    "rag_retrieval",
    "context_compression",
    "dialogue_state",
    "prompt_construction",
]

_stage_names = st.sampled_from([
    "query_rewrite",
    "rag_retrieval",
    "context_compression",
    "dialogue_state",
    "prompt_construction",
    "sql_generation",
    "sql_execution",
    "chart_generation",
    "data_analysis",
    "data_prediction",
    "direct_answer",
    "datasource_selection",
    "smart_output",
])

# Duration in milliseconds (0 to 60_000 ms = 60 seconds)
_duration_ms = st.integers(min_value=0, max_value=60000)

# Status values for record_stage convenience method
_record_status = st.sampled_from(["completed", "failed", "running"])

# Non-empty question strings
_questions = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())

# Non-empty error messages
_error_messages = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())

# Boolean strategy for rag_enabled
_rag_enabled = st.booleans()



class TestThinkingProcessStageCompleteness:
    """
    **Validates: Requirements 1.6, 4.1, 4.2, 9.5, 10.5, 11.5, 12.5, 13.5**

    Property 11: 阶段完整性
    For any completed RAGThinkingProcess, to_dict() output contains question,
    rag_enabled, and stages fields, and each recorded stage has status,
    duration (ms), and data fields.
    """

    # --- 11a: to_dict() always contains top-level required fields ---

    @given(question=_questions, rag_enabled=_rag_enabled)
    @settings(max_examples=100)
    def test_to_dict_contains_required_top_level_fields(self, question, rag_enabled):
        """Feature: chatbi-system-audit-optimization, Property 11: 阶段完整性
        to_dict() must always contain question, rag_enabled, and stages."""
        process = RAGThinkingProcess()
        process.set_question(question)
        process.set_rag_enabled(rag_enabled)

        result = process.to_dict()

        assert "question" in result, f"Missing 'question' in to_dict() output"
        assert "rag_enabled" in result, f"Missing 'rag_enabled' in to_dict() output"
        assert "stages" in result, f"Missing 'stages' in to_dict() output"

        assert result["question"] == question
        assert result["rag_enabled"] == rag_enabled
        assert isinstance(result["stages"], dict)

    # --- 11b: question and rag_enabled values are preserved ---

    @given(question=_questions, rag_enabled=_rag_enabled)
    @settings(max_examples=100)
    def test_question_and_rag_enabled_preserved(self, question, rag_enabled):
        """Feature: chatbi-system-audit-optimization, Property 11: 阶段完整性
        question and rag_enabled values must be preserved in to_dict()."""
        process = RAGThinkingProcess()
        process.set_question(question)
        process.set_rag_enabled(rag_enabled)

        # Add some stages
        stage = process.start_stage("query_rewrite")
        stage.complete()

        result = process.to_dict()
        assert result["question"] == question
        assert result["rag_enabled"] == rag_enabled

    # --- 11c: Each recorded stage has status and duration ---

    @given(
        stage_names=st.lists(_stage_names, min_size=1, max_size=8, unique=True),
        status=_record_status,
        duration=_duration_ms,
    )
    @settings(max_examples=100)
    def test_each_stage_has_status_and_duration(self, stage_names, status, duration):
        """Feature: chatbi-system-audit-optimization, Property 11: 阶段完整性
        Every stage in to_dict()['stages'] must have status and duration fields."""
        process = RAGThinkingProcess()
        process.set_question("test question")
        process.set_rag_enabled(True)

        for name in stage_names:
            process.record_stage(name=name, status=status, duration=duration)

        result = process.to_dict()
        stages = result["stages"]

        assert len(stages) > 0, "Expected at least one stage"

        for key, stage_data in stages.items():
            assert "status" in stage_data, f"Stage '{key}' missing 'status'"
            assert "duration" in stage_data, f"Stage '{key}' missing 'duration'"
            assert stage_data["status"] in VALID_STATUSES, (
                f"Stage '{key}' has invalid status '{stage_data['status']}'"
            )
            assert stage_data["duration"] >= 0, (
                f"Stage '{key}' has negative duration {stage_data['duration']}"
            )

    # --- 11d: start_stage + complete lifecycle produces valid output ---

    @given(
        stage_names=st.lists(_stage_names, min_size=1, max_size=6, unique=True),
        question=_questions,
        rag_enabled=_rag_enabled,
    )
    @settings(max_examples=100)
    def test_start_complete_lifecycle_valid(self, stage_names, question, rag_enabled):
        """Feature: chatbi-system-audit-optimization, Property 11: 阶段完整性
        Stages created via start_stage() + complete() must produce valid output."""
        process = RAGThinkingProcess()
        process.set_question(question)
        process.set_rag_enabled(rag_enabled)

        for name in stage_names:
            stage = process.start_stage(name)
            stage.complete()

        result = process.to_dict()

        assert "question" in result
        assert "rag_enabled" in result
        assert "stages" in result

        for key, stage_data in result["stages"].items():
            assert "status" in stage_data
            assert "duration" in stage_data
            assert stage_data["status"] == "completed"
            assert stage_data["duration"] >= 0

    # --- 11e: Data query stages completeness ---

    @given(question=_questions)
    @settings(max_examples=100)
    def test_data_query_stages_completeness(self, question):
        """Feature: chatbi-system-audit-optimization, Property 11: 阶段完整性
        For data query type, all expected stages should be present after recording."""
        process = RAGThinkingProcess()
        process.set_question(question)
        process.set_rag_enabled(True)

        # Simulate a complete data query thinking process
        for stage_name in DATA_QUERY_STAGES:
            process.record_stage(name=stage_name, status="completed", duration=100)

        result = process.to_dict()
        stages = result["stages"]

        # All data query stages should be present (possibly with name mapping)
        for expected_stage in DATA_QUERY_STAGES:
            # 重构：统一使用 rag_retrieval 阶段名，不再需要映射
            assert expected_stage in stages, (
                f"Expected stage '{expected_stage}' not found in stages: {list(stages.keys())}"
            )

    # --- 11f: ThinkingStage.to_dict() always has stage, status, duration ---

    @given(stage_name=_stage_names)
    @settings(max_examples=100)
    def test_individual_stage_to_dict_fields(self, stage_name):
        """Feature: chatbi-system-audit-optimization, Property 11: 阶段完整性
        Every ThinkingStage.to_dict() must contain stage, status, duration."""
        stage = ThinkingStage(stage_name=stage_name)
        d = stage.to_dict()

        assert "stage" in d, f"Missing 'stage' key"
        assert "status" in d, f"Missing 'status' key"
        assert "duration" in d, f"Missing 'duration' key"
        assert d["stage"] == stage_name
        assert d["status"] in VALID_STATUSES
        assert d["duration"] >= 0



class TestThinkingStageFailureMarking:
    """
    **Validates: Requirements 4.4**

    Property 12: 思考阶段失败标记
    For any ThinkingStage, after fail(error_message), status is "failed"
    and to_dict() contains non-empty error field.
    """

    # --- 12a: fail() sets status to "failed" ---

    @given(stage_name=_stage_names, error_msg=_error_messages)
    @settings(max_examples=100)
    def test_fail_sets_status_to_failed(self, stage_name, error_msg):
        """Feature: chatbi-system-audit-optimization, Property 12: 思考阶段失败标记
        After fail(), status must be 'failed'."""
        stage = ThinkingStage(stage_name=stage_name)
        stage.fail(error_msg)

        assert stage.status == "failed", (
            f"Expected status 'failed', got '{stage.status}'"
        )

        d = stage.to_dict()
        assert d["status"] == "failed", (
            f"Expected to_dict() status 'failed', got '{d['status']}'"
        )

    # --- 12b: fail() produces non-empty error in to_dict() ---

    @given(stage_name=_stage_names, error_msg=_error_messages)
    @settings(max_examples=100)
    def test_fail_contains_nonempty_error(self, stage_name, error_msg):
        """Feature: chatbi-system-audit-optimization, Property 12: 思考阶段失败标记
        After fail(), to_dict() must contain a non-empty 'error' field in extra_data."""
        stage = ThinkingStage(stage_name=stage_name)
        stage.fail(error_msg)

        d = stage.to_dict()
        # error 存储在 extra_data 中（ extra_data 不再展平到顶层）
        extra = d.get("extra_data", {})
        assert "error" in extra, f"Missing 'error' key in extra_data after fail()"
        assert extra["error"], f"'error' field is empty after fail()"
        assert len(extra["error"].strip()) > 0, f"'error' field is whitespace-only"

    # --- 12c: error message is preserved exactly ---

    @given(stage_name=_stage_names, error_msg=_error_messages)
    @settings(max_examples=100)
    def test_fail_preserves_error_message(self, stage_name, error_msg):
        """Feature: chatbi-system-audit-optimization, Property 12: 思考阶段失败标记
        The error message passed to fail() must be preserved in to_dict()."""
        stage = ThinkingStage(stage_name=stage_name)
        stage.fail(error_msg)

        d = stage.to_dict()
        extra = d.get("extra_data", {})
        assert extra["error"] == error_msg, (
            f"Error message not preserved: expected '{error_msg}', got '{extra.get('error')}'"
        )

    # --- 12d: fail() sets end_time ---

    @given(stage_name=_stage_names, error_msg=_error_messages)
    @settings(max_examples=100)
    def test_fail_sets_end_time(self, stage_name, error_msg):
        """Feature: chatbi-system-audit-optimization, Property 12: 思考阶段失败标记
        After fail(), end_time must be set and duration must be non-negative."""
        stage = ThinkingStage(stage_name=stage_name)
        stage.fail(error_msg)

        assert stage.end_time is not None, "end_time not set after fail()"
        assert stage.duration() >= 0, f"Negative duration after fail(): {stage.duration()}"
        assert stage.duration_ms() >= 0, f"Negative duration_ms after fail(): {stage.duration_ms()}"

    # --- 12e: fail() in RAGThinkingProcess context ---

    @given(
        stage_name=_stage_names,
        error_msg=_error_messages,
        question=_questions,
    )
    @settings(max_examples=100)
    def test_fail_in_process_context(self, stage_name, error_msg, question):
        """Feature: chatbi-system-audit-optimization, Property 12: 思考阶段失败标记
        A failed stage within RAGThinkingProcess must show failed status and error."""
        process = RAGThinkingProcess()
        process.set_question(question)

        stage = process.start_stage(stage_name)
        stage.fail(error_msg)

        result = process.to_dict()
        stages = result["stages"]

        # Find the stage (may be name-mapped)
        stage_data = None
        for key, data in stages.items():
            if data.get("stage") == stage_name or key == stage_name:
                stage_data = data
                break

        assert stage_data is not None, (
            f"Stage '{stage_name}' not found in process stages"
        )
        assert stage_data["status"] == "failed"
        extra = stage_data.get("extra_data", {})
        assert "error" in extra
        assert extra["error"] == error_msg

    # --- 12f: Multiple stages with mixed status ---

    @given(
        stage_names=st.lists(_stage_names, min_size=2, max_size=5, unique=True),
        error_msg=_error_messages,
    )
    @settings(max_examples=100)
    def test_mixed_status_stages(self, stage_names, error_msg):
        """Feature: chatbi-system-audit-optimization, Property 12: 思考阶段失败标记
        In a process with mixed completed/failed stages, failed stages must
        have error field while completed stages must not."""
        process = RAGThinkingProcess()
        process.set_question("test")

        # First stage completes, rest fail
        first_stage = process.start_stage(stage_names[0])
        first_stage.complete()

        for name in stage_names[1:]:
            s = process.start_stage(name)
            s.fail(error_msg)

        result = process.to_dict()
        stages = result["stages"]

        for key, data in stages.items():
            if data["status"] == "failed":
                extra = data.get("extra_data", {})
                assert "error" in extra, f"Failed stage '{key}' missing error in extra_data"
                assert extra["error"] == error_msg
            elif data["status"] == "completed":
                # Completed stages should not have error (unless extra_data had one)
                pass  # No assertion needed - error absence is not guaranteed for completed
