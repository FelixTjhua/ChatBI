"""测试可视化意图判定模块"""
import pytest
from apps.chat.thinking.visualization_intent import (
    VisualizationIntentDetector,
    VisualizationIntent,
)


class TestVisualizationIntentDetection:
    """测试可视化意图判定"""

    def test_trend_analysis_returns_line_chart(self):
        """趋势分析场景应推荐折线图"""
        features = {
            "has_time_column": True,
            "has_numeric_column": True,
            "has_categorical_column": False,
            "row_count": 12,
            "time_columns": ["month"],
            "numeric_columns": ["sales"],
        }
        result = VisualizationIntentDetector.detect(
            "各月销售额变化趋势", data_features=features
        )
        assert result.needs_visualization is True
        assert result.chart_type == "line"
        assert result.confidence >= 0.8

    def test_ratio_analysis_returns_pie_chart(self):
        """占比分析场景应推荐饼图"""
        features = {
            "has_time_column": False,
            "has_numeric_column": True,
            "has_categorical_column": True,
            "row_count": 5,
            "categorical_columns": ["region"],
            "numeric_columns": ["revenue"],
        }
        result = VisualizationIntentDetector.detect(
            "各区域营收占比", data_features=features
        )
        assert result.needs_visualization is True
        assert result.chart_type == "pie"

    def test_comparison_returns_column_chart(self):
        """对比分析场景应推荐柱状图"""
        features = {
            "has_time_column": False,
            "has_numeric_column": True,
            "has_categorical_column": True,
            "row_count": 8,
            "categorical_columns": ["product"],
            "numeric_columns": ["sales"],
        }
        result = VisualizationIntentDetector.detect(
            "各产品销售额对比", data_features=features
        )
        assert result.needs_visualization is True
        assert result.chart_type == "column"

    def test_pure_text_no_visualization(self):
        """纯文本解读场景不需要可视化"""
        result = VisualizationIntentDetector.detect(
            "合同中付款条款是什么？"
        )
        assert result.needs_visualization is False

    def test_explicit_chart_type(self):
        """用户显式指定图表类型应直接使用"""
        result = VisualizationIntentDetector.detect("用饼图展示数据")
        assert result.needs_visualization is True
        assert result.chart_type == "pie"
        assert result.confidence >= 0.9

    def test_rank_returns_bar_chart(self):
        """排名场景应推荐条形图"""
        features = {
            "has_time_column": False,
            "has_numeric_column": True,
            "has_categorical_column": True,
            "row_count": 10,
            "categorical_columns": ["product"],
            "numeric_columns": ["sales"],
        }
        result = VisualizationIntentDetector.detect(
            "销售额排名前10的产品", data_features=features
        )
        assert result.needs_visualization is True
        assert result.chart_type == "bar"

    def test_empty_question(self):
        """空问题应返回默认结果"""
        result = VisualizationIntentDetector.detect("")
        assert result.needs_visualization is False

    def test_distribution_returns_box_chart(self):
        """分布分析场景应推荐箱线图"""
        features = {
            "has_time_column": False,
            "has_numeric_column": True,
            "has_categorical_column": False,
            "row_count": 100,
            "numeric_columns": ["price"],
        }
        result = VisualizationIntentDetector.detect(
            "价格分布情况", data_features=features
        )
        assert result.needs_visualization is True
        assert result.chart_type == "box"


class TestDataFeatureExtraction:
    """测试数据特征提取"""

    def test_extract_features_with_time_and_numeric(self):
        """应正确识别时间列和数值列"""
        fields = ["日期", "销售额", "产品"]
        data = [
            {"日期": "2025-01", "销售额": 1000, "产品": "A"},
            {"日期": "2025-02", "销售额": 1200, "产品": "B"},
        ]
        features = VisualizationIntentDetector.extract_data_features(fields, data)
        assert features["has_time_column"] is True
        assert features["has_numeric_column"] is True
        assert features["has_categorical_column"] is True
        assert features["row_count"] == 2
        assert "日期" in features["time_columns"]
        assert "销售额" in features["numeric_columns"]

    def test_extract_features_empty_data(self):
        """空数据应返回默认特征"""
        features = VisualizationIntentDetector.extract_data_features([], [])
        assert features["row_count"] == 0
        assert features["has_time_column"] is False

    def test_to_dict(self):
        """VisualizationIntent.to_dict应返回完整字典"""
        intent = VisualizationIntent(
            needs_visualization=True,
            chart_type="line",
            reason="test",
            confidence=0.9,
        )
        d = intent.to_dict()
        assert d["needs_visualization"] is True
        assert d["chart_type"] == "line"
        assert d["confidence"] == 0.9
