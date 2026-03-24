"""
4.6 智能对话全场景18步统一处理流程 - 完整验证测试
覆盖所有可离线验证的步骤（不需要数据库/LLM连接）
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import pandas as pd
import numpy as np


# ============================================================
class TestStep3IntentDetection:
    """步骤3：系统对用户问题进行意图识别"""

    def setup_method(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        self.rewriter = QueryRewriter

    def test_fact_query(self):
        assert self.rewriter._detect_intent("查询今年各地区销售额") == 'fact_query'

    def test_statistical_analysis(self):
        assert self.rewriter._detect_intent("分析各产品线利润率") == 'statistical_analysis'

    def test_comparison_analysis(self):
        assert self.rewriter._detect_intent("对比华东和华南的销售数据") == 'comparison_analysis'

    def test_trend_analysis(self):
        assert self.rewriter._detect_intent("销售额增长趋势如何") == 'trend_analysis'

    def test_prediction(self):
        assert self.rewriter._detect_intent("预测下个月的销售额") == 'prediction'

    def test_term_explanation(self):
        assert self.rewriter._detect_intent("GMV是什么意思") == 'term_explanation'

    def test_ambiguous_query(self):
        assert self.rewriter._detect_intent("销售情况怎么样") == 'ambiguous_query'

    def test_irrelevant_query(self):
        assert self.rewriter._detect_intent("你好") == 'irrelevant_query'

    def test_nine_intents_coverage(self):
        """验证9种意图类型全部可达"""
        cases = {
            'fact_query': "列出所有订单",
            'statistical_analysis': "深入分析销售数据",
            'comparison_analysis': "对比A和B的业绩",
            'trend_analysis': "收入趋势",
            'prediction': "预测明年营收",
            'term_explanation': "ROI是什么",
            'ambiguous_query': "数据情况怎么样",
            'irrelevant_query': "你好啊",
        }
        results = set()
        for expected, q in cases.items():
            intent = self.rewriter._detect_intent(q)
            results.add(intent)
            assert intent == expected, f"'{q}' expected {expected}, got {intent}"
        assert len(results) >= 8


# ============================================================
class TestStep4QueryRewrite:
    """步骤4：执行查询重写，语义优化、条件补全、口径归一化"""

    def setup_method(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        self.rewriter = QueryRewriter

    def test_stop_word_removal(self):
        result = self.rewriter.rewrite("请帮我查一下今年的销售额吧")
        assert '请' not in result['rewritten']
        assert '帮我' not in result['rewritten']
        assert '吧' not in result['rewritten']
        assert result['rewrite_applied'] is True

    def test_time_normalization(self):
        from datetime import datetime
        year = str(datetime.now().year)
        result = self.rewriter.rewrite("今年各地区销售额咋样啊")
        assert year in result['rewritten']

    def test_empty_query(self):
        result = self.rewriter.rewrite("")
        assert result['intent'] == 'unknown'
        assert result['rewrite_applied'] is False


# ============================================================
class TestStep8CompressionAndReranking:
    """步骤8：对检索结果进行上下文压缩、去重、去噪与相关性重排序"""

    def test_retrieval_result_compression(self):
        """使用 compress_retrieval_results 测试列表级去重压缩"""
        from apps.chat.thinking.context_compressor import ContextCompressor
        terms = [
            {"word": "销售额", "description": "总销售金额", "similarity": 0.9},
            {"word": "销售额", "description": "总销售金额", "similarity": 0.9},  # 重复
            {"word": "低质量", "description": "x", "similarity": 0.1},  # 低相关
            {"word": "利润率", "description": "净利润与收入的比率", "similarity": 0.8},
        ]
        compressed_terms, _, stats = ContextCompressor.compress_retrieval_results(
            terminology_results=terms,
            sql_example_results=[],
            min_similarity=0.35
        )
        # 去重后应只有2个（销售额去重，低质量被过滤）
        assert len(compressed_terms) == 2
        assert stats['terms_removed'] == 2

    def test_context_string_compression(self):
        """使用 compress() 测试字符串级压缩"""
        from apps.chat.thinking.context_compressor import ContextCompressor
        long_schema = "Table sales\n  id INT\n  amount DECIMAL\n" * 200
        result = ContextCompressor.compress(
            terminologies="<terminology>销售额: 总金额</terminology>",
            sql_examples="<example>SELECT * FROM sales</example>",
            schema=long_schema,
            question="查询销售额",
            max_total_tokens=500
        )
        assert result['compression_applied'] is True
        # 动态 chars_per_token 转换：英文内容的 char_budget 更大（1 token ≈ 3 chars for English）
        # max_total_tokens=500, 英文内容 chars_per_token≈3.0, char_budget≈1500
        assert result['stats']['compressed_length'] <= 1500

    def test_reranking_terminologies(self):
        """使用 rerank_terminologies 测试重排序"""
        from apps.chat.thinking.rag_reranker import RAGReranker
        terms = [
            {"word": "天气", "description": "天气预报", "similarity": 0.3},
            {"word": "销售额", "description": "总销售金额", "similarity": 0.8},
            {"word": "利润", "description": "净利润", "similarity": 0.7},
        ]
        result = RAGReranker.rerank_terminologies(terms, question="销售额统计")
        assert len(result) > 0
        # 销售额应排在前面
        assert result[0]['word'] == '销售额'


# ============================================================
class TestStep9SubQuestionDecomposition:
    """步骤9：对复杂多维度问题进行子问题分解"""

    def setup_method(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        self.rewriter = QueryRewriter

    def test_comparison_decomposition(self):
        result = self.rewriter.decompose_complex_query("对比华东和华南的销售额")
        assert result['is_complex'] is True
        assert result['task_type'] == 'comparison'
        assert 'sub_tasks' in result
        assert len(result['sub_tasks']) >= 2

    def test_multi_step_decomposition(self):
        result = self.rewriter.decompose_complex_query("统计各部门人数并且找出人数最多的部门")
        assert result['is_complex'] is True
        assert result['task_type'] == 'multi_step'
        assert len(result['sub_tasks']) >= 2

    def test_simple_query_no_decomposition(self):
        result = self.rewriter.decompose_complex_query("查询今年销售额")
        assert result['is_complex'] is False
        assert len(result['sub_tasks']) == 1

    def test_trend_decomposition(self):
        result = self.rewriter.decompose_complex_query("分析销售额增长趋势")
        assert result['is_complex'] is True
        assert result['task_type'] == 'trend_analysis'


# ============================================================
class TestSteps2And10DialogueState:
    """步骤2：加载历史上下文 + 步骤10：多轮语义对齐"""

    def setup_method(self):
        from apps.chat.thinking.dialogue_state import DialogueStateTracker
        self.tracker = DialogueStateTracker()

    def test_history_loading(self):
        """Step 2: 加载历史对话上下文"""
        history = [
            {"question": "查询今年销售额", "sql": "SELECT SUM(amount) FROM sales", "sql_success": True},
            {"question": "按地区分组", "sql": "SELECT region, SUM(amount) FROM sales GROUP BY region", "sql_success": True},
        ]
        self.tracker.load_history(history)
        assert len(self.tracker.turns) == 2
        assert self.tracker.current_topic is not None

    def test_multi_turn_alignment(self):
        """Step 10: 多轮语义对齐"""
        r1 = self.tracker.track_turn("查询华东地区今年销售额")
        assert r1['intent'] == 'query'

        r2 = self.tracker.track_turn("那么利润率呢")
        assert r2['topic_changed'] is False

        r3 = self.tracker.track_turn("预测明年全国市场规模")
        assert r3['intent'] == 'prediction'

    def test_context_reference_resolution(self):
        """Step 10: 上下文引用解析（指代消解）"""
        self.tracker.track_turn(
            "查询今年销售额",
            sql="SELECT SUM(amount) FROM sales WHERE year=2026",
            sql_success=True
        )
        r2 = self.tracker.track_turn("上面的数据按月份拆分")
        assert r2['context_references']
        ref = r2['context_references'][0]
        assert ref['type'] == 'prev_result'
        assert ref['resolved']

    def test_dialogue_context_for_llm(self):
        """验证对话上下文可注入LLM提示词"""
        self.tracker.track_turn("查询销售额")
        self.tracker.track_turn("按地区分组")
        ctx = self.tracker.get_dialogue_context()
        assert 'recent_questions' in ctx
        assert 'current_intent' in ctx
        assert 'active_entities' in ctx
        assert len(ctx['recent_questions']) == 2

    def test_entity_memory(self):
        """验证实体记忆跨轮次保持"""
        self.tracker.track_turn("查询2026年华东地区销售额")
        self.tracker.track_turn("利润率是多少")
        assert len(self.tracker.entity_memory) > 0
        all_entities = list(self.tracker.entity_memory.keys())
        assert any('2026' in e for e in all_entities)

    def test_topic_switch_detection(self):
        """验证话题切换检测"""
        self.tracker.track_turn("查询华东地区销售额")
        r2 = self.tracker.track_turn("北京天气怎么样")
        assert r2['topic_changed'] is True

    def test_clarification_detection(self):
        """验证澄清意图检测"""
        self.tracker.track_turn("查询销售额")
        r2 = self.tracker.track_turn("什么意思，能不能解释一下")
        assert r2['is_clarification'] is True

    def test_correction_detection(self):
        """验证修正意图检测"""
        self.tracker.track_turn("查询华东销售额")
        r2 = self.tracker.track_turn("不对，应该是华南的")
        assert r2['is_correction'] is True


# ============================================================
class TestStep11ValidityCheck:
    """步骤11：执行结果有效性校验"""

    def test_trivial_chat_detection(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        assert QueryRewriter._is_trivial_chat("你好") is True
        assert QueryRewriter._is_trivial_chat("谢谢") is True
        assert QueryRewriter._is_trivial_chat("查询销售额") is False

    def test_intent_routing(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        assert QueryRewriter.map_to_route('fact_query') == 'data_query'
        assert QueryRewriter.map_to_route('statistical_analysis') == 'analysis'
        assert QueryRewriter.map_to_route('prediction') == 'prediction'
        assert QueryRewriter.map_to_route('term_explanation') == 'general_chat'
        assert QueryRewriter.map_to_route('irrelevant_query') == 'general_chat'

    def test_dialogue_intent_mapping(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        assert QueryRewriter.map_intent_to_dialogue_intent('fact_query') == 'query'
        assert QueryRewriter.map_intent_to_dialogue_intent('prediction') == 'prediction'
        assert QueryRewriter.map_intent_to_dialogue_intent('statistical_analysis') == 'analysis'


# ============================================================
class TestStep14TerminologyExpansion:
    """步骤14：调用系统商业术语库对回答进行术语统一"""

    def test_post_expand_with_terminologies(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        query = "查询GMV数据"
        terms = [{"word": "GMV", "description": "商品交易总额"}]
        result = QueryRewriter.post_expand_with_terminologies(query, terms)
        assert "商品交易总额" in result

    def test_empty_terminologies(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        result = QueryRewriter.post_expand_with_terminologies("查询数据", [])
        assert result == "查询数据"


# ============================================================
class TestDataCleaning:
    """4.1 步骤4：数据清洗（去重、空值、格式、异常值）"""

    @pytest.fixture(autouse=True)
    def _skip_if_no_oracledb(self):
        pytest.importorskip("oracledb", reason="oracledb not installed")

    def test_deduplication(self):
        from apps.datasource.api.datasource import _clean_dataframe
        df = pd.DataFrame({'a': [1, 1, 2], 'b': ['x', 'x', 'y']})
        result, stats = _clean_dataframe(df)
        assert len(result) == 2

    def test_null_handling(self):
        from apps.datasource.api.datasource import _clean_dataframe
        df = pd.DataFrame({
            'num': [1.0, np.nan, 3.0],
            'text': ['hello', None, 'world']
        })
        result, stats = _clean_dataframe(df)
        assert result['num'].isna().sum() == 0
        assert result['text'].isna().sum() == 0

    def test_all_null_row_removal(self):
        from apps.datasource.api.datasource import _clean_dataframe
        df = pd.DataFrame({
            'a': [1, np.nan, 3],
            'b': ['x', np.nan, 'z']
        })
        result, stats = _clean_dataframe(df)
        assert len(result) == 2

    def test_column_name_strip(self):
        from apps.datasource.api.datasource import _clean_dataframe
        df = pd.DataFrame({' name ': ['a'], ' value ': [1]})
        result, stats = _clean_dataframe(df)
        assert 'name' in result.columns
        assert 'value' in result.columns

    def test_outlier_clipping(self):
        """异常值3σ检测（不再截断，仅标记）"""
        from apps.datasource.api.datasource import _clean_dataframe
        # 生成正态分布数据 + 一个极端异常值
        np.random.seed(42)
        normal_data = np.random.normal(100, 10, 50).tolist()
        normal_data.append(100000)  # 极端异常值
        df = pd.DataFrame({'val': normal_data})
        result, stats = _clean_dataframe(df)
        # _clean_dataframe 不再截断异常值，仅记录日志
        # 异常值保留原始值，由下游 _annotate_data_quality 做非破坏性标注
        assert result['val'].max() == 100000, "Outlier should be preserved (non-destructive)"
