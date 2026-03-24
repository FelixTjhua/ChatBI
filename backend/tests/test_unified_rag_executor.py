"""统一三阶段 RAG 执行器测试"""
import pytest
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
    COMPONENT_MATRIX,
)


# ========== 意图映射测试 ==========

class TestDesignIntentMapping:
    """测试 9 种细粒度意图 → 5 大意图"""

    def test_fact_query(self):
        assert map_to_design_intent("fact_query") == DesignIntent.DATA_QUERY

    def test_comparison_analysis(self):
        assert map_to_design_intent("comparison_analysis") == DesignIntent.DATA_ANALYSIS

    def test_statistical_analysis(self):
        assert map_to_design_intent("statistical_analysis") == DesignIntent.DATA_ANALYSIS

    def test_trend_analysis(self):
        assert map_to_design_intent("trend_analysis") == DesignIntent.DATA_ANALYSIS

    def test_prediction(self):
        assert map_to_design_intent("prediction") == DesignIntent.DATA_PREDICTION

    def test_term_explanation_pdf(self):
        assert map_to_design_intent("term_explanation", "pdf") == DesignIntent.DOCUMENT_QA

    def test_term_explanation_database(self):
        assert map_to_design_intent("term_explanation", "database") == DesignIntent.DATA_QUERY

    def test_follow_up_defaults(self):
        assert map_to_design_intent("follow_up") == DesignIntent.DATA_QUERY

    def test_ambiguous_defaults(self):
        assert map_to_design_intent("ambiguous_query") == DesignIntent.DATA_QUERY

    def test_irrelevant_defaults(self):
        assert map_to_design_intent("irrelevant_query") == DesignIntent.DATA_QUERY

    def test_unknown_defaults(self):
        assert map_to_design_intent("unknown_xyz") == DesignIntent.DATA_QUERY


# ========== 组件可用性矩阵测试 ==========

class TestComponentMatrix:
    """测试 4 数据源 × 6 组件矩阵"""

    def test_pdf_components(self):
        """PDF组件矩阵：PDF固定不走SQL路径，不需要商业术语库"""
        c = get_available_components("pdf", has_table=True)
        assert c["terminology"] is False       # PDF不需要商业术语库
        assert c["sql_prompt"] is False        # PDF不走SQL路径
        assert c["sql_examples"] is False      # PDF不走SQL路径
        assert c["analysis_prompt"] is False   # PDF不做数据分析
        assert c["prediction_prompt"] is False # PDF不做数据预测
        assert c["antv_g2"] is False           # PDF不做数据可视化

    def test_pdf_no_table(self):
        """PDF无论has_table值如何，组件矩阵结果一致"""
        c = get_available_components("pdf", has_table=False)
        assert c["terminology"] is False       # PDF不需要商业术语库
        assert c["sql_prompt"] is False        # PDF不走SQL路径
        assert c["sql_examples"] is False      # PDF不走SQL路径
        assert c["analysis_prompt"] is False   # PDF不做数据分析
        assert c["prediction_prompt"] is False # PDF不做数据预测
        assert c["antv_g2"] is False           # PDF不做数据可视化

    def test_excel_components(self):
        c = get_available_components("excel")
        assert c["terminology"] is True
        assert c["sql_prompt"] is True
        assert c["sql_examples"] is True
        assert c["analysis_prompt"] is True
        assert c["prediction_prompt"] is True
        assert c["antv_g2"] is True

    def test_csv_components(self):
        c = get_available_components("csv")
        assert c["terminology"] is True
        assert c["sql_prompt"] is True
        assert c["sql_examples"] is True
        assert c["analysis_prompt"] is True
        assert c["antv_g2"] is True

    def test_database_components(self):
        c = get_available_components("database")
        assert c["terminology"] is True
        assert c["sql_prompt"] is True
        assert c["sql_examples"] is True
        assert c["analysis_prompt"] is True
        assert c["prediction_prompt"] is True
        assert c["antv_g2"] is True

    def test_unknown_type_defaults_to_database(self):
        c = get_available_components("mysql")
        assert c["sql_prompt"] is True
        assert c["sql_examples"] is True

    def test_all_four_sources_in_matrix(self):
        for ds in ["pdf", "excel", "csv", "database"]:
            assert ds in COMPONENT_MATRIX


# ========== 执行路径决策测试 ==========

class TestExecutionPath:
    """测试意图 + 数据源 → 执行路径"""

    def test_document_qa_path(self):
        path = get_execution_path(DesignIntent.DOCUMENT_QA, "pdf")
        assert path["direct_answer"] is True
        assert path["sql_generation"] is False
        assert path["analysis"] is False
        assert path["prediction"] is False

    def test_data_query_path(self):
        path = get_execution_path(DesignIntent.DATA_QUERY, "database")
        assert path["sql_generation"] is True
        assert path["direct_answer"] is False

    def test_data_analysis_path(self):
        path = get_execution_path(DesignIntent.DATA_ANALYSIS, "excel")
        assert path["sql_generation"] is True
        assert path["analysis"] is True
        assert path["visualization"] is True

    def test_data_prediction_path(self):
        path = get_execution_path(DesignIntent.DATA_PREDICTION, "database")
        assert path["sql_generation"] is True
        assert path["prediction"] is True
        assert path["visualization"] is True

    def test_visualization_path(self):
        path = get_execution_path(DesignIntent.VISUALIZATION, "csv")
        assert path["sql_generation"] is True
        assert path["visualization"] is True
        assert path["analysis"] is False


# ========== 数据结构测试 ==========

class TestDataStructures:
    """测试三阶段数据结构"""

    def test_pipeline_context(self):
        ctx = PipelineContext(question="查询销售额", ds_type="database", oid=1)
        assert ctx.question == "查询销售额"
        assert ctx.ds_type == "database"

    def test_retrieve_result_defaults(self):
        r = RetrieveResult()
        assert r.intent == ""
        assert r.terminology_results == []
        assert r.doc_chunk_results == []

    def test_augment_result_defaults(self):
        a = AugmentResult()
        assert a.visualization_detected is False
        assert a.compression_applied is False

    def test_generate_result_defaults(self):
        g = GenerateResult()
        assert g.text_answer == ""
        assert g.provenance == []
        assert g.post_recommendations == []


# ========== DesignIntent 常量测试 ==========

class TestDesignIntentConstants:
    """测试 5 大意图常量"""

    def test_all_five_intents(self):
        assert len(DesignIntent.ALL) == 5
        assert DesignIntent.DOCUMENT_QA in DesignIntent.ALL
        assert DesignIntent.DATA_QUERY in DesignIntent.ALL
        assert DesignIntent.DATA_ANALYSIS in DesignIntent.ALL
        assert DesignIntent.DATA_PREDICTION in DesignIntent.ALL
        assert DesignIntent.VISUALIZATION in DesignIntent.ALL

    def test_intent_values(self):
        assert DesignIntent.DOCUMENT_QA == "document_qa"
        assert DesignIntent.DATA_QUERY == "data_query"
        assert DesignIntent.DATA_ANALYSIS == "data_analysis"
        assert DesignIntent.DATA_PREDICTION == "data_prediction"
        assert DesignIntent.VISUALIZATION == "visualization"


# ========== PDF 文档 RAG 流水线测试 ==========

from apps.chat.thinking.unified_rag_executor import (
    format_pdf_context,
    get_pdf_source_summary,
    _build_system_prompt,
    _build_user_prompt,
    _build_provenance,
)


class TestPDFSystemPrompt:
    """测试 PDF 文档问答的约束型 Prompt 构建"""

    def test_pdf_document_qa_prompt_has_constraints(self):
        """PDF 文档问答 Prompt 必须包含约束规则"""
        prompt = _build_system_prompt(
            intent=DesignIntent.DOCUMENT_QA,
            ds_type="pdf",
            components=get_available_components("pdf"),
            doc_chunks=[{
                "text": "2025年营收增长15%",
                "source_name": "年报.pdf",
                "page_number": 12,
                "section_title": "财务概要",
                "similarity": 0.89,
                "chunk_type": "text",
            }],
        )
        # 必须包含约束规则
        assert "仅依据" in prompt
        assert "不得编造" in prompt
        assert "标注来源" in prompt
        assert "document-knowledge" in prompt
        assert "年报.pdf" in prompt
        assert "第12页" in prompt
        assert "财务概要" in prompt

    def test_pdf_document_qa_prompt_no_sql_components(self):
        """PDF 文档问答意图 Prompt 不包含 SQL（走 direct_answer 路径）"""
        prompt = _build_system_prompt(
            intent=DesignIntent.DOCUMENT_QA,
            ds_type="pdf",
            components=get_available_components("pdf"),
            sql_examples_xml="<example>SELECT * FROM sales</example>",
            schema_xml="<table>sales</table>",
        )
        # 文档问答路径不使用 SQL，即使组件矩阵允许
        assert "sql-examples" not in prompt
        assert "database-schema" not in prompt

    def test_pdf_prompt_empty_chunks(self):
        """无检索结果时应提示未找到"""
        prompt = _build_system_prompt(
            intent=DesignIntent.DOCUMENT_QA,
            ds_type="pdf",
            components=get_available_components("pdf"),
            doc_chunks=[],
        )
        assert "未检索到" in prompt

    def test_pdf_prompt_without_terminologies(self):
        """PDF Prompt 不应包含术语库（PDF纯文档问答，不需要商业术语库）"""
        prompt = _build_system_prompt(
            intent=DesignIntent.DOCUMENT_QA,
            ds_type="pdf",
            components=get_available_components("pdf"),
            terminologies_xml="",
            doc_chunks=[{"text": "test", "source_name": "t.pdf", "page_number": 1, "similarity": 0.5, "chunk_type": "text"}],
        )
        assert "ROI" not in prompt


class TestPDFUserPrompt:
    """测试 PDF 文档问答的用户提示词"""

    def test_pdf_user_prompt_has_constraints(self):
        prompt = _build_user_prompt(
            question="文档的核心结论是什么？",
            intent=DesignIntent.DOCUMENT_QA,
            ds_type="pdf",
        )
        assert "严格基于" in prompt
        assert "document-knowledge" in prompt
        assert "文档的核心结论是什么？" in prompt

    def test_non_pdf_user_prompt(self):
        prompt = _build_user_prompt(
            question="查询销售额",
            intent=DesignIntent.DATA_QUERY,
            ds_type="database",
        )
        assert "document-knowledge" not in prompt
        assert "查询销售额" in prompt


class TestPDFProvenance:
    """测试 PDF 溯源凭证构建"""

    def test_pdf_provenance_with_chunks(self):
        ctx = PipelineContext(ds_type="pdf", ds_name="report.pdf")
        retrieve = RetrieveResult(
            doc_chunk_results=[
                {"source_name": "report.pdf", "page_number": 5, "section_title": "摘要", "chunk_type": "text", "similarity": 0.92},
                {"source_name": "report.pdf", "page_number": 12, "section_title": "结论", "chunk_type": "table", "similarity": 0.85, "table_index": 2},
            ]
        )
        prov = _build_provenance(ctx, retrieve)
        # 2 chunk entries + 1 summary
        assert len(prov) == 3
        assert prov[0]["page_number"] == 5
        assert prov[1]["table_index"] == 2
        assert prov[2]["source_type"] == "pdf_summary"
        assert 5 in prov[2]["pages_referenced"]
        assert 12 in prov[2]["pages_referenced"]

    def test_pdf_provenance_empty(self):
        ctx = PipelineContext(ds_type="pdf", ds_name="empty.pdf")
        retrieve = RetrieveResult(doc_chunk_results=[])
        prov = _build_provenance(ctx, retrieve)
        assert len(prov) == 0


class TestFormatPDFContext:
    """测试 PDF 上下文格式化"""

    def test_basic_formatting(self):
        chunks = [
            {"text": "营收增长15%", "source_name": "年报.pdf", "page_number": 3, "section_title": "财务", "similarity": 0.9, "chunk_type": "text"},
            {"text": "表格数据", "source_name": "年报.pdf", "page_number": 5, "section_title": "", "similarity": 0.8, "chunk_type": "table"},
        ]
        ctx = format_pdf_context(chunks)
        assert "片段1" in ctx
        assert "片段2" in ctx
        assert "年报.pdf" in ctx
        assert "第3页" in ctx
        assert "表格数据" in ctx

    def test_empty_chunks(self):
        assert format_pdf_context([]) == ""

    def test_max_chars_limit(self):
        chunks = [
            {"text": "短文本", "source_name": "a.pdf", "page_number": 1, "similarity": 0.9, "chunk_type": "text"},
            {"text": "x" * 5000, "source_name": "b.pdf", "page_number": 2, "similarity": 0.8, "chunk_type": "text"},
        ]
        ctx = format_pdf_context(chunks, max_chars=200)
        # 第一个短片段应被包含，第二个超长片段应被截断
        assert "短文本" in ctx
        assert len(ctx) < 5000


class TestGetPDFSourceSummary:
    """测试 PDF 来源摘要"""

    def test_summary_with_data(self):
        chunks = [
            {"page_number": 3, "section_title": "摘要", "similarity": 0.9, "chunk_type": "text", "source_name": "a.pdf"},
            {"page_number": 5, "section_title": "结论", "similarity": 0.8, "chunk_type": "table", "source_name": "a.pdf"},
            {"page_number": 3, "section_title": "摘要", "similarity": 0.7, "chunk_type": "text", "source_name": "b.pdf"},
        ]
        summary = get_pdf_source_summary(chunks)
        assert summary["total_chunks"] == 3
        assert summary["pages"] == [3, 5]
        assert "摘要" in summary["sections"]
        assert summary["has_tables"] is True
        assert len(summary["source_files"]) == 2
        assert summary["avg_similarity"] == round((0.9 + 0.8 + 0.7) / 3, 4)

    def test_summary_empty(self):
        summary = get_pdf_source_summary([])
        assert summary["total_chunks"] == 0
        assert summary["has_tables"] is False


class TestPDFIntentMapping:
    """测试 PDF 数据源的意图映射"""

    def test_pdf_term_explanation_maps_to_document_qa(self):
        assert map_to_design_intent("term_explanation", "pdf") == DesignIntent.DOCUMENT_QA

    def test_pdf_fact_query_maps_to_document_qa(self):
        """PDF所有意图统一映射到DOCUMENT_QA（不走SQL路径）"""
        assert map_to_design_intent("fact_query", "pdf") == DesignIntent.DOCUMENT_QA

    def test_pdf_prediction_maps_to_document_qa(self):
        """PDF不支持数据预测，统一映射到DOCUMENT_QA"""
        assert map_to_design_intent("prediction", "pdf") == DesignIntent.DOCUMENT_QA


class TestPDFExecutionPath:
    """测试 PDF 的执行路径决策"""

    def test_pdf_document_qa_uses_direct_answer(self):
        path = get_execution_path(DesignIntent.DOCUMENT_QA, "pdf")
        assert path["direct_answer"] is True
        assert path["sql_generation"] is False

    def test_pdf_data_query_uses_direct_answer(self):
        """PDF所有意图走直接回答路径，不走SQL"""
        path = get_execution_path(DesignIntent.DATA_QUERY, "pdf")
        assert path["sql_generation"] is False
        assert path["direct_answer"] is True

    def test_pdf_visualization_uses_direct_answer(self):
        """PDF不支持可视化，统一走直接回答"""
        path = get_execution_path(DesignIntent.VISUALIZATION, "pdf")
        assert path["visualization"] is False
        assert path["direct_answer"] is True
