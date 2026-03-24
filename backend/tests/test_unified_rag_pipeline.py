"""统一RAG执行框架测试"""
import pytest
from apps.chat.thinking.unified_rag_pipeline import (
    IntentType, DataSourceType,
    ProvenanceRecord, RAGPipelineResult,
    map_fine_intent_to_design_intent,
    decompose_complex_intent,
    get_ds_capabilities,
    build_provenance_from_doc_chunks,
    build_provenance_from_sql,
    build_provenance_from_excel,
    build_provenance_from_csv,
)


class TestIntentMapping:
    """测试9种细粒度意图→5类意图的映射"""
    def test_fact_query_maps_to_data_query(self):
        assert map_fine_intent_to_design_intent("fact_query") == IntentType.DATA_QUERY
    def test_comparison_maps_to_data_analysis(self):
        assert map_fine_intent_to_design_intent("comparison_analysis") == IntentType.DATA_ANALYSIS
    def test_statistical_maps_to_data_analysis(self):
        assert map_fine_intent_to_design_intent("statistical_analysis") == IntentType.DATA_ANALYSIS
    def test_trend_maps_to_data_analysis(self):
        assert map_fine_intent_to_design_intent("trend_analysis") == IntentType.DATA_ANALYSIS
    def test_prediction_maps_to_data_prediction(self):
        assert map_fine_intent_to_design_intent("prediction") == IntentType.DATA_PREDICTION
    def test_term_explanation_pdf_maps_to_document_qa(self):
        assert map_fine_intent_to_design_intent("term_explanation", ds_type="pdf") == IntentType.DOCUMENT_QA
    def test_term_explanation_database_maps_to_data_query(self):
        assert map_fine_intent_to_design_intent("term_explanation", ds_type="database") == IntentType.DATA_QUERY
    def test_unknown_intent_defaults_to_data_query(self):
        assert map_fine_intent_to_design_intent("unknown") == IntentType.DATA_QUERY


class TestComplexIntentDecomposition:
    """测试复杂意图拆解"""
    def test_viz_keyword(self):
        intents = decompose_complex_intent("分析销售趋势并生成图表", IntentType.DATA_ANALYSIS)
        assert IntentType.VISUALIZATION in intents
    def test_prediction_keyword(self):
        intents = decompose_complex_intent("分析2025年销售并预测2026年", IntentType.DATA_ANALYSIS)
        assert IntentType.DATA_PREDICTION in intents
    def test_analysis_keyword(self):
        intents = decompose_complex_intent("查询销售额并分析趋势", IntentType.DATA_QUERY)
        assert IntentType.DATA_ANALYSIS in intents
    def test_no_duplicate(self):
        intents = decompose_complex_intent("分析销售数据", IntentType.DATA_ANALYSIS)
        assert intents.count(IntentType.DATA_ANALYSIS) == 1
    def test_simple_query(self):
        intents = decompose_complex_intent("查询今年的销售额", IntentType.DATA_QUERY)
        assert intents == [IntentType.DATA_QUERY]
    def test_full_complex(self):
        intents = decompose_complex_intent("分析各区域销售趋势并预测明年，生成对比图表", IntentType.DATA_QUERY)
        assert IntentType.DATA_QUERY in intents
        assert IntentType.DATA_ANALYSIS in intents
        assert IntentType.DATA_PREDICTION in intents
        assert IntentType.VISUALIZATION in intents


class TestDataSourceCapabilities:
    """测试数据源能力矩阵"""
    def test_pdf_document_qa(self):
        caps = get_ds_capabilities("pdf")
        assert caps["document_qa"] is True
        # PDF是非结构化文档，不走SQL路径
        assert caps["sql_generation"] is False
    def test_excel_no_document_qa(self):
        caps = get_ds_capabilities("excel")
        assert caps["document_qa"] is False
        # Excel 数据已导入PG，统一走SQL路径
        assert caps["sql_generation"] is True
    def test_csv_batch(self):
        caps = get_ds_capabilities("csv")
        assert caps["batch_processing"] is True
        # CSV 数据已导入PG，统一走SQL路径
        assert caps["sql_generation"] is True
    def test_database_full(self):
        caps = get_ds_capabilities("database")
        assert caps["sql_generation"] is True
        assert caps["realtime_refresh"] is True
        assert caps["chart_drilldown"] is True
    def test_all_support_viz(self):
        # PDF不支持可视化（非结构化文档）
        assert get_ds_capabilities("pdf")["visualization"] is False
        for ds in ["excel", "csv", "database"]:
            assert get_ds_capabilities(ds)["visualization"] is True
    def test_only_db_drilldown(self):
        for ds in ["pdf", "excel", "csv"]:
            assert get_ds_capabilities(ds)["chart_drilldown"] is False
        assert get_ds_capabilities("database")["chart_drilldown"] is True
    def test_all_support_sql_generation(self):
        """PDF不走SQL路径，其他数据源统一启用SQL生成（数据已导入PG）"""
        assert get_ds_capabilities("pdf")["sql_generation"] is False
        for ds in ["excel", "csv", "database"]:
            assert get_ds_capabilities(ds)["sql_generation"] is True


class TestProvenanceRecords:
    """测试溯源凭证生成"""
    def test_pdf_from_chunks(self):
        chunks = [{"source_name": "report.pdf", "page_number": 12, "section_title": "3.2", "similarity": 0.89, "chunk_type": "text"}]
        records = build_provenance_from_doc_chunks(chunks, source_type="pdf")
        assert len(records) == 1
        assert records[0].page_number == 12
    def test_pdf_table(self):
        chunks = [{"source_name": "r.pdf", "page_number": 5, "chunk_type": "table", "table_index": 2, "similarity": 0.75}]
        records = build_provenance_from_doc_chunks(chunks)
        assert records[0].table_index == 2
    def test_sql(self):
        record = build_provenance_from_sql(sql="SELECT * FROM sales", execution_time=0.15, ds_name="prod_db", cache_status="miss")
        assert record.source_type == "database"
        assert record.sql_statement == "SELECT * FROM sales"
        assert record.cache_status == "miss"
    def test_excel(self):
        record = build_provenance_from_excel(sheet_name="Sheet1", row_range="2-50", source_name="data.xlsx")
        assert record.source_type == "excel"
        assert record.sheet_name == "Sheet1"
    def test_csv(self):
        record = build_provenance_from_csv(row_range="1-1000", batch_index=0, source_name="data.csv", processing_rules=["去重"])
        assert record.source_type == "csv"
        assert record.batch_index == 0
    def test_to_dict_pdf(self):
        record = ProvenanceRecord(source_type="pdf", source_name="r.pdf", page_number=3, section_title="Summary")
        d = record.to_dict()
        assert d["page_number"] == 3
        assert "sheet_name" not in d
    def test_to_dict_db(self):
        record = ProvenanceRecord(source_type="database", source_name="prod", sql_statement="SELECT 1", execution_time=0.05, cache_status="hit")
        d = record.to_dict()
        assert d["execution_time_ms"] == 50.0
        assert d["cache_status"] == "hit"
    def test_source_tag(self):
        record = ProvenanceRecord(source_type="pdf", source_name="年报.pdf", page_number=12, section_title="3.2节")
        tag = record.to_source_tag()
        assert "年报.pdf" in tag
        assert "第12页" in tag


class TestRAGPipelineResultEncapsulation:
    """测试统一执行结果封装"""
    def test_basic(self):
        result = RAGPipelineResult(text_answer="销售额为100万", intent_type=IntentType.DATA_QUERY, ds_type="database")
        d = result.to_dict()
        assert d["text_answer"] == "销售额为100万"
        assert d["visualization"] is None
    def test_with_viz(self):
        result = RAGPipelineResult(text_answer="趋势", intent_type=IntentType.DATA_ANALYSIS, visualization_enabled=True, visualization_config={"type": "line"})
        d = result.to_dict()
        assert d["visualization"]["enabled"] is True
    def test_with_recommendations(self):
        result = RAGPipelineResult(pre_recommendations=[{"question": "q1"}], mid_recommendations=[{"question": "q2"}], post_recommendations=[{"question": "q3"}])
        d = result.to_dict()
        assert len(d["recommendations"]["pre"]) == 1
    def test_with_provenance(self):
        prov = ProvenanceRecord(source_type="database", source_name="db", sql_statement="SELECT 1", execution_time=0.2, cache_status="miss")
        result = RAGPipelineResult(provenance=[prov])
        d = result.to_dict()
        assert len(d["provenance"]) == 1
    def test_metadata(self):
        result = RAGPipelineResult(ds_type="excel", processing_time=1.5, rag_quality_score=0.85)
        d = result.to_dict()
        assert d["metadata"]["processing_time_ms"] == 1500.0
    def test_sub_intents(self):
        result = RAGPipelineResult(intent_type=IntentType.DATA_QUERY, sub_intents=[IntentType.DATA_ANALYSIS, IntentType.VISUALIZATION])
        d = result.to_dict()
        assert len(d["sub_intents"]) == 2
