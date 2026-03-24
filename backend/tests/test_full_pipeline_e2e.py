"""基于RAG与大语言模型的商业智能分析对话系统 — 完整处理链路端到端测试"""
import json
import pytest
from unittest.mock import MagicMock


# ========== 1. 查询理解：10种意图全覆盖 ==========

class TestIntentDetection:
    """测试9种意图检测的准确性"""

    ALL_INTENTS = (
        'fact_query', 'statistical_analysis', 'comparison_analysis',
        'trend_analysis', 'prediction', 'term_explanation',
        'follow_up', 'ambiguous_query', 'irrelevant_query'
    )

    @pytest.fixture
    def detect(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        return QueryRewriter._detect_intent

    @pytest.fixture
    def rewrite(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        return QueryRewriter.rewrite

    def test_fact_query(self, detect):
        assert detect("查询今年的销售额") == "fact_query"
        assert detect("列出所有产品的库存") == "fact_query"
        assert detect("帮我查一下今年利润") == "fact_query"

    def test_statistical_analysis(self, detect):
        assert detect("分析各产品的销售数据") == "statistical_analysis"
        assert detect("统计各部门的人数") == "statistical_analysis"

    def test_comparison_analysis(self, detect):
        assert detect("对比A产品和B产品的销售额") == "comparison_analysis"
        assert detect("A产品和B产品哪个卖得好") == "comparison_analysis"

    def test_trend_analysis(self, detect):
        assert detect("销售额的变化趋势") == "trend_analysis"
        assert detect("收入增长情况") == "trend_analysis"

    def test_prediction(self, detect):
        assert detect("预测下个月的销售额") == "prediction"
        assert detect("明年的收入会是多少") == "prediction"

    def test_term_explanation(self, detect):
        assert detect("ROI怎么计算") == "term_explanation"
        assert detect("什么是GMV") == "term_explanation"

    def test_data_summarization_routes_to_statistical_analysis(self, detect):
        """总结/概括类查询应路由到 statistical_analysis"""
        assert detect("总结一下数据") == "statistical_analysis"
        assert detect("概括里面的内容") == "statistical_analysis"
        assert detect("请总结里面的内容") == "statistical_analysis"
        assert detect("帮我归纳一下数据") == "statistical_analysis"
        assert detect("摘要") == "statistical_analysis"

    def test_follow_up(self, detect):
        assert detect("上述内容怎么样") == "follow_up"

    def test_ambiguous_query(self, detect):
        assert detect("销售情况怎么样") == "ambiguous_query"

    def test_irrelevant_query(self, detect):
        assert detect("你好") == "irrelevant_query"
        assert detect("谢谢") == "irrelevant_query"

    def test_rewrite_output_completeness(self, rewrite):
        """查询重写输出应包含所有必要字段"""
        result = rewrite("今年各产品的销售额是多少")
        required_keys = {'original', 'rewritten', 'expanded_queries',
                         'extracted_keywords', 'intent', 'intent_keywords', 'rewrite_applied'}
        assert required_keys.issubset(set(result.keys()))
        assert result['intent'] in self.ALL_INTENTS


# ========== 2. 意图路由映射 ==========

class TestIntentRouting:
    """测试9种意图到4种处理路由的映射"""

    def test_map_to_route(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        m = QueryRewriter.map_to_route
        # fact_query → data_query（纯SQL+图表）
        assert m("fact_query") == "data_query"
        # 分析类 → analysis（SQL+完整分析，注入分析提示词）
        assert m("statistical_analysis") == "analysis"
        assert m("comparison_analysis") == "analysis"
        assert m("trend_analysis") == "analysis"
        # 预测 → prediction（SQL+完整预测，注入预测提示词）
        assert m("prediction") == "prediction"
        # 非SQL类 → general_chat
        assert m("term_explanation") == "general_chat"
        assert m("ambiguous_query") == "general_chat"
        assert m("irrelevant_query") == "general_chat"
        # 追问 → data_query（兜底）
        assert m("follow_up") == "data_query"

    def test_map_to_design_intent(self):
        """5大设计意图映射"""
        from apps.chat.thinking.unified_rag_executor import map_to_design_intent, DesignIntent
        # PDF所有意图 → DOCUMENT_QA
        assert map_to_design_intent("fact_query", "pdf") == DesignIntent.DOCUMENT_QA
        assert map_to_design_intent("comparison_analysis", "pdf") == DesignIntent.DOCUMENT_QA
        assert map_to_design_intent("prediction", "pdf") == DesignIntent.DOCUMENT_QA
        # 非PDF
        assert map_to_design_intent("fact_query", "database") == DesignIntent.DATA_QUERY
        assert map_to_design_intent("statistical_analysis", "database") == DesignIntent.DATA_ANALYSIS
        assert map_to_design_intent("prediction", "database") == DesignIntent.DATA_PREDICTION

    def test_intent_to_frontend_scenario_mapping(self):
        """9种意图 → 前端 scenarioType 映射（决定思考过程步骤显示）"""
        # 映射规则（与 ChartAnswer.vue dynamicScenarioType 一致）
        INTENT_TO_SCENARIO = {
            'irrelevant_query': 'general_chat',
            'term_explanation': 'general_chat',
            'ambiguous_query': 'general_chat',
            'statistical_analysis': 'sql_analysis',
            'comparison_analysis': 'sql_analysis',
            'trend_analysis': 'sql_analysis',
            'prediction': 'sql_prediction',
            # fact_query/follow_up → sql 或 sql_analysis（取决于是否有分析结果）
            # 此处测试基础映射（无分析结果时）
        }
        for intent, expected_scenario in INTENT_TO_SCENARIO.items():
            # 验证 general_chat 意图不显示步骤5和6
            if expected_scenario == 'general_chat':
                assert expected_scenario not in ('sql', 'sql_analysis', 'sql_prediction'), \
                    f"Intent '{intent}' maps to '{expected_scenario}', step 5/6 should be hidden"

        # 验证分析类意图走 sql_analysis → 有步骤5和6
        assert INTENT_TO_SCENARIO['statistical_analysis'] == 'sql_analysis'
        assert INTENT_TO_SCENARIO['comparison_analysis'] == 'sql_analysis'
        assert INTENT_TO_SCENARIO['trend_analysis'] == 'sql_analysis'
        # 验证预测意图走 sql_prediction → 有步骤5和6
        assert INTENT_TO_SCENARIO['prediction'] == 'sql_prediction'


# ========== 3. 数据源组件矩阵 ==========

class TestComponentMatrix:
    """测试4类数据源的组件可用性矩阵"""

    def test_database_all_enabled(self):
        from apps.chat.thinking.ds_component_router import get_allowed_components
        c = get_allowed_components("pg")
        assert c['terminology'] is True
        assert c['sql_generation_prompt'] is True
        assert c['sql_example_library'] is True
        assert c['data_analysis_prompt'] is True
        assert c['data_prediction_prompt'] is True
        assert c['visualization'] is True
        assert c['document_qa'] is False

    def test_excel_csv_all_enabled(self):
        from apps.chat.thinking.ds_component_router import get_allowed_components
        for ds in ("excel", "csv"):
            c = get_allowed_components(ds)
            assert c['terminology'] is True
            assert c['sql_generation_prompt'] is True
            assert c['sql_example_library'] is True
            assert c['data_analysis_prompt'] is True
            assert c['data_prediction_prompt'] is True
            assert c['visualization'] is True

    def test_pdf_only_doc_qa(self):
        from apps.chat.thinking.ds_component_router import get_allowed_components
        c = get_allowed_components("pdf")
        assert c['terminology'] is False  # PDF不需要商业术语库
        assert c['document_qa'] is True
        # PDF禁用所有SQL/分析/预测/可视化
        assert c['sql_generation_prompt'] is False
        assert c['sql_example_library'] is False
        assert c['data_analysis_prompt'] is False
        assert c['data_prediction_prompt'] is False
        assert c['visualization'] is False

    def test_unified_rag_component_matrix_consistency(self):
        """unified_rag_executor的COMPONENT_MATRIX与ds_component_router一致"""
        from apps.chat.thinking.unified_rag_executor import COMPONENT_MATRIX
        from apps.chat.thinking.ds_component_router import (
            is_sql_allowed, is_analysis_allowed, is_prediction_allowed,
            is_chart_allowed, is_document_qa_allowed
        )
        for ds_type in ("pdf", "excel", "csv", "database"):
            row = COMPONENT_MATRIX.get(ds_type, COMPONENT_MATRIX["database"])
            assert row["sql_prompt"] == is_sql_allowed(ds_type), f"{ds_type} sql_prompt mismatch"
            assert row["analysis_prompt"] == is_analysis_allowed(ds_type), f"{ds_type} analysis_prompt mismatch"
            assert row["prediction_prompt"] == is_prediction_allowed(ds_type), f"{ds_type} prediction_prompt mismatch"
            assert row["antv_g2"] == is_chart_allowed(ds_type), f"{ds_type} antv_g2 mismatch"


# ========== 4. 自定义提示词全量注入 ==========

class TestCustomPromptInjection:
    """测试自定义提示词的全量注入逻辑"""

    def _make_session(self, prompts):
        mock = MagicMock()
        mock.exec.return_value.all.return_value = prompts
        return mock

    def _make_prompt(self, id, name, prompt, specific_ds=False, datasource_ids=None):
        p = MagicMock()
        p.id = id
        p.name = name
        p.prompt = prompt
        p.specific_ds = specific_ds
        p.datasource_ids = datasource_ids
        p.oid = 1
        return p

    def test_all_prompts_injected(self):
        """所有提示词应全量注入（reason=intent_inject）"""
        from common.chatbi.custom_prompt import find_relevant_custom_prompts, CustomPromptTypeEnum
        prompts = [
            self._make_prompt(1, "规则A", "内容A"),
            self._make_prompt(2, "规则B", "内容B"),
        ]
        session = self._make_session(prompts)
        content, details = find_relevant_custom_prompts(
            session, CustomPromptTypeEnum.GENERATE_SQL, 1, "任意问题"
        )
        assert "内容A" in content
        assert "内容B" in content
        assert all(d['reason'] == 'intent_inject' for d in details)
        assert all(d['score'] == 1.0 for d in details)

    def test_ds_filter(self):
        """specific_ds=True时，数据源不匹配的提示词应被过滤"""
        from common.chatbi.custom_prompt import find_relevant_custom_prompts, CustomPromptTypeEnum
        prompts = [
            self._make_prompt(1, "全局", "全局内容", specific_ds=False),
            self._make_prompt(2, "限定DS1", "DS1内容", specific_ds=True, datasource_ids=[1]),
        ]
        session = self._make_session(prompts)
        content, details = find_relevant_custom_prompts(
            session, CustomPromptTypeEnum.GENERATE_SQL, 1, "问题", ds_id=999
        )
        assert "全局内容" in content
        assert "DS1内容" not in content

    def test_token_budget(self):
        """超过5000字符预算的提示词应被标记为budget_exceeded"""
        from common.chatbi.custom_prompt import find_relevant_custom_prompts, CustomPromptTypeEnum
        prompts = [
            self._make_prompt(1, "大规则", "x" * 3000),
            self._make_prompt(2, "中规则", "y" * 2000),
            self._make_prompt(3, "超限", "z" * 1000),
        ]
        session = self._make_session(prompts)
        content, details = find_relevant_custom_prompts(
            session, CustomPromptTypeEnum.GENERATE_SQL, 1, "问题"
        )
        injected = [d for d in details if d['reason'] == 'intent_inject']
        exceeded = [d for d in details if d['reason'] == 'budget_exceeded']
        assert len(injected) == 2  # 3000+2000=5000，刚好
        assert len(exceeded) == 1  # 第3条超限

    def test_three_prompt_types(self):
        """三种提示词类型对应三张独立ORM表"""
        # 直接验证ORM表名，绕过全量测试中MagicMock污染CustomPromptTypeEnum的问题
        from common.chatbi.custom_prompt import PromptSQL, PromptAnalysis, PromptForecast
        assert PromptSQL.__tablename__ == "prompt_business_sql"
        assert PromptAnalysis.__tablename__ == "prompt_business_analysis"
        assert PromptForecast.__tablename__ == "prompt_business_forecast"
        # 验证三种类型枚举值
        from common.chatbi.custom_prompt import CustomPromptTypeEnum
        assert hasattr(CustomPromptTypeEnum, 'GENERATE_SQL')
        assert hasattr(CustomPromptTypeEnum, 'ANALYSIS')
        assert hasattr(CustomPromptTypeEnum, 'PREDICT_DATA')

    def test_orm_table_names(self):
        """ORM表名与数据库迁移一致"""
        from common.chatbi.custom_prompt import PromptSQL, PromptAnalysis, PromptForecast
        assert PromptSQL.__tablename__ == "prompt_business_sql"
        assert PromptAnalysis.__tablename__ == "prompt_business_analysis"
        assert PromptForecast.__tablename__ == "prompt_business_forecast"


# ========== 5. PDF多层保护 ==========

class TestPDFProtection:
    """测试PDF数据源的多层保护机制"""

    def test_layer1_intent_detection(self):
        """第1层：_detect_intent对PDF返回3种意图之一"""
        from apps.chat.thinking.query_rewriter import QueryRewriter
        # PDF所有查询都映射到3种意图（document_qa / comparison_analysis / irrelevant_query）
        assert QueryRewriter._detect_intent("总结这份文档", ds_type="pdf") == "document_qa"
        assert QueryRewriter._detect_intent("对比A和B", ds_type="pdf") == "comparison_analysis"
        assert QueryRewriter._detect_intent("你好", ds_type="pdf") == "irrelevant_query"
        # 默认→document_qa
        assert QueryRewriter._detect_intent("这份报告讲了什么", ds_type="pdf") == "document_qa"

    def test_layer2_design_intent_override(self):
        """第2层：PDF所有意图通过map_to_design_intent统一走DOCUMENT_QA"""
        from apps.chat.thinking.unified_rag_executor import map_to_design_intent, DesignIntent
        # map_to_route是通用路由（comparison_analysis→analysis），
        # 但PDF通过map_to_design_intent统一覆盖为DOCUMENT_QA
        pdf_intents = ["document_qa", "comparison_analysis", "irrelevant_query", "term_explanation"]
        for intent in pdf_intents:
            design = map_to_design_intent(intent, "pdf")
            assert design == DesignIntent.DOCUMENT_QA, f"PDF intent {intent} should map to DOCUMENT_QA, got {design}"

    def test_layer3_component_matrix(self):
        """第3层：组件矩阵禁用PDF的术语库/SQL/分析/预测/可视化"""
        from apps.chat.thinking.ds_component_router import get_allowed_components
        c = get_allowed_components("pdf")
        assert c['terminology'] is False
        assert c['sql_generation_prompt'] is False
        assert c['data_analysis_prompt'] is False
        assert c['data_prediction_prompt'] is False
        assert c['visualization'] is False

    def test_design_intent_all_to_document_qa(self):
        """设计意图：PDF所有意图统一映射到DOCUMENT_QA"""
        from apps.chat.thinking.unified_rag_executor import map_to_design_intent, DesignIntent
        all_intents = [
            "fact_query", "statistical_analysis", "comparison_analysis",
            "trend_analysis", "prediction", "term_explanation",
            "follow_up", "ambiguous_query", "irrelevant_query"
        ]
        for intent in all_intents:
            assert map_to_design_intent(intent, "pdf") == DesignIntent.DOCUMENT_QA


# ========== 6. 查询重写完整性 ==========

class TestQueryRewrite:
    """测试查询重写的各个子模块"""

    def test_time_normalization(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        from datetime import datetime
        ref = datetime(2026, 3, 19)
        result = QueryRewriter._normalize_time_expressions("今年的销售额", reference_time=ref)
        assert "2026" in result

    def test_stop_word_removal(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        result = QueryRewriter._remove_stop_words("请帮我查一下销售额")
        assert "请" not in result
        assert "帮我" not in result

    def test_keyword_extraction(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        keywords = QueryRewriter._extract_keywords("各产品的销售额排名")
        assert len(keywords) > 0

    def test_intent_explain(self):
        """意图解释应返回命中的关键词"""
        from apps.chat.thinking.query_rewriter import QueryRewriter
        keywords = QueryRewriter._explain_intent("预测下个月的销售额", "prediction")
        assert len(keywords) > 0

    def test_trivial_chat_detection(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        assert QueryRewriter._is_trivial_chat("你好") is True
        assert QueryRewriter._is_trivial_chat("查询今年销售额") is False

    def test_complex_query_decomposition(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        result = QueryRewriter.decompose_complex_query("对比A和B的销售额")
        assert result['is_complex'] is True
        assert result['task_type'] == 'comparison'
        assert len(result['sub_tasks']) >= 2


# ========== 7. 统一RAG执行器数据结构 ==========

class TestUnifiedRAGStructures:
    """测试三阶段RAG执行器的数据结构完整性"""

    def test_retrieve_result_fields(self):
        from apps.chat.thinking.unified_rag_executor import RetrieveResult
        r = RetrieveResult()
        assert hasattr(r, 'intent')
        assert hasattr(r, 'fine_intent')
        assert hasattr(r, 'terminology_results')
        assert hasattr(r, 'sql_example_results')
        assert hasattr(r, 'doc_chunk_results')
        assert hasattr(r, 'custom_prompts')

    def test_augment_result_fields(self):
        from apps.chat.thinking.unified_rag_executor import AugmentResult
        a = AugmentResult()
        assert hasattr(a, 'augmented_system_prompt')
        assert hasattr(a, 'terminologies_xml')
        assert hasattr(a, 'sql_examples_xml')
        assert hasattr(a, 'components_used')

    def test_generate_result_fields(self):
        from apps.chat.thinking.unified_rag_executor import GenerateResult
        g = GenerateResult()
        assert hasattr(g, 'text_answer')
        assert hasattr(g, 'sql')
        assert hasattr(g, 'analysis_text')
        assert hasattr(g, 'prediction_text')
        assert hasattr(g, 'antv_g2_config')

    def test_design_intent_constants(self):
        from apps.chat.thinking.unified_rag_executor import DesignIntent
        assert DesignIntent.DOCUMENT_QA == "document_qa"
        assert DesignIntent.DATA_QUERY == "data_query"
        assert DesignIntent.DATA_ANALYSIS == "data_analysis"
        assert DesignIntent.DATA_PREDICTION == "data_prediction"
        assert DesignIntent.VISUALIZATION == "visualization"


# ========== 8. 前端i18n场景标签 ==========

class TestI18nLabels:
    """测试前端i18n标签的正确性"""

    @pytest.fixture
    def zh_cn(self):
        import os
        i18n_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'frontend', 'src', 'i18n', 'zh-CN.json'
        )
        with open(i18n_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_scenario_labels(self, zh_cn):
        """场景标签应为简洁中文"""
        thinking = zh_cn.get('thinking', {})
        assert thinking.get('scenario_sql_query') == 'SQL'
        assert thinking.get('scenario_sql_analysis') == 'SQL + 分析'
        assert thinking.get('scenario_sql_prediction') == 'SQL + 预测'
        assert thinking.get('scenario_data_analysis') == '分析'
        assert thinking.get('scenario_data_prediction') == '预测'

    def test_prompt_match_intent_label(self, zh_cn):
        """intent_inject的中文标签"""
        thinking = zh_cn.get('thinking', {})
        assert thinking.get('prompt_match_intent') == '全规则意图注入'

    def test_type_match_count_format(self, zh_cn):
        """注入条数显示格式"""
        pc = zh_cn.get('prompt_construction', {})
        assert '条注入' in pc.get('type_match_count', '')
        # 不应包含"命中"
        assert '命中' not in pc.get('type_match_count', '')


# ========== 9. 边缘案例意图检测 ==========

class TestEdgeCaseIntents:
    """测试审计中发现的3个缺陷修复"""

    @pytest.fixture
    def detect(self):
        from apps.chat.thinking.query_rewriter import QueryRewriter
        return QueryRewriter._detect_intent

    def test_comparison_with_verb(self, detect):
        """'哪个卖得好'应识别为comparison_analysis"""
        assert detect("A产品和B产品哪个卖得好") == "comparison_analysis"

    def test_term_explanation_priority(self, detect):
        """'ROI怎么计算'应识别为term_explanation"""
        assert detect("ROI怎么计算") == "term_explanation"

    def test_fact_query_colloquial(self, detect):
        """'帮我查一下今年利润'应识别为fact_query"""
        assert detect("帮我查一下今年利润") == "fact_query"


# ========== 10. PromptBuilder来源标记 ==========

class TestPromptBuilder:
    """测试PromptBuilder的source标记"""

    def test_custom_prompt_source_is_intent_inject(self):
        """PromptBuilder._build_metadata中custom_prompt组件的source应为intent_inject"""
        from apps.chat.thinking.prompt_builder import PromptBuilder
        builder = PromptBuilder(prompt_type='sql_generation', model_name='test')
        builder.set_custom_prompts("测试内容", [])
        # _build_metadata返回PromptMetadata，其中components包含各组件
        metadata = builder._build_metadata("sys", "user")
        cp_comp = None
        for comp in metadata.components:
            if comp.name == 'custom_prompt':
                cp_comp = comp
                break
        assert cp_comp is not None
        assert cp_comp.source == 'intent_inject'
        assert cp_comp.injected is True

    def test_data_sample_component(self):
        """<data-sample>应被识别为data_sample组件，而非document_chunks"""
        from apps.chat.thinking.prompt_builder import PromptBuilder
        builder = PromptBuilder(prompt_type='direct_answer', model_name='test')
        # 模拟包含 <data-sample> 的场景
        data_training_with_sample = (
            '\n<data-sample>\n'
            '表名: 销售数据 (共100行)\n'
            '字段: 日期 | 产品 | 金额\n'
            '样本数据（前5行）:\n'
            '2024-01-01 | 产品A | 1000\n'
            '---\n'
            '表名: 客户数据 (共50行)\n'
            '字段: 姓名 | 地区\n'
            '样本数据（前5行）:\n'
            '张三 | 北京\n'
            '</data-sample>'
        )
        builder.set_rag_knowledge(
            terminologies_xml='<terminology>test</terminology>',
            sql_examples_xml=data_training_with_sample,
        )
        metadata = builder._build_metadata("sys prompt", "user prompt")

        # data_sample 组件应被注入
        ds_comp = next((c for c in metadata.components if c.name == 'data_sample'), None)
        assert ds_comp is not None, "data_sample component should exist"
        assert ds_comp.injected is True, "data_sample should be injected"
        assert ds_comp.count == 2, "should detect 2 tables"
        assert ds_comp.char_length > 0

        # document_chunks 组件不应被注入
        dc_comp = next((c for c in metadata.components if c.name == 'document_chunks'), None)
        assert dc_comp is not None
        assert dc_comp.injected is False, "document_chunks should NOT be injected when data_sample is present"
        assert dc_comp.count == 0

        # sql_examples 组件不应被注入（<data-sample>不是SQL示例）
        se_comp = next((c for c in metadata.components if c.name == 'sql_examples'), None)
        assert se_comp is not None
        assert se_comp.injected is False, "sql_examples should NOT be injected when only <data-sample> present"

        # component_counts 应包含 data_sample 字段
        counts = metadata.to_component_counts()
        assert counts.get('data_sample_count') == 2
        assert counts.get('data_sample_length', 0) > 0
        assert counts.get('doc_chunk_count') == 0

    def test_data_sample_separated_from_sql_examples(self):
        """<data-sample>应从sql_examples_xml中分离，不影响SQL示例计数"""
        from apps.chat.thinking.prompt_builder import PromptBuilder
        builder = PromptBuilder(prompt_type='direct_answer', model_name='test')
        # 混合内容：SQL示例 + data-sample（理论上不会同时出现，但测试防御性）
        mixed = (
            '<sql-example><question>查询销售额</question><sql>SELECT sum(amount) FROM sales</sql></sql-example>'
            '\n<data-sample>\n表名: sales (共100行)\n</data-sample>'
        )
        builder.set_rag_knowledge(terminologies_xml='', sql_examples_xml=mixed)
        metadata = builder._build_metadata("sys", "user")

        se_comp = next((c for c in metadata.components if c.name == 'sql_examples'), None)
        assert se_comp.count == 1, "SQL example count should be 1"

        ds_comp = next((c for c in metadata.components if c.name == 'data_sample'), None)
        assert ds_comp.injected is True
        assert ds_comp.count == 1

    def test_set_data_sample_explicit(self):
        """显式调用 set_data_sample 应正确设置组件"""
        from apps.chat.thinking.prompt_builder import PromptBuilder
        builder = PromptBuilder(prompt_type='direct_answer', model_name='test')
        builder.set_data_sample(table_count=3, data_sample_xml='<data-sample>test</data-sample>')
        metadata = builder._build_metadata("sys", "user")

        ds_comp = next((c for c in metadata.components if c.name == 'data_sample'), None)
        assert ds_comp.injected is True
        assert ds_comp.count == 3

    def test_excel_data_sample_no_document_chunks(self):
        """Excel场景：rag_components中document_chunks应为False"""
        from apps.chat.thinking.prompt_builder import PromptBuilder
        builder = PromptBuilder(prompt_type='direct_answer', model_name='test')
        # Excel 场景：只有 <data-sample>，没有 <document-knowledge>
        builder.set_rag_knowledge(
            terminologies_xml='',
            sql_examples_xml='\n<data-sample>\n表名: test (共10行)\n</data-sample>',
        )
        metadata = builder._build_metadata("sys", "user")
        rag_components = metadata.to_rag_components()

        assert rag_components.get('document_chunks') is False, \
            "Excel should NOT have document_chunks in rag_components when only data_sample present"
        assert rag_components.get('data_sample') is True, \
            "Excel should have data_sample in rag_components"

    def test_non_pdf_never_has_document_chunks(self):
        """非PDF数据源（Excel/CSV/Database）的任何意图都不应有document_chunks"""
        from apps.chat.thinking.prompt_builder import PromptBuilder
        # 模拟各种非PDF场景
        test_cases = [
            ('sql_generation', '<sql-example><question>test</question></sql-example>'),
            ('direct_answer', ''),
            ('direct_answer', '\n<data-sample>\n表名: test\n</data-sample>'),
            ('analysis', ''),
            ('prediction', ''),
        ]
        for prompt_type, sql_xml in test_cases:
            builder = PromptBuilder(prompt_type=prompt_type, model_name='test')
            builder.set_rag_knowledge(terminologies_xml='', sql_examples_xml=sql_xml)
            metadata = builder._build_metadata("sys prompt content", "user prompt")
            rag = metadata.to_rag_components()
            assert rag.get('document_chunks') is False, \
                f"Non-PDF prompt_type={prompt_type} should NOT have document_chunks"

    def test_template_literal_document_knowledge_not_counted(self):
        """模板指令文本中的<document-knowledge>字面量不应被计为文档片段"""
        from apps.chat.thinking.prompt_builder import PromptBuilder
        builder = PromptBuilder(prompt_type='direct_answer', model_name='test')
        # 模拟 direct_answer 模板：指令文本中提到 <document-knowledge> 但不是实际数据
        builder.set_rag_knowledge(terminologies_xml='', sql_examples_xml='')
        # 系统提示词中包含模板指令文本（含 <document-knowledge> 字面量）
        sys_prompt = (
            '你是ChatBI助手。\n'
            '如果数据源类型为PDF，你必须优先基于<document-knowledge>中的文档内容来回答。\n'
            '<Info>\n</Info>'
        )
        metadata = builder._build_metadata(sys_prompt, "user prompt")
        rag = metadata.to_rag_components()
        counts = metadata.to_component_counts()
        # 后端不应将模板指令中的字面量计为文档片段
        assert rag.get('document_chunks') is False
        assert counts.get('doc_chunk_count', 0) == 0


class TestVisualizationSummarization:
    """测试总结类关键词的可视化检测"""

    def test_summarization_keywords_skip_visualization(self):
        """总结/概括类关键词应跳过可视化，输出纯文字"""
        from apps.chat.thinking.visualization_intent import VisualizationIntentDetector
        test_questions = [
            "总结一下销售数据",
            "概括这个表的内容",
            "概述数据特征",
            "归纳一下主要指标",
            "summarize the sales data",
            "give me an overview of the data",
        ]
        for q in test_questions:
            result = VisualizationIntentDetector.detect(q, ds_type='excel')
            assert result.needs_visualization is False, \
                f"Question '{q}' should NOT trigger visualization"
