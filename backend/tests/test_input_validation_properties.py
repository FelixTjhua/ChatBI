"""Property-based tests for input validation."""
import sys
import os
import re

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.utils.input_validator import validate_chat_input, MAX_INPUT_LENGTH


_whitespace_chars = st.sampled_from([' ', '\t', '\n', '\r', '\u3000', '\xa0'])
_pure_whitespace = st.lists(
    _whitespace_chars, min_size=1, max_size=50
).map(lambda chars: ''.join(chars))

# Pure special character strings (no letters, digits, or CJK)
# Note: underscore '_' is excluded because \w matches it as a word character
_special_chars = st.sampled_from(list('!@#$%^&*()+-=[]{}|;:\'",.<>?/~`\\'))
_pure_special = st.lists(
    _special_chars, min_size=1, max_size=50
).map(lambda chars: ''.join(chars))

# Over-length strings (> 2000 chars)
# 排除空格字符，避免 strip() 后长度降到 2000 导致测试误判
_over_length = st.text(
    alphabet=st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789'),
    min_size=MAX_INPUT_LENGTH + 1,
    max_size=MAX_INPUT_LENGTH + 500,
)

# Valid input strings (contain at least one meaningful character, within length)
_valid_chinese = st.sampled_from([
    '查询销售数据', '今年的利润是多少', '分析趋势',
    '对比各部门业绩', '预测下个月销量', '你好',
    '帮我看看这个数据', '统计一下总数',
])

_valid_english = st.sampled_from([
    'show sales data', 'what is the total revenue',
    'compare departments', 'hello', 'help me analyze',
])

_valid_mixed = st.text(
    alphabet=st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789 '),
    min_size=1,
    max_size=200,
).filter(lambda s: s.strip() and re.search(r'[\w]', s))


# ---------------------------------------------------------------------------

class TestInputValidationProperty14:
    """
    **Validates: Requirements 3.1, 3.2**

    Property 14: 输入验证拒绝无效输入
    For any pure whitespace or pure special character string, and any string
    over 2000 chars, input validation should reject and return friendly message.
    """

    # --- 14a: Pure whitespace is rejected ---

    @given(ws=_pure_whitespace)
    @settings(max_examples=100)
    def test_pure_whitespace_rejected(self, ws):
        """Feature: chatbi-system-audit-optimization, Property 14: 输入验证拒绝无效输入
        Pure whitespace strings must be rejected."""
        is_valid, message = validate_chat_input(ws)
        assert not is_valid, (
            f"Pure whitespace should be rejected: input={ws!r}"
        )
        assert len(message) > 0, "Rejection must include a friendly message"

    # --- 14b: None and empty string are rejected ---

    @given(empty=st.sampled_from([None, '', '   ', '\t\n']))
    @settings(max_examples=10)
    def test_none_and_empty_rejected(self, empty):
        """Feature: chatbi-system-audit-optimization, Property 14: 输入验证拒绝无效输入
        None and empty strings must be rejected."""
        is_valid, message = validate_chat_input(empty)
        assert not is_valid
        assert len(message) > 0

    # --- 14c: Pure special characters are rejected ---

    @given(special=_pure_special)
    @settings(max_examples=100)
    def test_pure_special_chars_rejected(self, special):
        """Feature: chatbi-system-audit-optimization, Property 14: 输入验证拒绝无效输入
        Pure special character strings must be rejected."""
        is_valid, message = validate_chat_input(special)
        assert not is_valid, (
            f"Pure special chars should be rejected: input={special!r}"
        )
        assert len(message) > 0, "Rejection must include a friendly message"

    # --- 14d: Over-length strings are rejected ---

    @given(long_text=_over_length)
    @settings(max_examples=100)
    def test_over_length_rejected(self, long_text):
        """Feature: chatbi-system-audit-optimization, Property 14: 输入验证拒绝无效输入
        Strings over 2000 characters must be rejected."""
        is_valid, message = validate_chat_input(long_text)
        assert not is_valid, (
            f"Over-length input ({len(long_text)} chars) should be rejected"
        )
        assert len(message) > 0, "Rejection must include a friendly message"
        assert str(MAX_INPUT_LENGTH) in message, (
            f"Message should mention the max length ({MAX_INPUT_LENGTH})"
        )

    # --- 14e: Valid Chinese inputs are accepted ---

    @given(question=_valid_chinese)
    @settings(max_examples=100)
    def test_valid_chinese_accepted(self, question):
        """Feature: chatbi-system-audit-optimization, Property 14: 输入验证拒绝无效输入
        Valid Chinese question strings must be accepted."""
        is_valid, message = validate_chat_input(question)
        assert is_valid, (
            f"Valid Chinese input should be accepted: input={question!r}, msg={message}"
        )
        assert message == ""

    # --- 14f: Valid English inputs are accepted ---

    @given(question=_valid_english)
    @settings(max_examples=100)
    def test_valid_english_accepted(self, question):
        """Feature: chatbi-system-audit-optimization, Property 14: 输入验证拒绝无效输入
        Valid English question strings must be accepted."""
        is_valid, message = validate_chat_input(question)
        assert is_valid, (
            f"Valid English input should be accepted: input={question!r}, msg={message}"
        )
        assert message == ""

    # --- 14g: Valid mixed alphanumeric inputs are accepted ---

    @given(question=_valid_mixed)
    @settings(max_examples=100)
    def test_valid_mixed_accepted(self, question):
        """Feature: chatbi-system-audit-optimization, Property 14: 输入验证拒绝无效输入
        Valid mixed alphanumeric inputs within length limit must be accepted."""
        assume(len(question.strip()) <= MAX_INPUT_LENGTH)
        is_valid, message = validate_chat_input(question)
        assert is_valid, (
            f"Valid mixed input should be accepted: input={question!r}, msg={message}"
        )

    # --- 14h: Friendly message is always non-empty on rejection ---

    @given(invalid=st.one_of(_pure_whitespace, _pure_special, _over_length, st.just(None), st.just('')))
    @settings(max_examples=100)
    def test_rejection_always_has_friendly_message(self, invalid):
        """Feature: chatbi-system-audit-optimization, Property 14: 输入验证拒绝无效输入
        Every rejected input must return a non-empty friendly message."""
        is_valid, message = validate_chat_input(invalid)
        if not is_valid:
            assert isinstance(message, str)
            assert len(message) > 0, "Friendly message must be non-empty"
