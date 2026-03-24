"""AntV G2 可视化配置生成器 (AntV G2 Visualization Config Generator)"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from common.utils.utils import ChatBILogUtil


# 商业视觉规范色板
ENTERPRISE_COLORS = [
    "#1890FF",  # 商业蓝（主色调）
    "#2FC25B",  # 成功绿
    "#FACC14",  # 警告黄
    "#F04864",  # 危险红
    "#8543E0",  # 紫色
    "#13C2C2",  # 青色
    "#FA8C16",  # 橙色
    "#A0D911",  # 黄绿
    "#722ED1",  # 深紫
    "#EB2F96",  # 品红
]

PREDICTION_STYLE = {
    "lineDash": [4, 4],           # 虚线
    "fillOpacity": 0.15,          # 浅灰色填充
    "strokeOpacity": 0.6,
    "fill": "#BFBFBF",
}


@dataclass
class G2ChartConfig:
    """AntV G2 图表配置（Vue 3适配）"""
    chart_type: str = "column"
    data: List[Dict[str, Any]] = field(default_factory=list)
    x_field: str = ""
    y_field: str = ""
    series_field: str = ""          # color/series维度
    # 样式
    colors: List[str] = field(default_factory=lambda: ENTERPRISE_COLORS[:6])
    show_label: bool = True
    show_legend: bool = True
    legend_position: str = "top"
    responsive: bool = True
    # 交互
    enable_tooltip: bool = True
    tooltip_fields: List[str] = field(default_factory=list)
    enable_drilldown: bool = False
    drilldown_field: str = ""
    # 动态刷新（仅数据库）
    dynamic_refresh: bool = False
    refresh_interval_ms: int = 300000   # 5分钟
    refresh_api: str = ""
    # 预测区间
    has_prediction: bool = False
    prediction_start_index: int = -1
    # 溯源
    data_source_tag: str = ""

    def to_g2_spec(self) -> Dict[str, Any]:
        """生成AntV G2 Spec格式的JSON配置"""
        spec: Dict[str, Any] = {
            "type": self._map_chart_type(),
            "data": self.data,
            "encode": self._build_encode(),
            "style": self._build_style(),
            "axis": self._build_axis(),
        }

        if self.show_legend and self.series_field:
            spec["legend"] = {"color": {"position": self.legend_position}}

        if self.enable_tooltip:
            spec["tooltip"] = self._build_tooltip()

        if self.show_label:
            spec["label"] = self._build_label()

        if self.responsive:
            spec["autoFit"] = True

        # 预测区间样式
        if self.has_prediction and self.prediction_start_index >= 0:
            spec["_prediction"] = {
                "startIndex": self.prediction_start_index,
                "style": PREDICTION_STYLE,
                # 虚线+浅灰色填充+置信区间
                "confidenceInterval": {
                    "enabled": True,
                    "upper": "upper_bound",   # 上界字段名
                    "lower": "lower_bound",   # 下界字段名
                    "fillColor": "rgba(24,144,255,0.1)",
                    "strokeColor": "rgba(24,144,255,0.3)",
                    "strokeDash": [2, 2],
                },
            }

        # 动态刷新配置
        if self.dynamic_refresh:
            spec["_dynamic"] = {
                "enabled": True,
                "interval": self.refresh_interval_ms,
                "api": self.refresh_api,
            }

        # 钻取配置
        if self.enable_drilldown and self.drilldown_field:
            spec["_drilldown"] = {
                "enabled": True,
                "field": self.drilldown_field,
            }

        # 溯源标注
        if self.data_source_tag:
            spec["_provenance"] = {"source": self.data_source_tag}

        return spec

    def _map_chart_type(self) -> str:
        """映射内部图表类型到AntV G2 type"""
        mapping = {
            "column": "interval",
            "bar": "interval",
            "line": "line",
            "area": "area",
            "pie": "interval",
            "box": "boxplot",
            "funnel": "interval",
            "dual_axis": "line",
            "sankey": "sankey",
            "heatmap": "cell",
        }
        return mapping.get(self.chart_type, "interval")

    def _build_encode(self) -> Dict[str, str]:
        """构建编码映射"""
        encode: Dict[str, str] = {}
        if self.x_field:
            encode["x"] = self.x_field
        if self.y_field:
            encode["y"] = self.y_field
        if self.series_field:
            encode["color"] = self.series_field

        # 饼图特殊处理
        if self.chart_type == "pie":
            if self.y_field:
                encode["y"] = self.y_field
            if self.series_field or self.x_field:
                encode["color"] = self.series_field or self.x_field

        # 条形图坐标轴翻转
        if self.chart_type == "bar":
            # 安全交换 x/y，避免空字段覆盖有效字段
            # 当 y 未设置时，x 会被覆盖为空字符串，导致条形图无法渲染
            _orig_x = encode.get("x", "")
            _orig_y = encode.get("y", "")
            if _orig_x and _orig_y:
                encode["x"] = _orig_y
                encode["y"] = _orig_x

        return encode

    def _build_style(self) -> Dict[str, Any]:
        """构建样式配置"""
        style: Dict[str, Any] = {}
        if self.colors:
            style["fill"] = self.colors[0]
        if self.chart_type == "pie":
            style["radius"] = 0.8
            style["innerRadius"] = 0.5  # 环图
        return style

    def _build_axis(self) -> Dict[str, Any]:
        """构建坐标轴配置"""
        axis: Dict[str, Any] = {}
        if self.x_field:
            axis["x"] = {"title": self.x_field}
        if self.y_field:
            axis["y"] = {"title": self.y_field}
        return axis

    def _build_tooltip(self) -> Dict[str, Any]:
        """构建提示框配置"""
        tooltip: Dict[str, Any] = {"shared": True}
        if self.tooltip_fields:
            tooltip["items"] = [{"field": f} for f in self.tooltip_fields]
        return tooltip

    def _build_label(self) -> Dict[str, Any]:
        """构建标签配置"""
        if self.chart_type == "pie":
            return {"text": "percentage", "position": "outside"}
        return {"text": self.y_field} if self.y_field else {}


class AntVG2ConfigGenerator:
    """AntV G2配置生成器

    根据可视化意图+数据特征，生成完整的AntV G2 JSON配置。
    """

    @staticmethod
    def generate(
        chart_type: str,
        data: List[Dict[str, Any]],
        dimensions: Dict[str, str],
        ds_type: str = "database",
        intent: str = "",
        has_prediction: bool = False,
        prediction_start_index: int = -1,
        source_tag: str = "",
    ) -> G2ChartConfig:
        """生成AntV G2图表配置"""
        config = G2ChartConfig(
            chart_type=chart_type,
            data=data,
            x_field=dimensions.get("x", ""),
            y_field=dimensions.get("y", ""),
            series_field=dimensions.get("color", dimensions.get("series", "")),
            has_prediction=has_prediction,
            prediction_start_index=prediction_start_index,
            data_source_tag=source_tag,
        )

        # 数据库数据源：启用动态刷新和钻取
        if ds_type in ("database", "pg", "mysql", "oracle"):
            config.dynamic_refresh = True
            config.enable_drilldown = True
            if dimensions.get("x"):
                config.drilldown_field = dimensions["x"]

        # 提示框字段
        config.tooltip_fields = [
            v for v in dimensions.values() if v
        ]

        # 图表类型特定配置
        if chart_type == "pie":
            config.show_label = True
            config.show_legend = True
        elif chart_type == "box":
            config.show_label = False
        elif chart_type in ("sankey", "heatmap"):
            config.show_label = False
            config.show_legend = True

        ChatBILogUtil.info(
            f"[AntV G2] Generated config: type={chart_type}, "
            f"x={config.x_field}, y={config.y_field}, "
            f"series={config.series_field}, "
            f"dynamic={config.dynamic_refresh}, "
            f"prediction={config.has_prediction}"
        )

        return config

    @staticmethod
    def generate_from_visualization_intent(
        viz_intent,
        data: List[Dict[str, Any]],
        ds_type: str = "database",
        source_tag: str = "",
        has_prediction: bool = False,
        prediction_start_index: int = -1,
    ) -> Optional[G2ChartConfig]:
        """从VisualizationIntent对象生成AntV G2配置"""
        if not viz_intent or not viz_intent.needs_visualization:
            return None

        return AntVG2ConfigGenerator.generate(
            chart_type=viz_intent.chart_type,
            data=data,
            dimensions=viz_intent.dimensions,
            ds_type=ds_type,
            has_prediction=has_prediction,
            prediction_start_index=prediction_start_index,
            source_tag=source_tag,
        )
