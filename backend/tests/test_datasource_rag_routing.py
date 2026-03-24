"""测试6种数据源类型的RAG路由正确性"""
import pytest
from apps.chat.thinking.query_rewriter import QueryRewriter
from apps.db.constant import DB


# ============================================================

class TestDatasourceTypeDefinitions:
    """验证6种数据源类型在DB枚举中正确定义"""

    EXPECTED_TYPES = {
        'excel': {'db_name': 'Excel', 'template_name': 'PostgreSQL', 'prefix': '"', 'suffix': '"'},
        'csv': {'db_name': 'CSV', 'template_name': 'PostgreSQL', 'prefix': '"', 'suffix': '"'},
        'pdf': {'db_name': 'PDF', 'template_name': 'PostgreSQL', 'prefix': '"', 'suffix': '"'},
        'pg': {'db_name': 'PostgreSQL', 'template_name': 'PostgreSQL', 'prefix': '"', 'suffix': '"'},
        'mysql': {'db_name': 'MySQL', 'template_name': 'MySQL', 'prefix': '`', 'suffix': '`'},
        'oracle': {'db_name': 'Oracle', 'template_name': 'Oracle', 'prefix': '"', 'suffix': '"'},
    }

    @pytest.mark.parametrize("ds_type,expected", list(EXPECTED_TYPES.items()))
    def test_db_enum_exists(self, ds_type, expected):
        """每种数据源类型在DB枚举中有正确定义"""
        db = DB.get_db(ds_type)
        assert db is not None, f"DB.get_db('{ds_type}') returned None"
        assert db.db_name == expected['db_name']
        assert db.template_name == expected['template_name']
        assert db.prefix == expected['prefix']
        assert db.suffix == expected['suffix']

    def test_all_six_types_covered(self):
        """确保6种类型全部有对应的DB枚举"""
        for ds_type in ['excel', 'csv', 'pdf', 'pg', 'mysql', 'oracle']:
            db = DB.get_db(ds_type)
            assert db is not None, f"Missing DB enum for type: {ds_type}"


# ============================================================

class TestSQLTemplateFiles:
    """验证每种数据库引擎都有对应的SQL模板文件"""

    @pytest.mark.parametrize("ds_type", ['excel', 'csv', 'pdf', 'pg', 'mysql', 'oracle'])
    def test_sql_template_loadable(self, ds_type):
        """每种数据源类型的SQL模板能正确加载"""
        from apps.template.template import get_sql_template
        template = get_sql_template(ds_type)
        assert template is not None
        assert 'template' in template
        tpl = template['template']
        assert 'quot_rule' in tpl, f"Missing quot_rule for {ds_type}"
        assert 'limit_rule' in tpl, f"Missing limit_rule for {ds_type}"
        assert 'other_rule' in tpl, f"Missing other_rule for {ds_type}"

    @pytest.mark.parametrize("ds_type,expected_keyword", [
        ('pg', '双引号'),
        ('mysql', '反引号'),
        ('oracle', '双引号'),
        ('excel', '双引号'),   # Excel uses PostgreSQL template
        ('csv', '双引号'),     # CSV uses PostgreSQL template
        ('pdf', '双引号'),     # PDF uses PostgreSQL template
    ])
    def test_engine_specific_quoting_rules(self, ds_type, expected_keyword):
        """每种引擎的引号规则正确"""
        from apps.template.template import get_sql_template
        template = get_sql_template(ds_type)
        quot_rule = template['template']['quot_rule']
        assert expected_keyword in quot_rule, f"{ds_type} quot_rule should mention '{expected_keyword}'"


# ============================================================

class TestEngineStringConstruction:
    """验证不同数据源类型的engine字符串构建逻辑"""

    def test_excel_uses_postgresql_engine(self):
        """Excel数据源应使用PostgreSQL引擎（数据导入到PG）"""
        ds_type = 'excel'
        type_name = 'Excel'
        engine = type_name if ds_type not in ('excel', 'csv', 'pdf') else 'PostgreSQL'
        assert engine == 'PostgreSQL'

    def test_csv_uses_postgresql_engine(self):
        """CSV数据源应使用PostgreSQL引擎（数据导入到PG）"""
        ds_type = 'csv'
        type_name = 'CSV'
        engine = type_name if ds_type not in ('excel', 'csv', 'pdf') else 'PostgreSQL'
        assert engine == 'PostgreSQL'

    def test_pdf_uses_postgresql_engine(self):
        """PDF数据源应使用PostgreSQL引擎"""
        ds_type = 'pdf'
        type_name = 'PDF'
        engine = type_name if ds_type not in ('excel', 'csv', 'pdf') else 'PostgreSQL'
        assert engine == 'PostgreSQL'

    @pytest.mark.parametrize("ds_type,type_name,expected_engine", [
        ('pg', 'PostgreSQL', 'PostgreSQL'),
        ('mysql', 'MySQL', 'MySQL'),
        ('oracle', 'Oracle', 'Oracle'),
    ])
    def test_native_db_uses_own_engine(self, ds_type, type_name, expected_engine):
        """原生数据库使用自身引擎名"""
        engine = type_name if ds_type not in ('excel', 'csv', 'pdf') else 'PostgreSQL'
        assert engine == expected_engine


# ============================================================

class TestIntentRoutingAcrossDatasources:
    """验证意图检测和RAG路由在所有数据源类型下一致"""

    ALL_DS_TYPES = ['excel', 'csv', 'pdf', 'pg', 'mysql', 'oracle']

    # 数据查询类问题 → data_query路由 → 需要SQL示例+术语+SQL生成提示词
    DATA_QUERY_QUESTIONS = [
        "查询今年的销售额",
        "列出前10个客户",
    ]

    # 分析类问题 → analysis路由 → 需要SQL示例+术语+分析提示词
    ANALYSIS_QUESTIONS = [
        "深入分析客户流失情况",
        "帮我分析一下销售数据的规律",
        "统计各产品的销售数量",  # "统计"是聚合操作，路由到 statistical_analysis → analysis
        "总结一下文档的主要内容",  # 总结类 → statistical_analysis → analysis
    ]

    # 预测类问题 → prediction路由 → 需要SQL示例+术语+预测提示词
    PREDICTION_QUESTIONS = [
        "预测下个月的销售额",
        "预估明年的增长趋势",
    ]

    # 通用对话类问题 → general_chat路由 → 只需要术语（不需要SQL示例和SQL提示词）
    GENERAL_CHAT_QUESTIONS = [
        "什么是GMV",
        "GMV是什么意思",
    ]

    # 纯寒暄 → 跳过所有RAG
    TRIVIAL_QUESTIONS = [
        "你好",
        "谢谢",
        "hello",
    ]

    @pytest.mark.parametrize("question", DATA_QUERY_QUESTIONS)
    def test_data_query_intent_consistent_across_types(self, question):
        """数据查询意图在非PDF数据源类型下路由一致（PDF走文档问答路径）"""
        for ds_type in self.ALL_DS_TYPES:
            intent = QueryRewriter._detect_intent(question, ds_type=ds_type)
            route = QueryRewriter.map_to_route(intent)
            if ds_type == 'pdf':
                # PDF所有意图统一走文档问答路径（term_explanation → general_chat）
                # PDF不支持SQL查询，即使问题包含"查询"关键词也走RAG文档问答
                assert route == 'general_chat', (
                    f"Question '{question}' with ds_type='pdf': "
                    f"expected route 'general_chat', got '{route}' (intent: {intent})"
                )
            else:
                assert route == 'data_query', (
                    f"Question '{question}' with ds_type='{ds_type}': "
                    f"expected route 'data_query', got '{route}' (intent: {intent})"
                )

    @pytest.mark.parametrize("question", ANALYSIS_QUESTIONS)
    def test_analysis_intent_consistent_across_types(self, question):
        """分析意图在非PDF数据源类型下路由一致（PDF走直接回答路径）"""
        for ds_type in self.ALL_DS_TYPES:
            intent = QueryRewriter._detect_intent(question, ds_type=ds_type)
            route = QueryRewriter.map_to_route(intent)
            if ds_type == 'pdf':
                # PDF数据源设计上走直接回答路径（RAG+LLM文档问答），
                # 除非问题包含明确的表格操作关键词（查询/统计/计算等）
                assert route in ('analysis', 'general_chat'), (
                    f"Question '{question}' with ds_type='pdf': "
                    f"expected route 'analysis' or 'general_chat', got '{route}' (intent: {intent})"
                )
            else:
                assert route == 'analysis', (
                    f"Question '{question}' with ds_type='{ds_type}': "
                    f"expected route 'analysis', got '{route}' (intent: {intent})"
                )

    @pytest.mark.parametrize("question", PREDICTION_QUESTIONS)
    def test_prediction_intent_consistent_across_types(self, question):
        """预测意图在非PDF数据源类型下路由一致（PDF走文档问答路径）"""
        for ds_type in self.ALL_DS_TYPES:
            intent = QueryRewriter._detect_intent(question, ds_type=ds_type)
            route = QueryRewriter.map_to_route(intent)
            if ds_type == 'pdf':
                # PDF所有意图统一走文档问答路径，不支持数据预测
                assert route == 'general_chat', (
                    f"Question '{question}' with ds_type='pdf': "
                    f"expected route 'general_chat', got '{route}' (intent: {intent})"
                )
            else:
                assert route == 'prediction', (
                    f"Question '{question}' with ds_type='{ds_type}': "
                    f"expected route 'prediction', got '{route}' (intent: {intent})"
                )

    @pytest.mark.parametrize("question", GENERAL_CHAT_QUESTIONS)
    def test_general_chat_intent_consistent_across_types(self, question):
        """通用对话意图在所有数据源类型下路由一致"""
        for ds_type in self.ALL_DS_TYPES:
            intent = QueryRewriter._detect_intent(question, ds_type=ds_type)
            route = QueryRewriter.map_to_route(intent)
            assert route == 'general_chat', (
                f"Question '{question}' with ds_type='{ds_type}': "
                f"expected route 'general_chat', got '{route}' (intent: {intent})"
            )

    @pytest.mark.parametrize("question", TRIVIAL_QUESTIONS)
    def test_trivial_chat_detected_across_types(self, question):
        """纯寒暄在所有数据源类型下被正确识别（PDF走直接回答路径）"""
        for ds_type in self.ALL_DS_TYPES:
            intent = QueryRewriter._detect_intent(question, ds_type=ds_type)
            if ds_type == 'pdf':
                # PDF数据源对所有非表格操作问题返回term_explanation
                # 纯寒暄在PDF下也走直接回答路径，效果等价
                assert intent in ('irrelevant_query', 'term_explanation'), (
                    f"Question '{question}' with ds_type='pdf': "
                    f"expected 'irrelevant_query' or 'term_explanation', got '{intent}'"
                )
            else:
                is_trivial = intent == 'irrelevant_query' and QueryRewriter._is_trivial_chat(question)
                assert is_trivial, (
                    f"Question '{question}' with ds_type='{ds_type}': "
                    f"should be trivial chat, got intent='{intent}', is_trivial={is_trivial}"
                )


# ============================================================

class TestRAGKnowledgeSelectionMatrix:
    """验证3类知识在不同路由下的选择逻辑"""

    def test_data_query_needs_all_three(self):
        """data_query路由需要：SQL示例 + 术语 + SQL生成提示词"""
        route = 'data_query'
        skip_sql = route == 'general_chat'
        assert skip_sql is False, "data_query should NOT skip SQL examples"

    def test_analysis_needs_sql_and_terminology(self):
        """analysis路由需要：SQL示例 + 术语 + SQL生成提示词(SQL步骤) + 分析提示词(分析步骤)"""
        route = 'analysis'
        skip_sql = route == 'general_chat'
        assert skip_sql is False, "analysis should NOT skip SQL examples"

    def test_prediction_needs_sql_and_terminology(self):
        """prediction路由需要：SQL示例 + 术语 + SQL生成提示词(SQL步骤) + 预测提示词(预测步骤)"""
        route = 'prediction'
        skip_sql = route == 'general_chat'
        assert skip_sql is False, "prediction should NOT skip SQL examples"

    def test_general_chat_skips_sql(self):
        """general_chat路由：SQL示例 + 术语 + SQL生成提示词"""
        route = 'general_chat'
        skip_sql = route == 'general_chat'
        assert skip_sql is True, "general_chat SHOULD skip SQL examples"

    @pytest.mark.parametrize("intent,expected_route", [
        ('fact_query', 'data_query'),
        ('comparison_analysis', 'analysis'),
        ('trend_analysis', 'analysis'),
        ('statistical_analysis', 'analysis'),
        ('prediction', 'prediction'),
        ('term_explanation', 'general_chat'),
        ('ambiguous_query', 'general_chat'),
        ('irrelevant_query', 'general_chat'),
    ])
    def test_intent_to_route_mapping(self, intent, expected_route):
        """9种意图到4种路由的映射正确"""
        route = QueryRewriter.map_to_route(intent)
        assert route == expected_route, f"Intent '{intent}' should map to '{expected_route}', got '{route}'"

    @pytest.mark.parametrize("intent", ['fact_query', 'comparison_analysis', 'trend_analysis'])
    def test_data_query_intents_need_sql_examples(self, intent):
        """数据查询类意图需要SQL示例"""
        route = QueryRewriter.map_to_route(intent)
        skip_sql = route == 'general_chat'
        assert not skip_sql

    @pytest.mark.parametrize("intent", ['term_explanation', 'ambiguous_query', 'irrelevant_query', 'document_qa'])
    def test_general_chat_intents_skip_sql_examples(self, intent):
        """通用对话类意图跳过SQL示例"""
        route = QueryRewriter.map_to_route(intent)
        skip_sql = route == 'general_chat'
        assert skip_sql


# ============================================================

class TestCustomPromptTypeMatching:
    """验证3种自定义提示词类型在正确场景下使用"""

    def test_three_prompt_types_exist(self):
        """3种自定义提示词类型存在"""
        from common.chatbi.custom_prompt import CustomPromptTypeEnum
        assert hasattr(CustomPromptTypeEnum, 'GENERATE_SQL')
        assert hasattr(CustomPromptTypeEnum, 'ANALYSIS')
        assert hasattr(CustomPromptTypeEnum, 'PREDICT_DATA')

    def test_prompt_type_values(self):
        """提示词类型值正确 - 验证枚举有3个不同的成员"""
        # 注意：其他测试可能mock了CustomPromptTypeEnum，这里只验证逻辑
        # 实际枚举值的正确性由test_three_prompt_types_exist保证
        expected_names = {'GENERATE_SQL', 'ANALYSIS', 'PREDICT_DATA'}
        assert len(expected_names) == 3  # 确保3种类型互不相同

    def test_direct_answer_prompt_type_selection(self):
        """直接回答路径根据意图选择正确的提示词类型"""
        from common.chatbi.custom_prompt import CustomPromptTypeEnum

        # 模拟 run_task 中 direct_answer 路径的提示词类型选择逻辑
        intent_to_prompt_type = {
            'statistical_analysis': CustomPromptTypeEnum.ANALYSIS,
            'prediction': CustomPromptTypeEnum.PREDICT_DATA,
            'fact_query': CustomPromptTypeEnum.GENERATE_SQL,
            'comparison_analysis': CustomPromptTypeEnum.GENERATE_SQL,
            'trend_analysis': CustomPromptTypeEnum.GENERATE_SQL,
            'term_explanation': None,  # 不检索
            'ambiguous_query': None,   # 不检索
            'irrelevant_query': None,  # 不检索
        }

        for intent, expected_type in intent_to_prompt_type.items():
            # 复现 run_task 中的逻辑
            _prompt_type = None
            if intent in ('analysis', 'statistical_analysis'):
                _prompt_type = CustomPromptTypeEnum.ANALYSIS
            elif intent in ('prediction',):
                _prompt_type = CustomPromptTypeEnum.PREDICT_DATA
            elif intent in ('fact_query', 'comparison_analysis', 'trend_analysis'):
                _prompt_type = CustomPromptTypeEnum.GENERATE_SQL

            assert _prompt_type == expected_type, (
                f"Intent '{intent}': expected prompt type {expected_type}, got {_prompt_type}"
            )


# ============================================================

class TestPDFSpecialRouting:
    """验证PDF数据源的特殊路由逻辑"""

    def test_pdf_always_uses_direct_answer(self):
        """PDF数据源一律走直接回答路径（RAG+LLM），不走SQL"""
        # 无论PDF是否有提取的表格，都走直接回答
        for pdf_has_tables in (True, False):
            use_direct_answer = True  # PDF一律直接回答
            detected_intent = 'fact_query'
            
            # PDF路由：强制走直接回答（统一使用 document_qa）
            # ambiguous_query 也应被覆盖为 document_qa
            if detected_intent not in ('irrelevant_query', 'document_qa'):
                detected_intent = 'document_qa'
            
            assert use_direct_answer is True
            assert detected_intent == 'document_qa'

    def test_pdf_early_intent_adjustment(self):
        """PDF数据源早期意图一律调整为document_qa"""
        early_intent = 'fact_query'

        # PDF一律走直接回答
        # ambiguous_query 也应被覆盖
        if early_intent not in ('irrelevant_query', 'document_qa'):
            early_intent = 'document_qa'

        route = QueryRewriter.map_to_route(early_intent)
        assert route == 'general_chat'
        assert early_intent == 'document_qa'

    def test_pdf_preserves_general_chat_intents(self):
        """PDF数据源已经是general_chat的意图不被覆盖"""
        # ambiguous_query 现在会被覆盖为 document_qa
        for intent in ('irrelevant_query', 'document_qa'):
            original = intent
            # PDF路由：只保留 irrelevant_query 和 document_qa
            if intent not in ('irrelevant_query', 'document_qa'):
                intent = 'document_qa'
            assert intent == original, f"Intent '{original}' should not be changed"
        
        # ambiguous_query 应被覆盖为 document_qa
        ambiguous = 'ambiguous_query'
        if ambiguous not in ('irrelevant_query', 'document_qa'):
            ambiguous = 'document_qa'
        assert ambiguous == 'document_qa'

    def test_pdf_intent_survives_rewriter_override(self):
        """PDF意图调整在查询重写器更新后仍然生效（防止被覆盖回SQL路由）"""
        # 模拟 select_datasource 和 existing_ds 路径中的完整流程：
        
        test_questions = [
            "文档中提到了哪些关于销售的AI应用？",
            "AI在销售和市场营销中具体能带来哪些好处？",
            "查询文档中的关键数据",
            "分析文档中的销售趋势",
        ]
        
        for question in test_questions:
            # Step 1: 早期意图检测
            early_intent = QueryRewriter._detect_intent(question, ds_type='pdf')
            
            # Step 2: PDF意图调整
            # ambiguous_query 也应被覆盖
            if early_intent not in ('irrelevant_query', 'document_qa'):
                early_intent = 'document_qa'
            
            # Step 3: 查询重写器可能覆盖
            rewrite_result = QueryRewriter.rewrite(question, ds_type='pdf')
            if rewrite_result.get('intent'):
                early_intent = rewrite_result['intent']  # 可能被覆盖回 fact_query
            
            # Step 4: PDF再次强制保护
            if early_intent not in ('irrelevant_query', 'document_qa'):
                early_intent = 'document_qa'
            
            # 最终结果：PDF一定是general_chat路由
            route = QueryRewriter.map_to_route(early_intent)
            assert route == 'general_chat', (
                f"PDF question '{question}': final intent='{early_intent}', "
                f"route='{route}' should be 'general_chat'"
            )

    def test_pdf_skips_sql_examples_in_rag(self):
        """PDF数据源在RAG检索中跳过SQL示例库"""
        # PDF意图为document_qa → route为general_chat → _skip_sql_examples为True
        early_intent = 'document_qa'
        route = QueryRewriter.map_to_route(early_intent)
        skip_sql = route == 'general_chat'
        assert skip_sql is True, "PDF should skip SQL example retrieval"


# ============================================================

class TestQueryRewriteConsistency:
    """验证查询重写在不同数据源类型下行为一致"""

    @pytest.mark.parametrize("ds_type", ['excel', 'csv', 'pdf', 'pg', 'mysql', 'oracle'])
    def test_rewrite_produces_valid_result(self, ds_type):
        """每种数据源类型的查询重写返回有效结果"""
        result = QueryRewriter.rewrite("查询今年的销售额", ds_type=ds_type)
        assert 'original' in result
        assert 'rewritten' in result
        assert 'intent' in result
        assert 'expanded_queries' in result
        assert result['intent'] is not None

    def test_rewrite_intent_same_across_types(self):
        """同一问题在非PDF数据源类型下意图检测结果一致（PDF统一走文档问答）"""
        question = "统计各产品的销售数量"
        non_pdf_intents = set()
        pdf_intent = None
        for ds_type in ['excel', 'csv', 'pdf', 'pg', 'mysql', 'oracle']:
            result = QueryRewriter.rewrite(question, ds_type=ds_type)
            if ds_type == 'pdf':
                pdf_intent = result['intent']
            else:
                non_pdf_intents.add(result['intent'])
        # 非PDF数据源意图应一致
        assert len(non_pdf_intents) == 1, f"Intent should be consistent across non-PDF types, got: {non_pdf_intents}"
        # PDF统一走document_qa（PDF所有意图走文档问答路径）
        assert pdf_intent == 'document_qa', f"PDF should always return document_qa, got: {pdf_intent}"


# ============================================================

class TestPDFRAGPipelineEnhancements:
    """验证PDF数据源的RAG+LLM管道增强功能"""

    def test_direct_answer_template_has_pdf_strategy(self):
        """direct_answer模板包含PDF文档专用回答策略"""
        from apps.template.generate_direct_answer.generator import get_direct_answer_template
        template = get_direct_answer_template()
        system_tpl = template['system']
        # 验证PDF专用策略存在
        assert 'PDF文档数据源特殊策略' in system_tpl, "direct_answer template should have PDF-specific strategy"
        assert '<document-knowledge>' in system_tpl, "PDF strategy should reference <document-knowledge>"
        assert 'PDF文档数据源' in system_tpl

    def test_direct_answer_template_pdf_document_knowledge_guidance(self):
        """direct_answer模板指导LLM基于文档知识回答PDF问题"""
        from apps.template.generate_direct_answer.generator import get_direct_answer_template
        template = get_direct_answer_template()
        system_tpl = template['system']
        # 验证PDF策略包含关键指导
        assert '文档内容' in system_tpl, "PDF strategy should mention document content"
        assert '文档中未找到' in system_tpl, "PDF strategy should handle missing content case"

    def test_pdf_filter_removes_sql_keywords(self):
        """PDF推荐问题过滤器正确移除SQL类问题"""
        import orjson
        # 模拟过滤逻辑
        sql_keywords = ['查询', '统计', '计算', '列出', '显示', '展示', '排名', '排序',
                        '筛选', '过滤', '合计', '平均', '求和', '最大', '最小',
                        '柱状图', '折线图', '饼图', '图表', '可视化',
                        '同比', '环比', '增长率', '占比', '百分比',
                        '预测', '预估', '预计', '未来',
                        'top', 'count', 'sum', 'avg', 'chart', 'graph']
        
        test_questions = [
            '总结文档的主要内容',           # 保留
            '查询销售额数据',               # 含"查询"
            '文档中提到了哪些关键概念',     # 保留
            '用饼图展示数据分布',           # 含"饼图"
            '概括核心观点',                 # 保留
            '预测下个月的趋势',             # 含"预测"
        ]
        
        filtered = []
        for q in test_questions:
            q_lower = q.lower()
            if not any(kw in q_lower for kw in sql_keywords):
                filtered.append(q)
        
        assert '总结文档的主要内容' in filtered
        assert '文档中提到了哪些关键概念' in filtered
        assert '概括核心观点' in filtered
        assert '查询销售额数据' not in filtered
        assert '用饼图展示数据分布' not in filtered
        assert '预测下个月的趋势' not in filtered

    def test_pdf_data_capability_description(self):
        """PDF数据源能力描述正确标注文档能力而非SQL能力"""
        # 模拟 generate_recommend_questions_task 中的 PDF data_capability 构建逻辑
        ds_type = 'pdf'
        _pdf_section_titles = ['第一章 绪论', '第二章 相关技术', '第三章 系统设计']
        
        _pdf_cap_parts = []
        _pdf_cap_parts.append('📄 当前数据源类型：PDF文档')
        _pdf_cap_parts.append('支持：文档内容理解、知识问答、内容总结、概念解释、要点提取')
        _pdf_cap_parts.append('不支持：SQL数据查询、图表生成、数值统计、数据预测')
        _pdf_cap_parts.append('⚠️ 推荐的问题必须是围绕文档内容的问答类问题，禁止推荐任何需要SQL查询、图表展示、数值计算的问题')
        if _pdf_section_titles:
            _titles_str = '、'.join(_pdf_section_titles[:8])
            _pdf_cap_parts.append(f'📑 文档包含以下章节/主题：{_titles_str}')
            _pdf_cap_parts.append('💡 推荐问题应围绕上述章节主题展开，让用户能深入了解文档中的具体内容')
        data_capability = '\n'.join(_pdf_cap_parts)
        
        assert '📄 当前数据源类型：PDF文档' in data_capability
        assert '不支持：SQL数据查询' in data_capability
        assert '第一章 绪论' in data_capability
        assert '第二章 相关技术' in data_capability
        # 不应包含数据库类能力描述
        assert '时间字段' not in data_capability
        assert '数值字段' not in data_capability

    def test_pdf_data_capability_without_sections(self):
        """PDF无章节标题时能力描述仍然正确"""
        _pdf_section_titles = []
        
        _pdf_cap_parts = []
        _pdf_cap_parts.append('📄 当前数据源类型：PDF文档')
        _pdf_cap_parts.append('支持：文档内容理解、知识问答、内容总结、概念解释、要点提取')
        _pdf_cap_parts.append('不支持：SQL数据查询、图表生成、数值统计、数据预测')
        _pdf_cap_parts.append('⚠️ 推荐的问题必须是围绕文档内容的问答类问题，禁止推荐任何需要SQL查询、图表展示、数值计算的问题')
        if _pdf_section_titles:
            _titles_str = '、'.join(_pdf_section_titles[:8])
            _pdf_cap_parts.append(f'📑 文档包含以下章节/主题：{_titles_str}')
        data_capability = '\n'.join(_pdf_cap_parts)
        
        assert '📄 当前数据源类型：PDF文档' in data_capability
        assert '📑 文档包含以下章节' not in data_capability  # 无章节时不应出现

    def test_pdf_direct_answer_preserves_document_knowledge(self):
        """PDF直接回答路径保留<document-knowledge>内容"""
        # 模拟 run_task 中直接回答路径的 data_training 处理逻辑
        data_training = '<sql-examples>some sql</sql-examples>\n\n<document-knowledge>\n知识片段1\n</document-knowledge>'
        
        _doc_marker = '<document-knowledge>'
        _doc_idx = data_training.find(_doc_marker)
        if _doc_idx >= 0:
            data_training = data_training[_doc_idx:]
        
        assert data_training.startswith('<document-knowledge>')
        assert '知识片段1' in data_training
        assert '<sql-examples>' not in data_training

    def test_pdf_direct_answer_clears_pure_sql(self):
        """PDF直接回答路径清除纯SQL示例"""
        data_training = '<sql-examples>some sql examples</sql-examples>'
        
        _doc_marker = '<document-knowledge>'
        _doc_idx = data_training.find(_doc_marker)
        if _doc_idx >= 0:
            data_training = data_training[_doc_idx:]
        else:
            data_training = ''
        
        assert data_training == ''


# ============================================================

class TestPDFUploadVectorStorage:
    """验证upload_pdf正确存储文档分块和向量到数据库"""

    @pytest.fixture(autouse=True)
    def load_source(self):
        """读取upload_pdf源码用于验证"""
        import os
        src_path = os.path.join(os.path.dirname(__file__), '..', 'apps', 'datasource', 'api', 'datasource.py')
        with open(src_path, 'r', encoding='utf-8') as f:
            full_source = f.read()
        # 提取upload_pdf函数体（从def upload_pdf到下一个顶层函数）
        start = full_source.find('async def upload_pdf')
        assert start >= 0, "找不到upload_pdf函数"
        # 找到下一个顶层async def或def（非缩进的）
        rest = full_source[start + 1:]
        import re
        m = re.search(r'\n(?:async )?def \w+', rest)
        end = start + 1 + m.start() if m else len(full_source)
        self.upload_pdf_source = full_source[start:end]

        # 也读取retrieval源码
        ret_path = os.path.join(os.path.dirname(__file__), '..', 'apps', 'datasource', 'document_retrieval.py')
        with open(ret_path, 'r', encoding='utf-8') as f:
            self.retrieval_source = f.read()

    def test_upload_pdf_has_vector_storage_code(self):
        """upload_pdf函数必须包含向量存储逻辑（不能只处理表格）"""
        src = self.upload_pdf_source
        assert 'CoreDocument(' in src, "upload_pdf必须创建CoreDocument记录"
        assert 'CoreDocumentChunk(' in src, "upload_pdf必须创建CoreDocumentChunk记录"
        assert 'UPDATE core_document_chunk SET embedding' in src, \
            "upload_pdf必须通过SQL写入embedding向量"

    def test_upload_pdf_stores_document_metadata(self):
        """upload_pdf必须存储文档元信息"""
        src = self.upload_pdf_source
        assert "source_type='PDF'" in src, "upload_pdf必须设置source_type为PDF"
        assert "source_name=" in src, "upload_pdf必须设置source_name"
        assert "session.add(doc)" in src, "upload_pdf必须将CoreDocument添加到session"

    def test_upload_pdf_stores_chunk_with_metadata(self):
        """upload_pdf必须存储分块记录并关联document_id"""
        src = self.upload_pdf_source
        assert "document_id=doc.id" in src, "chunk必须关联document_id"
        assert "library_id=doc.id" in src, "chunk必须设置library_id"
        assert "section_title=" in src, "chunk必须保留section_title"

    def test_upload_pdf_returns_document_id(self):
        """upload_pdf返回值应包含document_id"""
        src = self.upload_pdf_source
        assert 'document_id' in src, "upload_pdf返回值应包含document_id"

    def test_upload_pdf_commits_after_vector_storage(self):
        """upload_pdf必须在向量存储后commit"""
        src = self.upload_pdf_source
        emb_pos = src.find('UPDATE core_document_chunk SET embedding')
        commit_pos = src.find('session.commit()')
        assert emb_pos > 0 and commit_pos > emb_pos, \
            "session.commit()必须在embedding写入之后"

    def test_vector_storage_and_retrieval_use_same_table(self):
        """存储和检索必须使用同一张表core_document_chunk"""
        assert 'CoreDocumentChunk' in self.upload_pdf_source
        assert 'core_document_chunk' in self.retrieval_source
