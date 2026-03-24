"""Property-based tests for DialogueStateTracker"""
import sys
import os

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path so that app modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.chat.thinking.dialogue_state import DialogueStateTracker, DialogueIntent


# ---------------------------------------------------------------------------

VALID_INTENTS = set(DialogueIntent)
VALID_INTENT_VALUES = {intent.value for intent in DialogueIntent}

# Reference patterns that _resolve_context_references should detect
CONTEXT_REF_WORDS = {
    'prev_result': ['上面的', '上述的', '刚才的', '之前的', '前面的'],
    'current_entity': ['这个', '这些', '它的', '它们的'],
    'same_condition': ['同样的', '一样的', '相同的'],
    'modify_condition': ['换一个', '换成', '改为'],
}

ALL_REF_WORDS = []
for words in CONTEXT_REF_WORDS.values():
    ALL_REF_WORDS.extend(words)

VALID_REF_TYPES = {'prev_result', 'current_entity', 'same_condition', 'modify_condition'}


_business_queries = [
    '查询销售额', '统计订单数量', '分析利润趋势',
    '显示客户数据', '预测下个月收入', '对比产品销售',
    '列出成本明细', '计算增长率', '展示库存报告',
    '帮我看看收入', '查询部门数据', '统计区域销售',
    '分析渠道效果', '显示产品排名', '预测未来趋势',
    '查询今年销售额', '统计上个月订单', '分析利润下降原因',
]

_business_query_strategy = st.sampled_from(_business_queries)

# Topic A: 销售/产品 domain
_topic_a_queries = [
    '查询产品销售额排名',
    '统计各产品线的销售数据',
    '分析产品销售趋势变化',
    '显示产品库存明细报告',
    '列出畅销产品排行榜',
]

# Topic B: 人事/员工 domain (completely different vocabulary)
_topic_b_queries = [
    '查看员工考勤记录',
    '统计各部门人员编制',
    '分析员工离职率变化',
    '显示招聘进度汇总',
    '列出培训课程安排',
]

_topic_a_strategy = st.sampled_from(_topic_a_queries)
_topic_b_strategy = st.sampled_from(_topic_b_queries)

# Strategy for context reference queries
_ref_word_strategy = st.sampled_from(ALL_REF_WORDS)
_query_suffixes = ['数据', '结果', '报告', '分析', '内容', '信息']
_query_suffix_strategy = st.sampled_from(_query_suffixes)


# ---------------------------------------------------------------------------

class TestDialogueHistoryMaintenanceProperty7:
    """
    **Validates: Requirements 11.1, 11.4**

    Property 7: 对话状态历史维护正确性
    For any N turns (N >= 1), DialogueStateTracker maintains history of length N,
    and get_dialogue_context(max_turns=K) returns min(N, K) recent questions.
    """

    @given(
        queries=st.lists(
            _business_query_strategy,
            min_size=1,
            max_size=10,
        ),
    )
    @settings(max_examples=100)
    def test_history_length_equals_turn_count(self, queries):
        """After N calls to track_turn(), the tracker should maintain
        exactly N turns in history."""
        tracker = DialogueStateTracker()

        for q in queries:
            tracker.track_turn(question=q)

        n = len(queries)
        assert len(tracker.turns) == n, (
            f"Expected {n} turns in history, got {len(tracker.turns)}"
        )

    @given(
        queries=st.lists(
            _business_query_strategy,
            min_size=1,
            max_size=10,
        ),
        max_turns=st.integers(min_value=1, max_value=15),
    )
    @settings(max_examples=100)
    def test_get_dialogue_context_returns_min_n_k_turns(self, queries, max_turns):
        """get_dialogue_context(max_turns=K) should return min(N, K) recent
        questions where N is total turns tracked."""
        tracker = DialogueStateTracker()

        for q in queries:
            tracker.track_turn(question=q)

        n = len(queries)
        context = tracker.get_dialogue_context(max_turns=max_turns)

        expected_count = min(n, max_turns)
        actual_count = len(context['recent_questions'])
        assert actual_count == expected_count, (
            f"Expected min({n}, {max_turns}) = {expected_count} recent questions, "
            f"got {actual_count}"
        )

    @given(
        queries=st.lists(
            _business_query_strategy,
            min_size=1,
            max_size=10,
        ),
    )
    @settings(max_examples=100)
    def test_track_turn_returns_correct_dialogue_length(self, queries):
        """Each track_turn() call should return the correct cumulative
        dialogue_length in its result."""
        tracker = DialogueStateTracker()

        for i, q in enumerate(queries):
            result = tracker.track_turn(question=q)
            expected_length = i + 1
            assert result['dialogue_length'] == expected_length, (
                f"At turn {i}, expected dialogue_length={expected_length}, "
                f"got {result['dialogue_length']}"
            )

    @given(
        queries=st.lists(
            _business_query_strategy,
            min_size=1,
            max_size=10,
        ),
    )
    @settings(max_examples=100)
    def test_track_turn_result_contains_required_fields(self, queries):
        """Each track_turn() result must contain intent, topic, entities,
        and context_references fields."""
        tracker = DialogueStateTracker()

        for q in queries:
            result = tracker.track_turn(question=q)

            required_fields = [
                'turn_index', 'intent', 'topic', 'entities',
                'context_references', 'dialogue_length',
            ]
            for field in required_fields:
                assert field in result, (
                    f"track_turn() result missing required field '{field}'"
                )
            assert result['intent'] in VALID_INTENT_VALUES, (
                f"Intent '{result['intent']}' not in valid set"
            )

    @given(
        queries=st.lists(
            _business_query_strategy,
            min_size=2,
            max_size=10,
        ),
        max_turns=st.integers(min_value=1, max_value=15),
    )
    @settings(max_examples=100)
    def test_context_recent_questions_are_most_recent(self, queries, max_turns):
        """get_dialogue_context() recent_questions should be the last
        min(N, K) questions in order."""
        tracker = DialogueStateTracker()

        for q in queries:
            tracker.track_turn(question=q)

        n = len(queries)
        context = tracker.get_dialogue_context(max_turns=max_turns)
        expected_count = min(n, max_turns)
        expected_questions = queries[-expected_count:]

        assert context['recent_questions'] == expected_questions, (
            f"Expected recent questions {expected_questions}, "
            f"got {context['recent_questions']}"
        )


# ---------------------------------------------------------------------------

class TestTopicSwitchDetectionProperty8:
    """
    **Validates: Requirements 11.2**

    Property 8: 话题切换检测
    When consecutive questions have completely different topics (no common
    keywords), topic change should be detected.
    """

    @given(
        topic_a=_topic_a_strategy,
        topic_b=_topic_b_strategy,
    )
    @settings(max_examples=100)
    def test_completely_different_topics_detected_as_switch(self, topic_a, topic_b):
        """When two consecutive turns have completely different topic words,
        _is_topic_switch() should return True."""
        tracker = DialogueStateTracker()

        # First turn establishes topic A
        tracker.track_turn(question=topic_a)

        # Check if topic B is detected as a switch
        is_switch = tracker._is_topic_switch(topic_b)

        assert is_switch is True, (
            f"Expected topic switch between '{topic_a}' and '{topic_b}', "
            f"but _is_topic_switch() returned False"
        )

    @given(query=_business_query_strategy)
    @settings(max_examples=100)
    def test_same_query_not_detected_as_switch(self, query):
        """When the same query is repeated, _is_topic_switch() should
        return False."""
        tracker = DialogueStateTracker()

        tracker.track_turn(question=query)

        is_switch = tracker._is_topic_switch(query)

        assert is_switch is False, (
            f"Same query '{query}' should not be detected as topic switch"
        )

    @given(
        topic_a=_topic_a_strategy,
        topic_b=_topic_b_strategy,
    )
    @settings(max_examples=100)
    def test_topic_switch_creates_new_topic_in_track_turn(self, topic_a, topic_b):
        """When track_turn detects a topic switch between completely different
        domains, the result should indicate topic_changed=True."""
        tracker = DialogueStateTracker()

        # First turn
        tracker.track_turn(question=topic_a)

        # Second turn with completely different topic
        result = tracker.track_turn(question=topic_b)

        # Should have at least 2 topics (one for each domain)
        assert len(tracker.topics) >= 2, (
            f"Expected at least 2 topics after switching from "
            f"'{topic_a}' to '{topic_b}', got {len(tracker.topics)}"
        )
        assert result['topic_changed'] is True, (
            f"Expected topic_changed=True when switching from "
            f"'{topic_a}' to '{topic_b}'"
        )


# ---------------------------------------------------------------------------

class TestContextReferenceResolutionProperty9:
    """
    **Validates: Requirements 11.3**

    Property 9: 上下文引用消解
    For questions with Chinese pronouns ("它的", "上面的", "这个", etc.) with
    prior history, _resolve_context_references() should return non-empty results.
    """

    @given(
        ref_word=_ref_word_strategy,
        suffix=_query_suffix_strategy,
    )
    @settings(max_examples=100)
    def test_reference_words_return_non_empty_results(self, ref_word, suffix):
        """Queries containing Chinese pronoun references with prior history
        should produce non-empty resolution results."""
        tracker = DialogueStateTracker()

        # Add history so references have context to resolve against
        tracker.track_turn(
            question="查询销售额数据",
            sql="SELECT SUM(amount) FROM sales",
        )

        query = f"{ref_word}{suffix}"
        refs = tracker._resolve_context_references(query)

        assert isinstance(refs, list), f"Expected list, got {type(refs)}"
        assert len(refs) > 0, (
            f"Query '{query}' contains reference word '{ref_word}' but "
            f"_resolve_context_references() returned empty list"
        )

    @given(
        ref_word=_ref_word_strategy,
        suffix=_query_suffix_strategy,
    )
    @settings(max_examples=100)
    def test_each_reference_has_required_fields(self, ref_word, suffix):
        """Each resolved reference must contain 'type', 'pattern', and
        'resolved' fields."""
        tracker = DialogueStateTracker()
        tracker.track_turn(
            question="查询产品销售数据",
            sql="SELECT * FROM products",
        )

        query = f"{ref_word}{suffix}"
        refs = tracker._resolve_context_references(query)

        for i, ref in enumerate(refs):
            assert 'type' in ref, f"Reference [{i}] missing 'type': {ref}"
            assert 'pattern' in ref, f"Reference [{i}] missing 'pattern': {ref}"
            assert 'resolved' in ref, f"Reference [{i}] missing 'resolved': {ref}"
            assert ref['type'] in VALID_REF_TYPES, (
                f"Reference [{i}] type '{ref['type']}' not in {VALID_REF_TYPES}"
            )

    @given(
        ref_word=_ref_word_strategy,
        suffix=_query_suffix_strategy,
    )
    @settings(max_examples=100)
    def test_resolved_content_is_non_empty_with_history(self, ref_word, suffix):
        """With prior history containing SQL, resolved references should
        have non-empty 'resolved' content."""
        tracker = DialogueStateTracker()
        tracker.track_turn(
            question="统计订单数量",
            sql="SELECT COUNT(*) FROM orders",
        )

        query = f"{ref_word}{suffix}"
        refs = tracker._resolve_context_references(query)

        # At least one reference should have non-empty resolved content
        has_resolved = any(ref.get('resolved', '') != '' for ref in refs)
        assert has_resolved, (
            f"Expected at least one reference with non-empty 'resolved' "
            f"for query '{query}', got: {refs}"
        )

    @given(suffix=_query_suffix_strategy)
    @settings(max_examples=100)
    def test_no_reference_words_returns_empty(self, suffix):
        """Queries without any reference words should return an empty list."""
        tracker = DialogueStateTracker()
        tracker.track_turn(question="查询销售额")

        query = f"查询最新{suffix}"
        assume(not any(rw in query for rw in ALL_REF_WORDS))

        refs = tracker._resolve_context_references(query)

        assert isinstance(refs, list), f"Expected list, got {type(refs)}"
        assert len(refs) == 0, (
            f"Query '{query}' has no reference words but got refs: {refs}"
        )
