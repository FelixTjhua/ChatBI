"""可视化意图判定模块 (Visualization Intent Detector)"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from common.utils.utils import ChatBILogUtil


@dataclass
class VisualizationIntent:
    """可视化意图结果"""
    needs_visualization: bool = False
    chart_type: str = "table"  # table/column/bar/line/pie/area/box/funnel
    reason: str = ""
    dimensions: Dict[str, str] = field(default_factory=dict)
    # dimensions: {x: 字段名, y: 字段名, color/series: 字段名}
    style_hints: Dict[str, Any] = field(default_factory=dict)
    # style_hints: {theme, show_label, show_legend, ...}
    confidence: float = 0.0  # 0~1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "needs_visualization": self.needs_visualization,
            "chart_type": self.chart_type,
            "reason": self.reason,
            "dimensions": self.dimensions,
            "style_hints": self.style_hints,
            "confidence": self.confidence,
        }


# 意图关键词 → 图表类型映射（中英双语）
_TREND_KEYWORDS = ['趋势', '变化', '走势', '增长', '下降', '波动', '历年', '逐月', '逐年', '时间序列',
                   'trend', 'change', 'growth', 'decline', 'fluctuation', 'over time', 'monthly', 'yearly']
_COMPARE_KEYWORDS = ['对比', '比较', '相比', 'vs', '差异', '哪个更', '各个', '各', '分别',
                     'compare', 'comparison', 'versus', 'differ', 'each', 'respectively']
_RATIO_KEYWORDS = ['占比', '比例', '百分比', '构成', '组成', '分布', '份额',
                   'proportion', 'percentage', 'ratio', 'share', 'composition', 'breakdown']
_DISTRIBUTION_KEYWORDS = ['分布', '散布', '离散', '集中', '异常值', '箱线',
                          'distribution', 'spread', 'outlier', 'box plot', 'scatter']
_RANK_KEYWORDS = ['排名', '排序', 'TOP', 'top', '前', '最高', '最低',
                  'rank', 'ranking', 'highest', 'lowest', 'best', 'worst']
_PURE_TEXT_KEYWORDS = ['条款', '定义', '解释', '什么是', '含义', '概念', '规定', '说明',
                       '总结', '概括', '概述', '归纳', '汇总', '梳理',
                       'definition', 'explain', 'what is', 'meaning', 'concept', 'describe',
                       'summarize', 'summary', 'overview', 'outline']
# 高阶图表关键词（数据库数据源专属）
_CONVERSION_KEYWORDS = ['转化', '漏斗', '转化率', '路径', '流程', '步骤', '环节',
                        'conversion', 'funnel', 'pipeline', 'workflow', 'step']
_GEO_KEYWORDS = ['地域', '地区', '省份', '城市', '区域', '热力', '地图', '经纬度',
                 'region', 'city', 'province', 'geographic', 'location', 'heatmap', 'map']
_DUAL_AXIS_KEYWORDS = ['双轴', '双指标', '两个指标', '同时展示',
                       'dual axis', 'dual-axis', 'two metrics', 'combined chart']
# 预测可视化关键词
_PREDICTION_VIZ_KEYWORDS = ['预测', '预估', '预计', '未来', '趋势预测',
                            'predict', 'forecast', 'estimate', 'future', 'projection']


class VisualizationIntentDetector:
    """可视化意图判定器"""

    @staticmethod
    def detect(
        question: str,
        data_features: Optional[Dict[str, Any]] = None,
        ds_type: str = "database",
        lang: str = "",
    ) -> VisualizationIntent:
        """判定用户问题是否需要可视化，并推荐图表类型。"""
        is_en = lang.lower().startswith('en') if lang else False
        _r = lambda zh, en: en if is_en else zh

        if not question:
            return VisualizationIntent(reason=_r("空问题", "Empty question"))

        q = question.lower()
        features = data_features or {}

        # 1. 纯文本场景：不需要可视化
        if any(kw in q for kw in _PURE_TEXT_KEYWORDS):
            return VisualizationIntent(reason=_r("纯文本解读场景", "Pure text interpretation scenario"), confidence=0.9)

        # 2. 用户显式指定图表类型
        explicit_type = VisualizationIntentDetector._detect_explicit_chart_type(q)
        if explicit_type:
            return VisualizationIntent(
                needs_visualization=True,
                chart_type=explicit_type,
                reason=_r(f"用户显式指定{explicit_type}", f"User explicitly specified {explicit_type}"),
                confidence=0.95,
            )

        # 3. 基于意图关键词 + 数据特征推断
        has_time = features.get("has_time_column", False)
        has_numeric = features.get("has_numeric_column", False)
        has_categorical = features.get("has_categorical_column", False)
        row_count = features.get("row_count", 0)

        # 预测可视化 → 带预测区间的折线图
        if any(kw in q for kw in _PREDICTION_VIZ_KEYWORDS) and has_time and has_numeric:
            dims = {}
            if features.get("time_columns"):
                dims["x"] = features["time_columns"][0]
            if features.get("numeric_columns"):
                dims["y"] = features["numeric_columns"][0]
            return VisualizationIntent(
                needs_visualization=True,
                chart_type="line",
                reason=_r("预测分析场景，推荐带预测区间的折线图",
                          "Prediction scenario, recommending line chart with prediction interval"),
                dimensions=dims,
                style_hints={"prediction": True, "lineDash": [4, 4]},
                confidence=0.85,
            )

        # 趋势分析 → 折线图/面积图
        if any(kw in q for kw in _TREND_KEYWORDS) and has_time and has_numeric:
            dims = {}
            if features.get("time_columns"):
                dims["x"] = features["time_columns"][0]
            if features.get("numeric_columns"):
                dims["y"] = features["numeric_columns"][0]
            return VisualizationIntent(
                needs_visualization=True,
                chart_type="line",
                reason=_r("趋势分析场景，含时间+数值维度",
                          "Trend analysis scenario with time + numeric dimensions"),
                dimensions=dims,
                confidence=0.85,
            )

        # 占比分析 → 饼图
        if any(kw in q for kw in _RATIO_KEYWORDS) and has_categorical and has_numeric:
            dims = {}
            if features.get("categorical_columns"):
                dims["series"] = features["categorical_columns"][0]
            if features.get("numeric_columns"):
                dims["y"] = features["numeric_columns"][0]
            return VisualizationIntent(
                needs_visualization=True,
                chart_type="pie",
                reason=_r("占比分析场景，含分类+数值维度",
                          "Proportion analysis scenario with categorical + numeric dimensions"),
                dimensions=dims,
                confidence=0.85,
            )

        # 转化/漏斗分析 → 漏斗图（数据库数据源优先桑基图）
        if any(kw in q for kw in _CONVERSION_KEYWORDS) and has_numeric:
            chart = "sankey" if ds_type in ("database", "pg", "mysql", "oracle") else "funnel"
            return VisualizationIntent(
                needs_visualization=True,
                chart_type=chart,
                reason=_r(f"转化分析场景，推荐{chart}",
                          f"Conversion analysis scenario, recommending {chart}"),
                confidence=0.8,
            )

        # 地域分析 → 热力图（仅数据库数据源）
        if any(kw in q for kw in _GEO_KEYWORDS) and has_numeric:
            if ds_type in ("database", "pg", "mysql", "oracle"):
                return VisualizationIntent(
                    needs_visualization=True,
                    chart_type="heatmap",
                    reason=_r("地域分析场景，推荐热力图",
                              "Geographic analysis scenario, recommending heatmap"),
                    confidence=0.75,
                )

        # 对比分析 → 柱状图
        if any(kw in q for kw in _COMPARE_KEYWORDS) and has_numeric:
            dims = {}
            if has_categorical and features.get("categorical_columns"):
                dims["x"] = features["categorical_columns"][0]
            if features.get("numeric_columns"):
                dims["y"] = features["numeric_columns"][0]
            chart = "column"
            if has_categorical and features.get("categorical_columns") and len(features["categorical_columns"]) >= 2:
                dims["series"] = features["categorical_columns"][1]
            return VisualizationIntent(
                needs_visualization=True,
                chart_type=chart,
                reason=_r("对比分析场景", "Comparison analysis scenario"),
                dimensions=dims,
                confidence=0.8,
            )

        # 分布分析 → 箱线图
        if any(kw in q for kw in _DISTRIBUTION_KEYWORDS) and has_numeric and row_count > 10:
            return VisualizationIntent(
                needs_visualization=True,
                chart_type="box",
                reason=_r("分布分析场景，数据量充足",
                          "Distribution analysis scenario with sufficient data"),
                confidence=0.75,
            )

        # 排名 → 条形图
        if any(kw in q for kw in _RANK_KEYWORDS) and has_numeric:
            return VisualizationIntent(
                needs_visualization=True,
                chart_type="bar",
                reason=_r("排名场景", "Ranking scenario"),
                confidence=0.75,
            )

        # 双指标分析 → 双轴图
        if any(kw in q for kw in _DUAL_AXIS_KEYWORDS):
            numeric_cols = features.get("numeric_columns", [])
            if len(numeric_cols) >= 2:
                return VisualizationIntent(
                    needs_visualization=True,
                    chart_type="dual_axis",
                    reason=_r("双指标分析场景，推荐双轴图",
                              "Dual-metric analysis scenario, recommending dual-axis chart"),
                    dimensions={"y": numeric_cols[0], "y2": numeric_cols[1]},
                    confidence=0.8,
                )

        # 兜底：有数值+分类且行数>1 → 推荐柱状图
        if has_numeric and has_categorical and row_count > 1:
            return VisualizationIntent(
                needs_visualization=True,
                chart_type="column",
                reason=_r("数据含分类+数值维度，默认推荐柱状图",
                          "Data has categorical + numeric dimensions, defaulting to column chart"),
                confidence=0.75,
            )

        # 兜底：有时间+数值且行数>1 → 推荐折线图
        if has_numeric and has_time and row_count > 1:
            dims = {}
            if features.get("time_columns"):
                dims["x"] = features["time_columns"][0]
            if features.get("numeric_columns"):
                dims["y"] = features["numeric_columns"][0]
            return VisualizationIntent(
                needs_visualization=True,
                chart_type="line",
                reason=_r("数据含时间+数值维度，默认推荐折线图",
                          "Data has time + numeric dimensions, defaulting to line chart"),
                dimensions=dims,
                confidence=0.75,
            )

        # 单行或纯数值 → 表格
        return VisualizationIntent(
            needs_visualization=False,
            reason=_r("数据特征不适合可视化，使用表格展示",
                      "Data features not suitable for visualization, using table display"),
            confidence=0.6,
        )

    @staticmethod
    def _detect_explicit_chart_type(question: str) -> Optional[str]:
        """检测用户是否显式指定了图表类型
        
         英文裸词 "line", "bar", "column", "table" 过于宽泛，
        "bottom line revenue" 会误匹配 line chart，"bar revenue" 误匹配 bar chart。
        改为短语匹配（"line chart", "bar chart" 等），中文关键词不受影响。
        """
        mapping = {
            # 中文关键词（精确，无歧义）
            "柱状图": "column",
            "条形图": "bar",
            "折线图": "line",
            "饼图": "pie",
            "面积图": "area",
            "箱线图": "box",
            "桑基图": "sankey",
            "热力图": "heatmap",
            "双轴图": "dual_axis",
            "环图": "pie",
            "环形图": "pie",
            "漏斗图": "funnel",
            "直方图": "column",
            "表格": "table",
            # 英文关键词（使用短语避免误匹配常见英文单词）
            "column chart": "column",
            "bar chart": "bar",
            "line chart": "line",
            "pie chart": "pie",
            "area chart": "area",
            "box chart": "box", "box plot": "box", "boxplot": "box",
            "sankey chart": "sankey", "sankey diagram": "sankey",
            "heatmap": "heatmap", "heat map": "heatmap",
            "dual-axis": "dual_axis", "dual axis": "dual_axis",
            "donut chart": "pie", "donut": "pie",
            "funnel chart": "funnel", "funnel": "funnel",
            "histogram": "column",
            "as a table": "table", "in table": "table", "table format": "table",
        }
        for keyword, chart_type in mapping.items():
            if keyword in question:
                return chart_type
        return None

    @staticmethod
    def extract_data_features(fields: list, data: list) -> Dict[str, Any]:
        """从SQL执行结果中提取数据特征，供可视化意图判定使用。"""
        features: Dict[str, Any] = {
            "has_time_column": False,
            "has_numeric_column": False,
            "has_categorical_column": False,
            "row_count": len(data) if data else 0,
            "column_count": len(fields) if fields else 0,
            "time_columns": [],
            "numeric_columns": [],
            "categorical_columns": [],
        }

        if not data or not fields:
            return features

        # 取多行样本检测列类型，避免首行为空值时将数值列误判为分类列
        sample_rows = [r for r in data[:5] if isinstance(r, dict)]
        if not sample_rows:
            return features
        time_patterns = re.compile(r'date|time|日期|时间|年|月|week|quarter|季度', re.IGNORECASE)

        for f in fields:
            fname = f if isinstance(f, str) else str(f)

            # 时间列检测
            if time_patterns.search(fname):
                features["time_columns"].append(fname)
                features["has_time_column"] = True
                continue

            # 数值列检测：遍历多行样本，只要有一行能转为数值即视为数值列
            is_numeric = False
            for row in sample_rows:
                val = row.get(fname)
                if val is not None and str(val).strip() != '':
                    try:
                        float(val)
                        is_numeric = True
                        break
                    except (ValueError, TypeError):
                        pass
            if is_numeric:
                features["numeric_columns"].append(fname)
                features["has_numeric_column"] = True
                continue

            # 分类列
            features["categorical_columns"].append(fname)
            features["has_categorical_column"] = True

        return features
