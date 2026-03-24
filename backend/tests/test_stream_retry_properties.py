"""Property-based tests for stream_with_retry() retry mechanism."""
import sys
import os
import time
import types
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_heavy_modules = [
    "langchain", "langchain.chat_models", "langchain.chat_models.base",
    "langchain_community", "langchain_community.utilities",
    "langchain_core", "langchain_core.messages",
    "langchain_openai",
    "apps.ai_model.model_factory",
    "apps.chat.crud.chat",
    "apps.chat.models.chat_model",
    "apps.chat.thinking.rag_thinking",
    "apps.chat.thinking.thinking_integration",
    "apps.chat.thinking.query_rewriter",
    "apps.chat.thinking.context_compressor",
    "apps.chat.thinking.rag_evidence_filter",
    "apps.chat.thinking.rag_evaluator",
    "apps.chat.thinking.dialogue_state",
    "apps.data_training.crud.data_training",
    "apps.datasource.crud.datasource",
    "apps.datasource.crud.permission",
    "apps.datasource.embedding.ds_embedding",
    "apps.datasource.models.datasource",
    "apps.datasource.models",
    "apps.db.db",
    "apps.system.schemas.system_schema",
    "apps.system.crud.assistant",
    "apps.system.crud.ai_model",
    "apps.terminology.crud.terminology",
    "common.chatbi.custom_prompt",
    "common.chatbi.license",
    "common.core.db",
    "dicttoxml",
    "sqlparse",
    "pandas",
]
for mod_name in _heavy_modules:
    sys.modules.setdefault(mod_name, MagicMock())

from apps.chat.task.llm import stream_with_retry


_max_retries = st.integers(min_value=0, max_value=5)

# Retryable error messages — contain keywords that stream_with_retry treats as transient
_retryable_errors = st.sampled_from([
    "Connection timeout occurred",
    "rate limit exceeded",
    "too many requests",
    "HTTP 429 response",
    "HTTP 503 service unavailable",
    "HTTP 502 bad gateway",
    "connection reset by peer",
    "connection refused",
    "service temporarily unavailable",
])

# Non-retryable error messages — permanent errors that should NOT be retried
_non_retryable_errors = st.sampled_from([
    "Invalid API key",
    "Model not found",
    "Invalid request parameters",
    "Authentication failed",
    "Permission denied",
    "Unsupported model version",
    "Malformed input payload",
])


# ---------------------------------------------------------------------------

def _make_llm_always_fails(error_msg: str) -> tuple[MagicMock, list]:
    """Create a mock LLM whose .stream() always raises with the given message.

    Returns (mock_llm, call_log) where call_log tracks each invocation.
    """
    call_log: list[int] = []
    mock_llm = MagicMock()

    def _stream_side_effect(messages):
        call_log.append(1)
        raise Exception(error_msg)

    mock_llm.stream.side_effect = _stream_side_effect
    return mock_llm, call_log


def _make_llm_fails_then_succeeds(error_msg: str, fail_count: int) -> tuple[MagicMock, list]:
    """Create a mock LLM that fails `fail_count` times then succeeds.

    Returns (mock_llm, call_log).
    """
    call_log: list[int] = []
    mock_llm = MagicMock()
    state = {"calls": 0}

    def _stream_side_effect(messages):
        call_log.append(1)
        state["calls"] += 1
        if state["calls"] <= fail_count:
            raise Exception(error_msg)
        # Success: yield some chunks
        return iter(["chunk1", "chunk2"])

    mock_llm.stream.side_effect = _stream_side_effect
    return mock_llm, call_log


# ---------------------------------------------------------------------------

class TestStreamRetryProperty15:
    """
    **Validates: Requirements 3.5**

    Property 15: LLM 调用重试机制
    验证 stream_with_retry() 的总调用次数 ≤ max_retries + 1，
    且不可重试错误只调用一次。
    """

    @given(max_retries=_max_retries, error_msg=_retryable_errors)
    @settings(max_examples=100)
    @patch("apps.chat.task.llm.time.sleep", return_value=None)
    def test_retryable_error_call_count_bounded(self, mock_sleep, max_retries, error_msg):
        """With retryable errors, total .stream() calls ≤ max_retries + 1."""
        mock_llm, call_log = _make_llm_always_fails(error_msg)
        messages = [{"role": "user", "content": "test"}]

        # Exhaust the generator — stream_with_retry is a generator
        with pytest.raises(Exception):
            for _ in stream_with_retry(mock_llm, messages, max_retries=max_retries, retry_delay=0.0):
                pass

        assert len(call_log) <= max_retries + 1, (
            f"Expected at most {max_retries + 1} calls, got {len(call_log)} "
            f"(max_retries={max_retries}, error='{error_msg}')"
        )
        # Should use exactly max_retries + 1 attempts for always-failing retryable errors
        assert len(call_log) == max_retries + 1, (
            f"Expected exactly {max_retries + 1} calls for always-failing retryable error, "
            f"got {len(call_log)}"
        )

    @given(max_retries=_max_retries, error_msg=_non_retryable_errors)
    @settings(max_examples=100)
    @patch("apps.chat.task.llm.time.sleep", return_value=None)
    def test_non_retryable_error_no_retry(self, mock_sleep, max_retries, error_msg):
        """Non-retryable errors should cause exactly 1 call (no retries)."""
        mock_llm, call_log = _make_llm_always_fails(error_msg)
        messages = [{"role": "user", "content": "test"}]

        with pytest.raises(Exception):
            for _ in stream_with_retry(mock_llm, messages, max_retries=max_retries, retry_delay=0.0):
                pass

        assert len(call_log) == 1, (
            f"Non-retryable error should cause exactly 1 call, got {len(call_log)} "
            f"(error='{error_msg}')"
        )

    @given(
        max_retries=st.integers(min_value=1, max_value=5),
        error_msg=_retryable_errors,
        fail_count=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100)
    @patch("apps.chat.task.llm.time.sleep", return_value=None)
    def test_recovery_after_transient_failures(self, mock_sleep, max_retries, error_msg, fail_count):
        """When failures < max_retries, the function recovers and total calls ≤ max_retries + 1."""
        assume(fail_count <= max_retries)  # ensure recovery is possible

        mock_llm, call_log = _make_llm_fails_then_succeeds(error_msg, fail_count)
        messages = [{"role": "user", "content": "test"}]

        chunks = list(stream_with_retry(mock_llm, messages, max_retries=max_retries, retry_delay=0.0))

        assert len(call_log) <= max_retries + 1, (
            f"Expected at most {max_retries + 1} calls, got {len(call_log)}"
        )
        assert len(call_log) == fail_count + 1, (
            f"Expected {fail_count + 1} calls (fail_count={fail_count} + 1 success), "
            f"got {len(call_log)}"
        )
        assert len(chunks) > 0, "Should have received chunks after recovery"
