"""AntV G2 可视化配置生成器测试"""
import pytest
from apps.chat.thinking.antv_g2_config import (
    G2ChartConfig, AntVG2ConfigGenerator,
    ENTERPRISE_COLORS, PREDICTION_STYLE,
)


class TestG2ChartConfig:
    """测试G2图表配置生成"""

    def test_basic_column_chart(self):
        config = G2ChartConfig(
            chart_type="column",
            x_field="month",
            y_field="sales",
        )
        spec = config.to_g2_spec()
        assert spec["type"] == "interval"
        assert spec["encode"]["x"] == "month"
        assert spec["encode"]["y"] == "sales"
        assert spec["autoFit"] is True

    def test_line_chart_with_series(self):
        config = G2ChartConfig(
            chart_type="line",
            x_field="date",
            y_field="revenue",
            series_field="region",
        )
        spec = config.to_g2_spec()
        assert spec["type"] == "line"
        assert spec["encode"]["color"] == "region"
        assert "legend" in spec

    def test_pie_chart(self):
        config = G2ChartConfig(
            chart_type="pie",
            x_field="category",
            y_field="amount",
        )
        spec = config.to_g2_spec()
        assert spec["type"] == "interval"
        assert spec["style"]["innerRadius"] == 0.5  # 环图

    def test_prediction_style(self):
        config = G2ChartConfig(
            chart_type="line",
            x_field="month",
            y_field="sales",
            has_prediction=True,
            prediction_start_index=12,
        )
        spec = config.to_g2_spec()
        assert "_prediction" in spec
        assert spec["_prediction"]["startIndex"] == 12
        assert spec["_prediction"]["style"]["lineDash"] == [4, 4]

    def test_dynamic_refresh_database(self):
        config = G2ChartConfig(
            chart_type="column",
            x_field="date",
            y_field="orders",
            dynamic_refresh=True,
            refresh_interval_ms=300000,
            refresh_api="/api/query",
        )
        spec = config.to_g2_spec()
        assert "_dynamic" in spec
        assert spec["_dynamic"]["enabled"] is True
        assert spec["_dynamic"]["interval"] == 300000

    def test_drilldown_config(self):
        config = G2ChartConfig(
            chart_type="column",
            x_field="region",
            y_field="sales",
            enable_drilldown=True,
            drilldown_field="region",
        )
        spec = config.to_g2_spec()
        assert "_drilldown" in spec
        assert spec["_drilldown"]["field"] == "region"

    def test_provenance_tag(self):
        config = G2ChartConfig(
            chart_type="line",
            data_source_tag="【来源: 销售数据-Excel-Sheet1】",
        )
        spec = config.to_g2_spec()
        assert "_provenance" in spec
        assert "销售数据" in spec["_provenance"]["source"]

    def test_bar_chart_axis_swap(self):
        config = G2ChartConfig(
            chart_type="bar",
            x_field="category",
            y_field="count",
        )
        spec = config.to_g2_spec()
        # bar chart swaps x and y
        assert spec["encode"]["x"] == "count"
        assert spec["encode"]["y"] == "category"


class TestAntVG2ConfigGenerator:
    """测试配置生成器"""

    def test_generate_basic(self):
        config = AntVG2ConfigGenerator.generate(
            chart_type="column",
            data=[{"month": "Jan", "sales": 100}],
            dimensions={"x": "month", "y": "sales"},
        )
        assert config.chart_type == "column"
        assert config.x_field == "month"
        assert config.y_field == "sales"

    def test_database_enables_dynamic_and_drilldown(self):
        config = AntVG2ConfigGenerator.generate(
            chart_type="line",
            data=[],
            dimensions={"x": "date", "y": "revenue"},
            ds_type="database",
        )
        assert config.dynamic_refresh is True
        assert config.enable_drilldown is True
        assert config.drilldown_field == "date"

    def test_excel_no_dynamic_refresh(self):
        config = AntVG2ConfigGenerator.generate(
            chart_type="column",
            data=[],
            dimensions={"x": "month", "y": "sales"},
            ds_type="excel",
        )
        assert config.dynamic_refresh is False
        assert config.enable_drilldown is False

    def test_prediction_config(self):
        config = AntVG2ConfigGenerator.generate(
            chart_type="line",
            data=[],
            dimensions={"x": "month", "y": "sales"},
            has_prediction=True,
            prediction_start_index=12,
        )
        assert config.has_prediction is True
        assert config.prediction_start_index == 12

    def test_generate_from_visualization_intent(self):
        from apps.chat.thinking.visualization_intent import VisualizationIntent
        viz = VisualizationIntent(
            needs_visualization=True,
            chart_type="line",
            dimensions={"x": "date", "y": "sales"},
        )
        config = AntVG2ConfigGenerator.generate_from_visualization_intent(
            viz, data=[], ds_type="database"
        )
        assert config is not None
        assert config.chart_type == "line"
        assert config.dynamic_refresh is True

    def test_no_config_when_no_visualization(self):
        from apps.chat.thinking.visualization_intent import VisualizationIntent
        viz = VisualizationIntent(needs_visualization=False)
        config = AntVG2ConfigGenerator.generate_from_visualization_intent(
            viz, data=[]
        )
        assert config is None
