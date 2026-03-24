"""测试分层智能推荐问题引擎"""
import pytest
from apps.chat.thinking.recommendation_engine import (
    RecommendationEngine,
    RecommendationLayer,
)


class TestPreRecommendations:
    """测试前置推荐（冷启动）"""

    def test_pdf_generates_document_questions(self):
        """PDF数据源应生成文档问答类推荐"""
        recs = RecommendationEngine.generate_pre_recommendations(
            ds_type="pdf",
            section_titles=["第一章 概述", "第二章 市场分析"],
        )
        assert len(recs) >= 2
        assert all(r["layer"] == RecommendationLayer.PRE for r in recs)
        assert any(r["type"] == "文档" for r in recs)
        # 应包含基于章节标题的推荐
        assert any("概述" in r["question"] or "市场分析" in r["question"] for r in recs)

    def test_excel_generates_data_overview(self):
        """Excel数据源应生成数据概览类推荐"""
        recs = RecommendationEngine.generate_pre_recommendations(
            ds_type="excel",
            field_names=["销售额", "产品名称", "日期"],
        )
        assert len(recs) >= 1
        assert any(r["type"] == "查询" for r in recs)

    def test_database_with_prediction(self):
        """支持预测的数据库应包含预测类推荐"""
        recs = RecommendationEngine.generate_pre_recommendations(
            ds_type="pg",
            table_names=["orders", "products"],
            has_prediction_capability=True,
        )
        assert any(r["type"] == "预测" for r in recs)

    def test_database_without_prediction(self):
        """不支持预测的数据库不应包含预测类推荐"""
        recs = RecommendationEngine.generate_pre_recommendations(
            ds_type="pg",
            table_names=["orders"],
            has_prediction_capability=False,
        )
        assert not any(r["type"] == "预测" for r in recs)

    def test_max_5_recommendations(self):
        """前置推荐最多5个"""
        recs = RecommendationEngine.generate_pre_recommendations(
            ds_type="pdf",
            section_titles=["A", "B", "C", "D", "E", "F", "G"],
        )
        assert len(recs) <= 5


class TestMidRecommendations:
    """测试中置推荐（检索后）"""

    def test_fact_query_generates_analysis_drill(self):
        """数据查询意图应推荐分析类下钻"""
        recs = RecommendationEngine.generate_mid_recommendations(
            question="查询各产品销售额",
            intent="fact_query",
            has_visualization=True,
        )
        assert any(r["type"] == "分析" for r in recs)
        assert any(r["type"] == "可视化" for r in recs)

    def test_trend_generates_prediction(self):
        """趋势分析意图应推荐预测"""
        recs = RecommendationEngine.generate_mid_recommendations(
            question="销售额趋势",
            intent="trend_analysis",
        )
        assert any(r["type"] == "预测" for r in recs)

    def test_pdf_generates_document_drill(self):
        """PDF文档场景应推荐文档类下钻"""
        recs = RecommendationEngine.generate_mid_recommendations(
            question="文档中的核心结论",
            intent="term_explanation",
            ds_type="pdf",
            retrieval_results={"doc_chunks": [{"text": "some content"}]},
        )
        assert any(r["type"] == "文档" for r in recs)

    def test_max_3_recommendations(self):
        """中置推荐最多3个"""
        recs = RecommendationEngine.generate_mid_recommendations(
            question="test", intent="fact_query", has_visualization=True,
        )
        assert len(recs) <= 3


class TestPostRecommendations:
    """测试后置推荐（生成后）"""

    def test_chart_generates_switch_recommendation(self):
        """有图表时应推荐可视化切换"""
        recs = RecommendationEngine.generate_post_recommendations(
            question="各产品销售额",
            chart_type="column",
            intent="fact_query",
        )
        assert any(r["type"] == "可视化" for r in recs)
        assert any("折线图" in r["question"] for r in recs)

    def test_table_no_switch_recommendation(self):
        """表格类型不应推荐可视化切换"""
        recs = RecommendationEngine.generate_post_recommendations(
            question="查询用户信息",
            chart_type="table",
            intent="fact_query",
        )
        assert not any(r["type"] == "可视化" for r in recs)

    def test_prediction_recommendation(self):
        """数据查询后应推荐预测"""
        recs = RecommendationEngine.generate_post_recommendations(
            question="各月销售额",
            chart_type="line",
            intent="trend_analysis",
        )
        assert any(r["type"] == "预测" for r in recs)

    def test_pdf_generates_related_content(self):
        """PDF场景应推荐相关文档内容"""
        recs = RecommendationEngine.generate_post_recommendations(
            question="文档核心结论",
            ds_type="pdf",
            intent="term_explanation",
        )
        assert any(r["type"] == "文档" for r in recs)


class TestMergeRecommendations:
    """测试推荐问题合并"""

    def test_merge_deduplicates(self):
        """合并时应去重"""
        pre = [{"question": "Q1", "type": "查询", "layer": "pre"}]
        mid = [{"question": "Q1", "type": "查询", "layer": "mid"}]
        post = [{"question": "Q2", "type": "分析", "layer": "post"}]
        merged = RecommendationEngine.merge_recommendations(pre, mid, post)
        questions = [r["question"] for r in merged]
        assert questions.count("Q1") == 1
        assert "Q2" in questions

    def test_merge_max_8(self):
        """合并后最多8个"""
        pre = [{"question": f"P{i}", "type": "查询", "layer": "pre"} for i in range(5)]
        mid = [{"question": f"M{i}", "type": "分析", "layer": "mid"} for i in range(3)]
        post = [{"question": f"O{i}", "type": "预测", "layer": "post"} for i in range(5)]
        merged = RecommendationEngine.merge_recommendations(pre, mid, post)
        assert len(merged) <= 8

    def test_merge_empty_layers(self):
        """空层级不影响合并"""
        post = [{"question": "Q1", "type": "分析", "layer": "post"}]
        merged = RecommendationEngine.merge_recommendations(None, None, post)
        assert len(merged) == 1
