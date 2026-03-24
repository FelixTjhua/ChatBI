"""分层智能推荐问题引擎 (Layered Recommendation Engine)"""
from typing import Any, Dict, List, Optional

from common.utils.utils import ChatBILogUtil


class RecommendationLayer:
    """推荐问题层级"""
    PRE = "pre"       # 前置（冷启动）
    MID = "mid"       # 中置（检索后）
    POST = "post"     # 后置（生成后）


class RecommendationEngine:
    """分层智能推荐问题引擎（中英文双语支持）"""

    @staticmethod
    def _q(zh: str, en: str, lang: str = "zh") -> str:
        """根据语言返回对应文本"""
        return en if lang.lower().startswith("en") else zh

    @staticmethod
    def generate_pre_recommendations(
        ds_type: str,
        schema_summary: str = "",
        section_titles: Optional[List[str]] = None,
        table_names: Optional[List[str]] = None,
        field_names: Optional[List[str]] = None,
        has_prediction_capability: bool = False,
        has_table: bool = True,
        lang: str = "zh",
    ) -> List[Dict[str, str]]:
        """前置推荐：冷启动场景，基于数据源元信息生成概览类问题。"""
        recommendations = []
        _q = lambda zh, en: RecommendationEngine._q(zh, en, lang)

        if ds_type == "pdf":
            # PDF = 纯文档问答，只推荐文档理解类问题
            # 不推荐任何SQL查询、数据分析、数据预测、图表类问题
            recommendations.append({
                "question": _q("本文档的核心内容和主要结论是什么？",
                               "What are the key contents and main conclusions of this document?"),
                "type": _q("文档", "Document"), "layer": RecommendationLayer.PRE,
            })
            if section_titles:
                for title in section_titles[:3]:
                    recommendations.append({
                        "question": _q(f"文档中关于「{title}」的内容是什么？",
                                       f'What does the document say about "{title}"?'),
                        "type": _q("文档", "Document"), "layer": RecommendationLayer.PRE,
                    })
            # 文档类通用推荐
            recommendations.append({
                "question": _q("总结文档中提到的关键数据和结论",
                               "Summarize the key data and conclusions mentioned in the document"),
                "type": _q("文档", "Document"), "layer": RecommendationLayer.PRE,
            })
        elif ds_type in ("excel", "csv"):
            recommendations.append({
                "question": _q("这个数据源包含哪些数据？整体情况如何？",
                               "What data does this datasource contain? What's the overview?"),
                "type": _q("查询", "Query"), "layer": RecommendationLayer.PRE,
            })
            if field_names:
                numeric_hints = [f for f in field_names if any(
                    kw in f for kw in ['额', '量', '数', '率', '价', 'amount', 'count', 'price', 'total']
                )]
                if numeric_hints:
                    recommendations.append({
                        "question": _q(f"查询{numeric_hints[0]}的汇总统计",
                                       f"Query summary statistics of {numeric_hints[0]}"),
                        "type": _q("查询", "Query"), "layer": RecommendationLayer.PRE,
                    })
            recommendations.append({
                "question": _q("总结一下这个数据源的整体数据情况",
                               "Summarize the overall data in this datasource"),
                "type": _q("分析", "Analysis"), "layer": RecommendationLayer.PRE,
            })
            if has_prediction_capability:
                recommendations.append({
                    "question": _q("预测未来的数据趋势",
                                   "Predict future data trends"),
                    "type": _q("预测", "Prediction"), "layer": RecommendationLayer.PRE,
                })
        else:
            # Database
            if table_names:
                recommendations.append({
                    "question": _q(f"查询{table_names[0]}的最新数据",
                                   f"Query the latest data from {table_names[0]}"),
                    "type": _q("查询", "Query"), "layer": RecommendationLayer.PRE,
                })
            recommendations.append({
                "question": _q("总结一下这个数据源的整体数据情况",
                               "Summarize the overall data in this datasource"),
                "type": _q("分析", "Analysis"), "layer": RecommendationLayer.PRE,
            })
            if has_prediction_capability:
                recommendations.append({
                    "question": _q("预测未来的数据趋势",
                                   "Predict future data trends"),
                    "type": _q("预测", "Prediction"), "layer": RecommendationLayer.PRE,
                })

        return recommendations[:5]

    @staticmethod
    def generate_mid_recommendations(
        question: str,
        intent: str,
        retrieval_results: Optional[Dict[str, Any]] = None,
        ds_type: str = "database",
        has_visualization: bool = False,
        has_table: bool = True,
        data_features: Optional[Dict[str, Any]] = None,
        lang: str = "zh",
    ) -> List[Dict[str, str]]:
        """中置推荐：基于检索结果+当前问题，生成下钻类推荐问题。"""
        recommendations = []
        results = retrieval_results or {}
        features = data_features or {}
        _q = lambda zh, en: RecommendationEngine._q(zh, en, lang)

        is_pdf = ds_type.lower() == "pdf" if ds_type else False

        if is_pdf:
            # PDF = 纯文档问答，所有意图都只推荐文档理解类问题
            doc_chunks = results.get("doc_chunks", [])
            if intent in ("fact_query", "statistical_analysis"):
                recommendations.append({
                    "question": _q("文档中关于这个主题还有哪些补充内容？",
                                   "What additional content does the document have on this topic?"),
                    "type": _q("文档", "Document"), "layer": RecommendationLayer.MID,
                })
            elif intent == "trend_analysis":
                recommendations.append({
                    "question": _q("文档中对未来趋势有哪些预判？",
                                   "What future trend predictions does the document contain?"),
                    "type": _q("文档", "Document"), "layer": RecommendationLayer.MID,
                })
            elif intent == "comparison_analysis":
                recommendations.append({
                    "question": _q("文档中还有哪些对比分析内容？",
                                   "What other comparative analysis does the document contain?"),
                    "type": _q("文档", "Document"), "layer": RecommendationLayer.MID,
                })
            elif intent == "prediction":
                recommendations.append({
                    "question": _q("文档中对未来发展有哪些展望？",
                                   "What future outlook does the document provide?"),
                    "type": _q("文档", "Document"), "layer": RecommendationLayer.MID,
                })
            elif intent == "term_explanation" and doc_chunks:
                recommendations.append({
                    "question": _q("总结文档中的关键数据和结论",
                                   "Summarize key data and conclusions in the document"),
                    "type": _q("文档", "Document"), "layer": RecommendationLayer.MID,
                })
                recommendations.append({
                    "question": _q("查看该结论的具体数据支撑",
                                   "View the specific data supporting this conclusion"),
                    "type": _q("文档", "Document"), "layer": RecommendationLayer.MID,
                })
            # 补充 follow_up（追问）意图的推荐
            elif intent == "follow_up":
                recommendations.append({
                    "question": _q("从另一个角度解读文档中的相关内容",
                                   "Interpret related content from a different perspective"),
                    "type": _q("文档", "Document"), "layer": RecommendationLayer.MID,
                })
            # term_explanation 无 doc_chunks 时也应有推荐
            elif intent == "term_explanation":
                recommendations.append({
                    "question": _q("文档中对这个概念有哪些具体说明？",
                                   "What specific explanations does the document provide for this concept?"),
                    "type": _q("文档", "Document"), "layer": RecommendationLayer.MID,
                })
            # ambiguous_query 也应有推荐（引导用户明确问题）
            elif intent == "ambiguous_query":
                recommendations.append({
                    "question": _q("文档的主要内容和结构是什么？",
                                   "What are the main contents and structure of the document?"),
                    "type": _q("文档", "Document"), "layer": RecommendationLayer.MID,
                })
            # PDF 通用兜底
            if intent not in ("irrelevant_query", "ambiguous_query"):
                recommendations.append({
                    "question": _q("总结文档的核心观点和关键数据",
                                   "Summarize the document's core viewpoints and key data"),
                    "type": _q("文档", "Document"), "layer": RecommendationLayer.MID,
                })
        else:
            # 结构化数据源（Excel/CSV/Database）：全能力推荐
            if intent in ("fact_query", "statistical_analysis"):
                recommendations.append({
                    "question": _q("对上述查询结果进行深度分析",
                                   "Perform in-depth analysis on the query results above"),
                    "type": _q("分析", "Analysis"), "layer": RecommendationLayer.MID,
                })
                if has_visualization:
                    recommendations.append({
                        "question": _q("切换为其他图表类型展示",
                                       "Switch to a different chart type"),
                        "type": _q("可视化", "Visualization"), "layer": RecommendationLayer.MID,
                    })
            elif intent == "trend_analysis":
                recommendations.append({
                    "question": _q("基于当前趋势预测未来数据",
                                   "Predict future data based on current trends"),
                    "type": _q("预测", "Prediction"), "layer": RecommendationLayer.MID,
                })
            elif intent == "comparison_analysis":
                recommendations.append({
                    "question": _q("进一步细分对比维度",
                                   "Further break down comparison dimensions"),
                    "type": _q("分析", "Analysis"), "layer": RecommendationLayer.MID,
                })
            elif intent == "prediction":
                recommendations.append({
                    "question": _q("查看预测的置信区间和误差范围",
                                   "View prediction confidence intervals and error margins"),
                    "type": _q("分析", "Analysis"), "layer": RecommendationLayer.MID,
                })
            # 补充 term_explanation 意图的专属推荐
            elif intent == "term_explanation":
                recommendations.append({
                    "question": _q("查询该指标的实际数据",
                                   "Query the actual data for this metric"),
                    "type": _q("查询", "Query"), "layer": RecommendationLayer.MID,
                })
                recommendations.append({
                    "question": _q("分析该指标的历史变化趋势",
                                   "Analyze the historical trend of this metric"),
                    "type": _q("分析", "Analysis"), "layer": RecommendationLayer.MID,
                })
            # 补充 follow_up 意图的推荐
            elif intent == "follow_up":
                recommendations.append({
                    "question": _q("对上述结果做进一步分析",
                                   "Perform further analysis on the results above"),
                    "type": _q("分析", "Analysis"), "layer": RecommendationLayer.MID,
                })

            # 数据源特定推荐
            if ds_type in ("excel", "csv"):
                if features.get("has_time_column"):
                    recommendations.append({
                        "question": _q("按季度拆分查看数据变化",
                                       "View data changes by quarter"),
                        "type": _q("分析", "Analysis"), "layer": RecommendationLayer.MID,
                    })
                if features.get("has_categorical_column"):
                    recommendations.append({
                        "question": _q("按分类维度查看数据分布",
                                       "View data distribution by category"),
                        "type": _q("查询", "Query"), "layer": RecommendationLayer.MID,
                    })
                if ds_type == "csv" and features.get("row_count", 0) > 100:
                    recommendations.append({
                        "question": _q("查看数据的异常值分布情况",
                                       "View outlier distribution in the data"),
                        "type": _q("分析", "Analysis"), "layer": RecommendationLayer.MID,
                    })
            elif ds_type in ("database", "pg", "mysql", "oracle", "postgresql", "postgres"):
                if has_visualization:
                    recommendations.append({
                        "question": _q("钻取查看详细数据明细",
                                       "Drill down to view detailed data"),
                        "type": _q("查询", "Query"), "layer": RecommendationLayer.MID,
                    })
                # Database也利用数据特征生成更精准的推荐
                if features.get("has_time_column"):
                    recommendations.append({
                        "question": _q("按时间维度查看数据变化趋势",
                                       "View data trends over time"),
                        "type": _q("分析", "Analysis"), "layer": RecommendationLayer.MID,
                    })
                if features.get("has_categorical_column") and not features.get("has_time_column"):
                    recommendations.append({
                        "question": _q("按分类维度对比各组数据",
                                       "Compare data across categories"),
                        "type": _q("分析", "Analysis"), "layer": RecommendationLayer.MID,
                    })

            # 结构化数据源通用兜底
            if intent not in ("irrelevant_query", "ambiguous_query"):
                recommendations.append({
                    "question": _q("按更细的维度拆分查看",
                                   "Break down by finer dimensions"),
                    "type": _q("查询", "Query"), "layer": RecommendationLayer.MID,
                })

        return recommendations[:3]

    @staticmethod
    def generate_post_recommendations(
        question: str,
        answer_summary: str = "",
        chart_type: Optional[str] = None,
        intent: str = "",
        ds_type: str = "database",
        has_table: bool = True,
        lang: str = "zh",
    ) -> List[Dict[str, str]]:
        """后置推荐：基于最终回答+可视化结果，生成关联/预测类推荐问题。

        架构设计推荐问题必须严格匹配数据源的实际能力
        - PDF：非结构化文档，只能做RAG文档问答 → 只推荐文档类问题
          PDF不生成图表、不做SQL查询、不做数据分析/预测
        - Excel/CSV/Database：结构化数据 → 推荐可视化切换+分析+预测
        """
        recommendations = []
        _q = lambda zh, en: RecommendationEngine._q(zh, en, lang)

        is_pdf = ds_type.lower() == "pdf" if ds_type else False

        if is_pdf:
            # PDF = 纯文档问答，只推荐文档理解类问题
            if intent in ("fact_query", "trend_analysis", "statistical_analysis"):
                recommendations.append({
                    "question": _q("文档中对未来发展有哪些展望？",
                                   "What future outlook does the document provide?"),
                    "type": _q("文档", "Document"), "layer": RecommendationLayer.POST,
                })
            if intent not in ("irrelevant_query", "prediction"):
                recommendations.append({
                    "question": _q("总结文档的核心结论和建议",
                                   "Summarize the document's core conclusions and recommendations"),
                    "type": _q("文档", "Document"), "layer": RecommendationLayer.POST,
                })
            recommendations.append({
                "question": _q("文档中还有哪些相关的内容？",
                               "What other related content is in the document?"),
                "type": _q("文档", "Document"), "layer": RecommendationLayer.POST,
            })
        else:
            # 结构化数据源（Excel/CSV/Database）：全能力推荐
            # 可视化切换类
            if chart_type and chart_type != "table":
                alt_charts_zh = {
                    "column": "折线图", "line": "柱状图",
                    "pie": "柱状图", "bar": "饼图",
                    "area": "柱状图", "box": "柱状图",
                    "heatmap": "柱状图", "sankey": "柱状图",
                    "dual_axis": "折线图",
                }
                alt_charts_en = {
                    "column": "line chart", "line": "bar chart",
                    "pie": "bar chart", "bar": "donut chart",
                    "area": "bar chart", "box": "bar chart",
                    "heatmap": "bar chart", "sankey": "bar chart",
                    "dual_axis": "line chart",
                }
                alt_zh = alt_charts_zh.get(chart_type)
                alt_en = alt_charts_en.get(chart_type)
                if alt_zh:
                    recommendations.append({
                        "question": _q(f"切换为{alt_zh}展示",
                                       f"Switch to {alt_en} display"),
                        "type": _q("可视化", "Visualization"), "layer": RecommendationLayer.POST,
                    })

            # 预测类
            if intent in ("fact_query", "trend_analysis", "statistical_analysis"):
                recommendations.append({
                    "question": _q("基于历史数据预测未来趋势",
                                   "Predict future trends based on historical data"),
                    "type": _q("预测", "Prediction"), "layer": RecommendationLayer.POST,
                })

            # 深度分析类
            if intent not in ("irrelevant_query",):
                recommendations.append({
                    "question": _q("分析数据背后的驱动因素",
                                   "Analyze the driving factors behind the data"),
                    "type": _q("分析", "Analysis"), "layer": RecommendationLayer.POST,
                })

            # 数据源特定
            if ds_type == "csv":
                recommendations.append({
                    "question": _q("查看数据的异常值统计和分布",
                                   "View outlier statistics and distribution"),
                    "type": _q("分析", "Analysis"), "layer": RecommendationLayer.POST,
                })
            elif ds_type in ("database", "pg", "mysql", "oracle", "postgresql", "postgres"):
                if intent in ("statistical_analysis", "trend_analysis"):
                    recommendations.append({
                        "question": _q("关联其他数据表进行交叉分析",
                                       "Cross-analyze with other data tables"),
                        "type": _q("分析", "Analysis"), "layer": RecommendationLayer.POST,
                    })

        return recommendations[:5]

    @staticmethod
    def merge_recommendations(
        pre: List[Dict] = None,
        mid: List[Dict] = None,
        post: List[Dict] = None,
    ) -> List[Dict[str, str]]:
        """合并三层推荐问题，去重并限制总数。

         增加模糊去重，避免语义相似的推荐重复出现
        "查询销售数据"和"查看销售数据"只保留一个
        """
        all_recs = []
        seen_questions = set()

        def _normalize_for_dedup(q: str) -> str:
            """将问题归一化用于去重比较"""
            import re
            # 去除常见的同义动词差异
            synonyms = [
                ('查看', '查询'), ('展示', '查询'), ('显示', '查询'), ('列出', '查询'),
                ('看一下', '查询'), ('看下', '查询'), ('查一下', '查询'),
                ('view', 'query'), ('show', 'query'), ('display', 'query'), ('list', 'query'),
            ]
            normalized = q.strip()
            for old, new in synonyms:
                normalized = normalized.replace(old, new)
            # 去除标点和空格
            normalized = re.sub(r'[？?。！!，,\s]', '', normalized)
            return normalized

        for layer_recs in [pre or [], mid or [], post or []]:
            for rec in layer_recs:
                q = rec.get("question", "")
                if not q:
                    continue
                normalized = _normalize_for_dedup(q)
                if normalized not in seen_questions:
                    all_recs.append(rec)
                    seen_questions.add(normalized)

        return all_recs[:8]
