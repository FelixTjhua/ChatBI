"""Property-based tests for RateLimitMiddleware."""
import time
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from common.middleware.rate_limiter import RateLimitMiddleware


_rate_limits = st.integers(min_value=1, max_value=20)

# Window size fixed at 60 seconds per requirement
_window = 60

# Number of requests to send (slightly above max possible limit)
_request_counts = st.integers(min_value=1, max_value=30)

# Client keys: simulate different users/IPs
_client_keys = st.sampled_from([
    "192.168.1.1:user1",
    "10.0.0.5:user2",
    "172.16.0.1:",
    "unknown:user3",
    "127.0.0.1:admin",
])

# Endpoint types
_is_llm_flags = st.booleans()


# ---------------------------------------------------------------------------

def _fresh_middleware(llm_rate: int = 10, api_rate: int = 60, window: int = 60) -> RateLimitMiddleware:
    """Create a fresh RateLimitMiddleware instance with empty counters."""
    # BaseHTTPMiddleware requires an app; we pass a dummy since we test internals
    dummy_app = MagicMock()
    mw = RateLimitMiddleware(dummy_app, llm_rate=llm_rate, api_rate=api_rate, window=window)
    return mw


# ---------------------------------------------------------------------------

class TestRateLimitProperty18:
    """
    **Validates: Requirements 11.2**

    Property 18: 频率限制
    验证在 60 秒窗口内超过限制次数的请求返回 HTTP 429，
    且在限制次数内的请求全部被接受。
    """

    @given(rate_limit=_rate_limits, n_requests=_request_counts, client_key=_client_keys)
    @settings(max_examples=100)
    def test_requests_within_limit_accepted(self, rate_limit, n_requests, client_key):
        """All requests within the rate limit should be accepted (not rate-limited).

        Given a rate limit L and N requests where N <= L,
        every call to _is_rate_limited should return False.
        """
        assume(n_requests <= rate_limit)

        mw = _fresh_middleware(llm_rate=rate_limit, api_rate=rate_limit, window=_window)

        for i in range(n_requests):
            result = mw._is_rate_limited(client_key, is_llm=True)
            assert result is False, (
                f"Request {i + 1}/{n_requests} was rate-limited but limit is {rate_limit}. "
                f"Should accept all {n_requests} requests within limit."
            )

    @given(rate_limit=_rate_limits, extra_requests=st.integers(min_value=1, max_value=10), client_key=_client_keys)
    @settings(max_examples=100)
    def test_requests_exceeding_limit_rejected(self, rate_limit, extra_requests, client_key):
        """The (limit+1)th and subsequent requests within the window should be rejected (HTTP 429).

        Given a rate limit L, after L accepted requests, the next `extra_requests`
        calls should all return True (rate-limited / 429).
        """
        mw = _fresh_middleware(llm_rate=rate_limit, api_rate=rate_limit, window=_window)

        # First, exhaust the limit — all should be accepted
        for i in range(rate_limit):
            result = mw._is_rate_limited(client_key, is_llm=True)
            assert result is False, (
                f"Request {i + 1}/{rate_limit} was unexpectedly rate-limited"
            )

        # Now, additional requests should be rejected
        for i in range(extra_requests):
            result = mw._is_rate_limited(client_key, is_llm=True)
            assert result is True, (
                f"Extra request {i + 1} after limit ({rate_limit}) should be rate-limited (429), "
                f"but was accepted."
            )

    @given(rate_limit=_rate_limits, client_key=_client_keys, is_llm=_is_llm_flags)
    @settings(max_examples=100)
    def test_window_expiry_resets_counter(self, rate_limit, client_key, is_llm):
        """After the time window expires, the counter resets and requests are accepted again.

        This verifies the 60-second window boundary behavior.
        """
        mw = _fresh_middleware(llm_rate=rate_limit, api_rate=rate_limit, window=_window)

        # Exhaust the limit
        for _ in range(rate_limit):
            mw._is_rate_limited(client_key, is_llm=is_llm)

        # Verify we're rate-limited
        assert mw._is_rate_limited(client_key, is_llm=is_llm) is True

        # Simulate window expiry by manipulating the stored timestamp
        counters = mw._llm_counters if is_llm else mw._api_counters
        count, window_start = counters[client_key]
        # Move window_start back beyond the window duration
        counters[client_key] = (count, window_start - _window - 1)

        # After window expiry, the next request should be accepted
        result = mw._is_rate_limited(client_key, is_llm=is_llm)
        assert result is False, (
            "After window expiry, request should be accepted but was rate-limited"
        )

    @given(
        llm_rate=_rate_limits,
        api_rate=_rate_limits,
        client_key=_client_keys,
    )
    @settings(max_examples=100)
    def test_llm_and_api_limits_independent(self, llm_rate, api_rate, client_key):
        """LLM and API rate limits are tracked independently.

        Exhausting the LLM limit should not affect the API limit and vice versa.
        """
        mw = _fresh_middleware(llm_rate=llm_rate, api_rate=api_rate, window=_window)

        # Exhaust LLM limit
        for _ in range(llm_rate):
            mw._is_rate_limited(client_key, is_llm=True)

        # LLM should be rate-limited
        assert mw._is_rate_limited(client_key, is_llm=True) is True

        # API should still be available (independent counter)
        result = mw._is_rate_limited(client_key, is_llm=False)
        assert result is False, (
            "API requests should not be affected by LLM rate limit exhaustion"
        )

    @given(
        rate_limit=_rate_limits,
        keys=st.lists(
            st.sampled_from(["10.0.0.1:u1", "10.0.0.2:u2", "10.0.0.3:u3"]),
            min_size=2,
            max_size=3,
            unique=True,
        ),
    )
    @settings(max_examples=100)
    def test_different_clients_independent(self, rate_limit, keys):
        """Rate limits are per-client — exhausting one client's limit doesn't affect others."""
        mw = _fresh_middleware(llm_rate=rate_limit, api_rate=rate_limit, window=_window)

        # Exhaust limit for first client
        first_key = keys[0]
        for _ in range(rate_limit):
            mw._is_rate_limited(first_key, is_llm=True)
        assert mw._is_rate_limited(first_key, is_llm=True) is True

        # Other clients should still be accepted
        for other_key in keys[1:]:
            result = mw._is_rate_limited(other_key, is_llm=True)
            assert result is False, (
                f"Client {other_key} should not be affected by {first_key}'s rate limit"
            )
