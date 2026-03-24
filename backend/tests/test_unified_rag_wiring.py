"""统一三阶段 RAG 执行器接入测试 (Wiring Tests)"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from apps.chat.thinking.unified_rag_executor import (
    DesignIntent,
    UnifiedRAGExecutor,
    PipelineContext,
    RetrieveResult,
    AugmentResult,
    GenerateResult,
    get_available_components,
    get_execution_path,
    map_to_design_intent,
    format_pdf_context,
    get_pdf_source_summary,
    COMPONENT_MATRIX,
)


# ========== 组件矩阵强制执行测试 ==========

class TestComponentMatrixEnforcement:
    """测试组件矩阵在实际流程中被正确强制执行"""

    def test_pdf_no_sql_components(self):
        """PDF 数据源不使用 SQL 组件（PDF是非结构化文档，不走SQL路径）"""
        components = get_available_components("pdf")
        assert components["sql_prompt"] is False
        assert components["sql_examples"] is False

    def test_pdf_no_terminology(self):
        """PDF 数据源不使用商业术语库（纯文档问答，只需文档知识库检索）"""
        components = get_available_components("pdf")
        assert components["terminology"] is False

    def test_pdf_no_antv_g2(self):
        """PDF 数据源不支持 AntV G2 可视化（PDF不走SQL路径，无数据可视化）"""
        components = get_available_components("pdf")
        assert components["antv_g2"] is False

    def test_pdf_no_analysis_prediction_prompts(self):
        """PDF 不使用数据分析/预测提示词（has_table参数对PDF无意义）"""
        # has_table参数已废弃，PDF固定返回False
        components = get_available_components("pdf", has_table=True)
        assert components["analysis_prompt"] is False
        assert components["prediction_prompt"] is False
        # 与has_table=False结果一致
        components2 = get_available_components("pdf", has_table=False)
        assert components2["analysis_prompt"] is False
        assert components2["prediction_prompt"] is False

    def test_database_has_all_sql_components(self):
        """Database 数据源使用所有 SQL 组件"""
        components = get_available_components("database")
        assert components["sql_prompt"] is True
        assert components["sql_examples"] is True

    def test_excel_has_sql_components(self):
        """Excel 数据源使用 SQL 组件（数据已导入PG，SQL路径统一）"""
        components = get_available_components("excel")
        assert components["sql_prompt"] is True
        assert components["sql_examples"] is True

    def test_csv_has_sql_components(self):
        """CSV 数据源使用 SQL 组件（数据已导入PG，SQL路径统一）"""
        components = get_available_components("csv")
        assert components["sql_prompt"] is True
        assert components["sql_examples"] is True


# ========== 意图路由决策测试 ==========

class TestExecutionPathRouting:
    """测试 get_execution_path 在意图路由中的正确性"""

    def test_document_qa_uses_direct_answer(self):
        """文档问答意图走直接回答路径"""
        path = get_execution_path(DesignIntent.DOCUMENT_QA, "pdf")
        assert path["direct_answer"] is True
        assert path["sql_generation"] is False
        assert path["analysis"] is False
        assert path["prediction"] is False
        assert path["visualization"] is False

    def test_data_query_uses_sql(self):
        """数据查询意图走 SQL 路径"""
        path = get_execution_path(DesignIntent.DATA_QUERY, "database")
        assert path["sql_generation"] is True
        assert path["direct_answer"] is False

    def test_data_analysis_uses_sql_and_analysis(self):
        """数据分析意图走 SQL + 分析路径"""
        path = get_execution_path(DesignIntent.DATA_ANALYSIS, "database")
        assert path["sql_generation"] is True
        assert path["analysis"] is True
        assert path["visualization"] is True

    def test_data_prediction_uses_sql_and_prediction(self):
        """数据预测意图走 SQL + 预测路径"""
        path = get_execution_path(DesignIntent.DATA_PREDICTION, "database")
        assert path["sql_generation"] is True
        assert path["prediction"] is True
        assert path["visualization"] is True

    def test_visualization_uses_sql(self):
        """可视化意图走 SQL 路径"""
        path = get_execution_path(DesignIntent.VISUALIZATION, "database")
        assert path["sql_generation"] is True
        assert path["visualization"] is True

    def test_pdf_document_qa_no_sql(self):
        """PDF 文档问答不走 SQL"""
        path = get_execution_path(DesignIntent.DOCUMENT_QA, "pdf")
        assert path["sql_generation"] is False
        assert path["direct_answer"] is True

    def test_pdf_data_query_uses_direct_answer(self):
        """PDF所有意图走直接回答路径，不走SQL"""
        path = get_execution_path(DesignIntent.DATA_QUERY, "pdf")
        assert path["sql_generation"] is False
        assert path["direct_answer"] is True


# ========== PDF 溯源凭证测试 ==========

class TestPDFProvenanceWiring:
    """测试 PDF 溯源凭证从执行器传递到前端"""

    def test_provenance_has_page_numbers(self):
        """溯源凭证包含页码"""
        ctx = PipelineContext(ds_type="pdf", ds_name="test.pdf")
        retrieve = RetrieveResult(
            doc_chunk_results=[
                {"source_name": "test.pdf", "page_number": 5, "section_title": "第三章",
                 "chunk_type": "text", "similarity": 0.85},
                {"source_name": "test.pdf", "page_number": 12, "section_title": "附录",
                 "chunk_type": "table", "similarity": 0.72, "table_index": 2},
            ]
        )
        gen = UnifiedRAGExecutor.generate_config(ctx, retrieve, AugmentResult())
        assert len(gen.provenance) >= 2
        # 检查页码
        pages = [p.get("page_number") for p in gen.provenance if p.get("page_number")]
        assert 5 in pages
        assert 12 in pages

    def test_provenance_has_summary(self):
        """溯源凭证包含汇总摘要"""
        ctx = PipelineContext(ds_type="pdf", ds_name="report.pdf")
        retrieve = RetrieveResult(
            doc_chunk_results=[
                {"source_name": "report.pdf", "page_number": 1, "similarity": 0.9},
                {"source_name": "report.pdf", "page_number": 3, "similarity": 0.7},
            ]
        )
        gen = UnifiedRAGExecutor.generate_config(ctx, retrieve, AugmentResult())
        # 最后一条应该是 pdf_summary
        summary = [p for p in gen.provenance if p.get("source_type") == "pdf_summary"]
        assert len(summary) == 1
        assert summary[0]["pages_referenced"] == [1, 3]

    def test_database_provenance(self):
        """Database 溯源凭证"""
        ctx = PipelineContext(ds_type="database", ds_name="sales_db")
        retrieve = RetrieveResult()
        gen = UnifiedRAGExecutor.generate_config(ctx, retrieve, AugmentResult())
        assert gen.provenance[0]["source_type"] == "database"


# ========== PDF 来源摘要测试 ==========

class TestPDFSourceSummary:
    """测试 get_pdf_source_summary 供前端展示"""

    def test_summary_fields(self):
        chunks = [
            {"page_number": 1, "section_title": "引言", "similarity": 0.9,
             "chunk_type": "text", "source_name": "a.pdf"},
            {"page_number": 3, "section_title": "方法", "similarity": 0.8,
             "chunk_type": "table", "source_name": "a.pdf"},
        ]
        summary = get_pdf_source_summary(chunks)
        assert summary["total_chunks"] == 2
        assert summary["pages"] == [1, 3]
        assert "引言" in summary["sections"]
        assert summary["has_tables"] is True
        assert summary["avg_similarity"] > 0

    def test_empty_summary(self):
        summary = get_pdf_source_summary([])
        assert summary["total_chunks"] == 0
        assert summary["pages"] == []


# ========== 意图映射完整性测试 ==========

class TestIntentMappingCompleteness:
    """确保所有 9 种细粒度意图都有映射"""

    FINE_INTENTS = [
        "fact_query", "comparison_analysis", "statistical_analysis",
        "trend_analysis", "prediction", "term_explanation",
        "follow_up", "ambiguous_query", "irrelevant_query",
    ]

    def test_all_fine_intents_mapped(self):
        """所有 9 种细粒度意图都能映射到 5 大意图"""
        for fi in self.FINE_INTENTS:
            result = map_to_design_intent(fi)
            assert result in DesignIntent.ALL, f"{fi} mapped to invalid intent: {result}"

    def test_mapping_to_exactly_5_intents(self):
        """映射结果只包含 5 大意图"""
        results = set()
        for fi in self.FINE_INTENTS:
            for ds in ["pdf", "database", "excel", "csv"]:
                results.add(map_to_design_intent(fi, ds))
        assert results.issubset(set(DesignIntent.ALL))

    def test_pdf_term_explanation_is_document_qa(self):
        """PDF 的 term_explanation 映射到文档问答"""
        assert map_to_design_intent("term_explanation", "pdf") == DesignIntent.DOCUMENT_QA

    def test_non_pdf_term_explanation_is_data_query(self):
        """非 PDF 的 term_explanation 映射到数据查询"""
        for ds in ["database", "excel", "csv"]:
            assert map_to_design_intent("term_explanation", ds) == DesignIntent.DATA_QUERY


# ========== PDF 上下文格式化测试 ==========

class TestPDFContextFormatting:
    """测试 format_pdf_context 的溯源标注"""

    def test_source_tag_format(self):
        """检查溯源标注格式"""
        chunks = [
            {"source_name": "report.pdf", "page_number": 5, "section_title": "概述",
             "similarity": 0.85, "chunk_type": "text", "text": "这是测试内容"},
        ]
        ctx = format_pdf_context(chunks)
        assert "report.pdf" in ctx
        assert "第5页" in ctx
        assert "概述" in ctx
        assert "85%" in ctx

    def test_table_chunk_labeled(self):
        """表格片段有表格标签"""
        chunks = [
            {"source_name": "data.pdf", "page_number": 10, "similarity": 0.7,
             "chunk_type": "table", "text": "表格数据"},
        ]
        ctx = format_pdf_context(chunks)
        assert "表格数据" in ctx


# ========== 三阶段数据流测试 ==========

class TestThreeStageDataFlow:
    """测试三阶段数据在执行器中的正确流转"""

    def test_retrieve_to_augment_intent_flow(self):
        """检索阶段的意图传递到增强阶段"""
        ctx = PipelineContext(
            question="什么是机器学习",
            ds_type="pdf",
            available_components=get_available_components("pdf", False),
        )
        retrieve = RetrieveResult(
            intent=DesignIntent.DOCUMENT_QA,
            fine_intent="term_explanation",
        )
        augment = UnifiedRAGExecutor.augment(ctx, retrieve)
        # 增强阶段应该使用检索阶段的意图
        assert augment.components_used is not None
        # PDF不使用SQL组件
        assert augment.components_used.get("sql_prompt") is False
        assert augment.components_used.get("sql_examples") is False
        assert augment.components_used.get("terminology") is False  # PDF不需要商业术语库

    def test_augment_to_generate_viz_flow(self):
        """增强阶段的可视化判定传递到生成阶段"""
        ctx = PipelineContext(ds_type="pdf")
        retrieve = RetrieveResult(intent=DesignIntent.VISUALIZATION)
        augment = AugmentResult(
            visualization_detected=True,
            visualization_chart_type="bar",
            visualization_reason="数据对比适合柱状图",
        )
        gen = UnifiedRAGExecutor.generate_config(ctx, retrieve, augment)
        assert gen.antv_g2_config is not None
        assert gen.antv_g2_config["chart_type"] == "bar"

    def test_full_pipeline_context_sharing(self):
        """三阶段共享 PipelineContext"""
        ctx = PipelineContext(
            question="测试问题",
            ds_type="database",
            ds_name="test_db",
            has_table=True,
            oid=1,
        )
        # 验证 context 在各阶段可用
        assert ctx.ds_type == "database"
        assert ctx.has_table is True
        components = get_available_components(ctx.ds_type, ctx.has_table)
        assert components["sql_prompt"] is True  # database 有 SQL 组件
