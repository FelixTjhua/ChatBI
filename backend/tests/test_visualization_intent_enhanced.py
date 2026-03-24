"""增强可视化意图判定测试"""
import pytest
from apps.chat.thinking.visualization_intent import (
    VisualizationIntentDetector, VisualizationIntent,
)


class TestConversionChartDetection:
    """转化分析 → 桑基图/漏斗图"""

    def test_conversion_database_sankey(self):
        features = {"has_numeric_column": True, "row_count": 10}
        result = VisualizationIntentDetector.detect(
            "分析用户转化路径", features, ds_type="database"
        )
        assert result.needs_visualization is True
        assert result.chart_type == "sankey"

    def test_conversion_excel_funnel(self):
        features = {"has_numeric_column": True, "row_count": 10}
        result = VisualizationIntentDetector.detect(
            "查看转化率漏斗", features, ds_type="excel"
        )
        assert result.needs_visualization is True
        assert result.chart_type == "funnel"


class TestGeoChartDetection:
    """地域分析 → 热力图"""

    def test_geo_database_heatmap(self):
        features = {"has_numeric_column": True, "row_count": 10}
        result = VisualizationIntentDetector.detect(
            "各地区销售热力分布", features, ds_type="database"
        )
        assert result.needs_visualization is True
        assert result.chart_type == "heatmap"

    def test_geo_excel_no_heatmap(self):
        features = {"has_numeric_column": True, "row_count": 10}
        result = VisualizationIntentDetector.detect(
            "各地区销售热力分布", features, ds_type="excel"
        )
        # Excel不支持热力图，应走其他路径
        assert result.chart_type != "heatmap"


class TestDualAxisDetection:
    """双指标分析 → 双轴图"""

    def test_dual_axis_with_two_numeric(self):
        features = {
            "has_numeric_column": True,
            "numeric_columns": ["sales", "profit_rate"],
            "row_count": 10,
        }
        result = VisualizationIntentDetector.detect(
            "双轴展示销售额和利润率", features
        )
        assert result.needs_visualization is True
        assert result.chart_type == "dual_axis"

    def test_dual_axis_insufficient_columns(self):
        features = {
            "has_numeric_column": True,
            "numeric_columns": ["sales"],
            "row_count": 10,
        }
        result = VisualizationIntentDetector.detect(
            "双指标展示", features
        )
        # 只有一个数值列，不应推荐双轴图
        assert result.chart_type != "dual_axis"


class TestPredictionVisualization:
    """预测分析 → 带预测区间的折线图"""

    def test_prediction_line_chart(self):
        features = {
            "has_time_column": True,
            "has_numeric_column": True,
            "time_columns": ["month"],
            "numeric_columns": ["sales"],
            "row_count": 24,
        }
        result = VisualizationIntentDetector.detect(
            "预测未来销售趋势", features
        )
        assert result.needs_visualization is True
        assert result.chart_type == "line"
        assert result.style_hints.get("prediction") is True


class TestExplicitChartTypes:
    """显式图表类型指定（新增类型）"""

    def test_explicit_sankey(self):
        result = VisualizationIntentDetector._detect_explicit_chart_type("生成桑基图")
        assert result == "sankey"

    def test_explicit_heatmap(self):
        result = VisualizationIntentDetector._detect_explicit_chart_type("用热力图展示")
        assert result == "heatmap"

    def test_explicit_dual_axis(self):
        result = VisualizationIntentDetector._detect_explicit_chart_type("双轴图展示")
        assert result == "dual_axis"

    def test_explicit_donut(self):
        result = VisualizationIntentDetector._detect_explicit_chart_type("环图展示占比")
        assert result == "pie"
