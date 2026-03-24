"""Property-based tests for Prompt Construction and Pipeline Data Integrity."""
import sys
import os

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path so that app modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.chat.thinking.rag_thinking import RAGThinkingProcess
from apps.chat.thinking.thinking_integration import record_prompt_construction_stage
from apps.chat.thinking.query_rewriter import QueryRewriter

_terminology_st = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'), min_codepoint=0x4e00, max_codepoint=0x9fff),
        min_size=1,
        max_size=20,
    ),
    min_size=0,
    max_size=5,
).map(lambda terms: '\n'.join(
    f'<terminology>{t}</terminology>' for t in terms
) if terms else '')

# Strategy for generating SQL example XML strings
_sql_example_st = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
        min_size=1,
        max_size=30,
    ),
    min_size=0,
    max_size=3,
).map(lambda examples: '\n'.join(
    f'<sql-example>{e}</sql-example>' for e in examples
) if examples else '')

# Strategy for schema strings
_schema_st = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
    min_size=0,
    max_size=200,
)

# Strategy for prompt types
_prompt_type_st = st.sampled_from(['sql_generation', 'direct_answer', 'analysis', 'prediction'])

# Strategy for model names
_model_name_st = st.sampled_from(['deepseek-chat', 'gpt-4o', 'qwen-plus', 'chatglm-4', ''])

# Strategy for non-empty Chinese question strings
_chinese_question_st = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'), min_codepoint=0x4e00, max_codepoint=0x9fff),
    min_size=2,
    max_size=100,
)

# Strategy for mixed question strings (Chinese + ASCII)
_question_st = st.one_of(
    _chinese_question_st,
    st.text(min_size=2, max_size=100).filter(lambda s: s.strip()),
)

# Strategy for terminology dicts (for QueryRewriter)
_terminology_dict_st = st.fixed_dictionaries({
    'word': st.text(min_size=1, max_size=10),
    'description': st.text(min_size=0, max_size=50),
    'sql_mapping': st.text(min_size=0, max_size=30),
    'similarity': st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
})


# ---------------------------------------------------------------------------

class TestProperty21RAGContextInjection:
    """Feature: chatbi-system-audit-optimization, Property 21: RAG 上下文注入提示词"""

    @settings(max_examples=100)
    @given(
        terminologies=_terminology_st,
        sql_examples=_sql_example_st,
        schema=_schema_st,
        prompt_type=_prompt_type_st,
        model_name=_model_name_st,
    )
    def test_prompt_construction_records_all_rag_components(
        self, terminologies, sql_examples, schema, prompt_type, model_name
    ):
        """record_prompt_construction_stage should record all RAG component injection
        status and counts in the thinking process."""

        thinking = RAGThinkingProcess()
        thinking.set_question("测试问题")
        thinking.set_rag_enabled(True)

        # Build rag_components dict (boolean flags)
        rag_components = {
            'schema': bool(schema),
            'terminologies': bool(terminologies),
            'sql_examples': bool(sql_examples),
            'custom_prompt': False,
            'dialogue_context': False,
        }

        # Count actual components
        term_count = terminologies.count('<terminology>') if terminologies else 0
        example_count = sql_examples.count('<sql-example>') if sql_examples else 0

        component_counts = {
            'terminology_count': term_count,
            'sql_example_count': example_count,
            'schema_length': len(schema) if schema else 0,
        }

        # Build a fake system prompt that includes all RAG components
        sys_prompt = f"Schema: {schema}\nTerminologies: {terminologies}\nSQL Examples: {sql_examples}"
        user_prompt = "请生成SQL查询"
        total_len = len(sys_prompt) + len(user_prompt)

        record_prompt_construction_stage(
            thinking=thinking,
            prompt_type=prompt_type,
            system_prompt_preview=sys_prompt,
            user_prompt_preview=user_prompt,
            model_name=model_name,
            rag_components=rag_components,
            message_count=2,
            total_prompt_length=total_len,
            component_counts=component_counts,
        )

        # Verify the stage was recorded
        stage_data = thinking.get_stage('prompt_construction')
        assert stage_data is not None, "prompt_construction stage should be recorded"
        assert stage_data['status'] == 'completed', "Stage should be completed"

        # get_stage() 返回 to_dict()，数据在 extra_data 中
        extra = stage_data.get('extra_data', {})

        # Verify rag_components are recorded correctly
        recorded_rc = extra.get('rag_components', {})
        assert recorded_rc.get('schema') == bool(schema)
        assert recorded_rc.get('terminologies') == bool(terminologies)
        assert recorded_rc.get('sql_examples') == bool(sql_examples)

        # Verify component_counts are recorded
        recorded_cc = extra.get('component_counts', {})
        assert recorded_cc.get('terminology_count') == term_count
        assert recorded_cc.get('sql_example_count') == example_count
        assert recorded_cc.get('schema_length') == (len(schema) if schema else 0)

        # Verify prompt type and model name
        assert extra.get('prompt_type') == prompt_type
        assert extra.get('model_name') == model_name

        # Verify prompt previews exist
        assert extra.get('system_prompt_preview') is not None
        assert extra.get('user_prompt_preview') is not None

        # Verify total_prompt_length is recorded
        assert extra.get('total_prompt_length') == total_len

    @settings(max_examples=100)
    @given(
        has_schema=st.booleans(),
        has_terms=st.booleans(),
        has_examples=st.booleans(),
        has_custom=st.booleans(),
        has_dialogue=st.booleans(),
    )
    def test_rag_component_boolean_flags_match_presence(
        self, has_schema, has_terms, has_examples, has_custom, has_dialogue
    ):
        """The rag_components boolean flags should accurately reflect whether
        each RAG component is present (non-empty) in the prompt."""

        thinking = RAGThinkingProcess()
        thinking.set_question("测试")
        thinking.set_rag_enabled(True)

        rag_components = {
            'schema': has_schema,
            'terminologies': has_terms,
            'sql_examples': has_examples,
            'custom_prompt': has_custom,
            'dialogue_context': has_dialogue,
        }

        record_prompt_construction_stage(
            thinking=thinking,
            prompt_type='sql_generation',
            system_prompt_preview='test prompt',
            user_prompt_preview='test user',
            model_name='test-model',
            rag_components=rag_components,
            message_count=2,
            total_prompt_length=100,
        )

        stage_data = thinking.get_stage('prompt_construction')
        assert stage_data is not None

        extra = stage_data.get('extra_data', {})
        recorded_rc = extra.get('rag_components', {})
        # Each flag should be preserved exactly
        for key in ['schema', 'terminologies', 'sql_examples', 'custom_prompt', 'dialogue_context']:
            assert recorded_rc.get(key) == rag_components[key], \
                f"rag_components['{key}'] should be {rag_components[key]}, got {recorded_rc.get(key)}"


# ---------------------------------------------------------------------------

class TestProperty22PipelineDataIntegrity:
    """Feature: chatbi-system-audit-optimization, Property 22: 管道数据完整性"""

    @settings(max_examples=100)
    @given(question=_question_st)
    def test_query_rewrite_output_fields_complete(self, question):
        """QueryRewriter.rewrite() should always return all required fields
        that downstream stages depend on."""
        assume(question.strip())

        result = QueryRewriter.rewrite(question)

        # All required fields must be present
        required_fields = ['original', 'rewritten', 'expanded_queries', 'extracted_keywords', 'intent', 'rewrite_applied']
        for field in required_fields:
            assert field in result, f"Missing required field '{field}' in rewrite result"

        # Type checks
        assert isinstance(result['original'], str)
        assert isinstance(result['rewritten'], str)
        assert isinstance(result['expanded_queries'], list)
        assert isinstance(result['extracted_keywords'], list)
        assert isinstance(result['intent'], str)
        assert isinstance(result['rewrite_applied'], bool)

        # rewritten_query should be non-empty for non-empty input
        assert result['rewritten'], "rewritten query should not be empty for non-empty input"

        # original should match the stripped input
        assert result['original'] == question.strip()

    @settings(max_examples=100)
    @given(
        question=_question_st,
        terminologies=st.lists(_terminology_dict_st, min_size=0, max_size=5),
    )
    def test_rewrite_result_preserves_data_for_downstream(self, question, terminologies):
        """The rewrite result should contain all data needed by downstream stages
        (RAG retrieval and SQL generation) without field loss."""
        assume(question.strip())

        result = QueryRewriter.rewrite(question, terminologies=terminologies)

        # The rewritten query is used as retrieval_question for RAG
        retrieval_question = result['rewritten']
        assert retrieval_question, "retrieval_question (rewritten) must not be empty"

        # expanded_queries are used for multi-path retrieval
        expanded_queries = result['expanded_queries']
        assert isinstance(expanded_queries, list)
        # Each expanded query should be a non-empty string
        for eq in expanded_queries:
            assert isinstance(eq, str)
            assert eq.strip(), "Each expanded query should be non-empty"

        # intent is used for routing (data_query, prediction, etc.)
        intent = result['intent']
        assert intent, "intent must not be empty"

        # keywords are used for context compression relevance scoring
        keywords = result['extracted_keywords']
        assert isinstance(keywords, list)

    @settings(max_examples=100)
    @given(
        terminologies=_terminology_st,
        sql_examples=_sql_example_st,
        schema=_schema_st,
    )
    def test_pipeline_data_preserved_through_prompt_construction(
        self, terminologies, sql_examples, schema
    ):
        """When RAG data (terminologies, sql_examples, schema) flows through
        the pipeline to prompt construction, all data should be preserved
        in the thinking process record."""

        thinking = RAGThinkingProcess()
        thinking.set_question("pipeline test")
        thinking.set_rag_enabled(True)

        # Simulate the pipeline: data flows from RAG retrieval to prompt construction
        # Count components before recording
        term_count = terminologies.count('<terminology>') if terminologies else 0
        example_count = sql_examples.count('<sql-example>') if sql_examples else 0

        rag_components = {
            'schema': bool(schema),
            'terminologies': bool(terminologies),
            'sql_examples': bool(sql_examples),
            'custom_prompt': False,
            'dialogue_context': False,
        }

        component_counts = {
            'terminology_count': term_count,
            'sql_example_count': example_count,
            'schema_length': len(schema) if schema else 0,
        }

        record_prompt_construction_stage(
            thinking=thinking,
            prompt_type='sql_generation',
            system_prompt_preview=f"Schema:{schema} Terms:{terminologies} Examples:{sql_examples}",
            user_prompt_preview="test",
            rag_components=rag_components,
            component_counts=component_counts,
            message_count=2,
            total_prompt_length=100,
        )

        stage_data = thinking.get_stage('prompt_construction')
        assert stage_data is not None

        # get_stage() 返回 to_dict()，数据在 extra_data 中
        extra = stage_data.get('extra_data', {})

        # Verify data integrity: counts match what was passed in
        cc = extra.get('component_counts', {})
        assert cc.get('terminology_count') == term_count, \
            f"terminology_count mismatch: expected {term_count}, got {cc.get('terminology_count')}"
        assert cc.get('sql_example_count') == example_count, \
            f"sql_example_count mismatch: expected {example_count}, got {cc.get('sql_example_count')}"

        # Verify boolean flags match
        rc = extra.get('rag_components', {})
        assert rc.get('schema') == bool(schema)
        assert rc.get('terminologies') == bool(terminologies)
        assert rc.get('sql_examples') == bool(sql_examples)

    @settings(max_examples=100)
    @given(question=_question_st)
    def test_rewrite_idempotent_field_structure(self, question):
        """Calling rewrite() multiple times on the same input should always
        produce results with the same field structure."""
        assume(question.strip())

        result1 = QueryRewriter.rewrite(question)
        result2 = QueryRewriter.rewrite(question)

        # Same fields present
        assert set(result1.keys()) == set(result2.keys())

        # Same types
        for key in result1:
            assert type(result1[key]) == type(result2[key]), \
                f"Type mismatch for field '{key}': {type(result1[key])} vs {type(result2[key])}"

        # Deterministic: same input → same output
        assert result1['rewritten'] == result2['rewritten']
        assert result1['intent'] == result2['intent']
        assert result1['rewrite_applied'] == result2['rewrite_applied']
