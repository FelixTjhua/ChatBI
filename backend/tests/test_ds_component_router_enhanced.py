"""增强数据源组件路由器测试"""
import pytest
from apps.chat.thinking.ds_component_router import get_allowed_components


class TestEnhancedComponentMatrix:
    """测试增强的组件可用性矩阵"""

    def test_pdf_document_qa(self):
        components = get_allowed_components("pdf")
        assert components["document_qa"] is True
        assert components["terminology"] is False  # PDF不需要商业术语库
        # PDF是非结构化文档，不走SQL路径
        assert components["sql_generation_prompt"] is False
        assert components["sql_example_library"] is False
        assert components["visualization"] is False
        assert components["batch_processing"] is False
        assert components["realtime_refresh"] is False

    def test_csv_batch_processing(self):
        components = get_allowed_components("csv")
        assert components["batch_processing"] is True
        assert components["document_qa"] is False
        # 所有数据源统一启用SQL组件（CSV数据已导入PG，SQL路径统一）
        assert components["sql_generation_prompt"] is True

    def test_database_full_capabilities(self):
        components = get_allowed_components("pg")
        assert components["sql_generation_prompt"] is True
        assert components["sql_example_library"] is True
        assert components["realtime_refresh"] is True
        assert components["chart_drilldown"] is True
        assert components["query_cache"] is True
        assert components["document_qa"] is False
        assert components["batch_processing"] is False

    def test_excel_no_advanced_features(self):
        components = get_allowed_components("excel")
        assert components["document_qa"] is False
        assert components["batch_processing"] is False
        assert components["realtime_refresh"] is False
        assert components["chart_drilldown"] is False
        # 所有数据源统一启用SQL组件（Excel数据已导入PG，SQL路径统一）
        assert components["sql_generation_prompt"] is True

    def test_all_structured_types_have_terminology(self):
        for ds_type in ["excel", "csv", "pg", "mysql"]:
            components = get_allowed_components(ds_type)
            assert components["terminology"] is True
        # PDF不需要商业术语库（纯文档问答，不涉及业务术语映射）
        pdf_components = get_allowed_components("pdf")
        assert pdf_components["terminology"] is False

    def test_all_types_have_visualization(self):
        """Excel/CSV/Database支持可视化，PDF不支持（非结构化文档）"""
        for ds_type in ["excel", "csv", "pg", "mysql"]:
            components = get_allowed_components(ds_type)
            assert components["visualization"] is True
        # PDF不支持可视化
        pdf_components = get_allowed_components("pdf")
        assert pdf_components["visualization"] is False

    def test_all_types_have_recommendation(self):
        for ds_type in ["pdf", "excel", "csv", "pg", "mysql"]:
            components = get_allowed_components(ds_type)
            assert components["recommendation"] is True
