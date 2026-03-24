"""统一RAG执行框架 (Unified RAG Execution Pipeline)"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from common.utils.utils import ChatBILogUtil

# ========== 统一三阶段执行器（新版） ==========
from apps.chat.thinking.unified_rag_executor import (  # noqa: F401
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


# ========== 意图类型常量（保留向后兼容） ==========

# IntentType 改为 DesignIntent 的别名，消除重复定义
# 新代码请直接使用 DesignIntent，IntentType 仅为向后兼容保留
IntentType = DesignIntent


class DataSourceType:
    """数据源类型"""
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    DATABASE = "database"


# ========== 溯源凭证 ==========

@dataclass
class ProvenanceRecord:
    """溯源凭证 - 记录数据来源，确保结果可追溯"""
    source_type: str = ""           # pdf/excel/csv/database
    source_name: str = ""           # 文件名/数据库名
    # PDF溯源
    page_number: Optional[int] = None
    section_title: str = ""
    table_index: Optional[int] = None
    # Excel溯源
    sheet_name: str = ""
    row_range: str = ""             # e.g. "2-13"
    col_range: str = ""             # e.g. "A-F"
    # CSV溯源
    batch_index: Optional[int] = None
    # Database溯源
    sql_statement: str = ""
    execution_time: float = 0.0     # 秒
    data_update_time: str = ""      # ISO格式时间戳
    cache_status: str = ""          # hit/miss/stale
    # 通用
    similarity_score: float = 0.0
    processing_rules: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = {"source_type": self.source_type, "source_name": self.source_name}
        if self.source_type == "pdf":
            if self.page_number is not None:
                result["page_number"] = self.page_number
            if self.section_title:
                result["section_title"] = self.section_title
            if self.table_index is not None:
                result["table_index"] = self.table_index
        elif self.source_type == "excel":
            if self.sheet_name:
                result["sheet_name"] = self.sheet_name
            if self.row_range:
                result["row_range"] = self.row_range
            if self.col_range:
                result["col_range"] = self.col_range
        elif self.source_type == "csv":
            if self.batch_index is not None:
                result["batch_index"] = self.batch_index
        elif self.source_type == "database":
            if self.sql_statement:
                result["sql_statement"] = self.sql_statement
            if self.execution_time > 0:
                result["execution_time_ms"] = round(self.execution_time * 1000, 1)
            if self.data_update_time:
                result["data_update_time"] = self.data_update_time
            if self.cache_status:
                result["cache_status"] = self.cache_status
        if self.similarity_score > 0:
            result["similarity_score"] = round(self.similarity_score, 4)
        if self.processing_rules:
            result["processing_rules"] = self.processing_rules
        return result

    def to_source_tag(self, lang: str = "zh") -> str:
        """生成溯源标注文本，支持中英文

        中文示例：【来源: XX报告-第12页-章节「3.2节」】
        英文示例：[Source: XX Report - Page 12 - Section "3.2"]
        """
        is_en = lang.lower().startswith("en")
        if is_en:
            parts = [f"Source: {self.source_name}"]
            if self.source_type == "pdf":
                if self.page_number is not None:
                    parts.append(f"Page {self.page_number}")
                if self.section_title:
                    parts.append(f'Section "{self.section_title}"')
                if self.table_index is not None:
                    parts.append(f"Table {self.table_index}")
            elif self.source_type == "excel":
                if self.sheet_name:
                    parts.append(f'Sheet "{self.sheet_name}"')
                if self.row_range:
                    parts.append(f"Rows {self.row_range}")
            elif self.source_type == "csv":
                if self.row_range:
                    parts.append(f"Rows {self.row_range}")
            elif self.source_type == "database":
                if self.data_update_time:
                    parts.append(f"Updated: {self.data_update_time}")
            return "[" + " - ".join(parts) + "]"
        else:
            parts = [f"来源: {self.source_name}"]
            if self.source_type == "pdf":
                if self.page_number is not None:
                    parts.append(f"第{self.page_number}页")
                if self.section_title:
                    parts.append(f"章节「{self.section_title}」")
                if self.table_index is not None:
                    parts.append(f"表{self.table_index}")
            elif self.source_type == "excel":
                if self.sheet_name:
                    parts.append(f"Sheet「{self.sheet_name}」")
                if self.row_range:
                    parts.append(f"第{self.row_range}行")
            elif self.source_type == "csv":
                if self.row_range:
                    parts.append(f"第{self.row_range}行")
            elif self.source_type == "database":
                if self.data_update_time:
                    parts.append(f"更新时间: {self.data_update_time}")
            return "【" + "-".join(parts) + "】"


# ========== 统一执行结果 ==========

@dataclass
class RAGPipelineResult:
    """统一RAG执行结果"""
    # 核心结果
    text_answer: str = ""
    intent_type: str = ""
    sub_intents: List[str] = field(default_factory=list)

    # 可视化资源
    visualization_config: Optional[Dict[str, Any]] = None
    visualization_enabled: bool = False

    # 推荐问题
    pre_recommendations: List[Dict[str, str]] = field(default_factory=list)
    mid_recommendations: List[Dict[str, str]] = field(default_factory=list)
    post_recommendations: List[Dict[str, str]] = field(default_factory=list)

    # 溯源凭证
    provenance: List[ProvenanceRecord] = field(default_factory=list)

    # 元数据
    ds_type: str = ""
    processing_time: float = 0.0
    rag_quality_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text_answer": self.text_answer,
            "intent_type": self.intent_type,
            "sub_intents": self.sub_intents,
            "visualization": {
                "enabled": self.visualization_enabled,
                "config": self.visualization_config,
            } if self.visualization_enabled else None,
            "recommendations": {
                "pre": self.pre_recommendations,
                "mid": self.mid_recommendations,
                "post": self.post_recommendations,
            },
            "provenance": [p.to_dict() for p in self.provenance],
            "metadata": {
                "ds_type": self.ds_type,
                "processing_time_ms": round(self.processing_time * 1000, 1),
                "rag_quality_score": round(self.rag_quality_score, 3),
            },
        }


# ========== 意图映射 ==========

def map_fine_intent_to_design_intent(fine_intent: str, ds_type: str = "database") -> str:
    """将9种细粒度意图映射到5类意图"""
    return map_to_design_intent(fine_intent, ds_type)


def decompose_complex_intent(
    question: str,
    primary_intent: str,
    ds_type: str = "database",
) -> List[str]:
    """复杂意图拆解"""
    intents = [primary_intent]

    q = question.lower()

    # 否定语境检测
    negation_prefixes_zh = ['不需要', '不用', '不要', '无需', '不必', '别', '没必要', '不做', '不进行']
    negation_prefixes_en = ["don't", "do not", "no need to", "without", "skip", "not", "no"]

    def _is_negated(keyword: str) -> bool:
        """检查关键词是否处于否定语境中"""
        kw_pos = q.find(keyword)
        if kw_pos < 0:
            return False
        # 检查关键词前方是否有否定前缀（中文：前方0~6字符内）
        prefix_window = q[max(0, kw_pos - 6):kw_pos]
        for neg in negation_prefixes_zh:
            if neg in prefix_window:
                return True
        # 英文否定检测（前方0~15字符内）
        en_prefix_window = q[max(0, kw_pos - 15):kw_pos]
        for neg in negation_prefixes_en:
            if neg in en_prefix_window:
                return True
        return False

    # 检测可视化子意图（中英文）
    viz_keywords = ['可视化', '图表', '柱状图', '折线图', '饼图', '生成图',
                    '画图', '做图', '绘制', '展示图',
                    'visualize', 'chart', 'bar chart', 'line chart', 'pie chart',
                    'plot', 'graph', 'draw', 'generate chart']
    if any(kw in q and not _is_negated(kw) for kw in viz_keywords):
        if IntentType.VISUALIZATION not in intents:
            intents.append(IntentType.VISUALIZATION)

    # 检测分析子意图（中英文）
    analysis_keywords = ['分析', '解读', '评估', '对比',
                         'analyze', 'analysis', 'evaluate', 'compare', 'interpret']
    if any(kw in q and not _is_negated(kw) for kw in analysis_keywords):
        if IntentType.DATA_ANALYSIS not in intents and primary_intent != IntentType.DATA_ANALYSIS:
            intents.append(IntentType.DATA_ANALYSIS)

    # 检测预测子意图（中英文）
    predict_keywords = ['预测', '预估', '预计', '未来', '明年', '下个月',
                        'predict', 'forecast', 'estimate', 'future', 'next year', 'next month']
    if any(kw in q and not _is_negated(kw) for kw in predict_keywords):
        if IntentType.DATA_PREDICTION not in intents and primary_intent != IntentType.DATA_PREDICTION:
            intents.append(IntentType.DATA_PREDICTION)

    return intents


def detect_cross_datasource_hint(question: str) -> Dict[str, Any]:
    """检测用户问题是否涉及跨数据源需求"""
    import re
    q = question.lower()

    # 检测跨数据源关键词模式（中英文）
    cross_patterns = [
        (r'(excel|表格).*(数据库|库表|sql|database)', ['excel', 'database']),
        (r'(数据库|库表|sql|database).*(excel|表格)', ['database', 'excel']),
        (r'(pdf|文档|报告|document|report).*(数据库|库表|sql|database)', ['pdf', 'database']),
        (r'(数据库|库表|sql|database).*(pdf|文档|报告|document|report)', ['database', 'pdf']),
        (r'(csv).*(excel|数据库|database)', ['csv', 'excel']),
        (r'(excel).*(csv)', ['excel', 'csv']),
        (r'(pdf|文档|document).*(excel|表格)', ['pdf', 'excel']),
        (r'(对比|compare).*(不同|两个|多个|different|multiple).*(数据源|文件|表|datasource|file|table)', ['multiple']),
    ]

    for pattern, sources in cross_patterns:
        if re.search(pattern, q):
            return {
                "is_cross_datasource": True,
                "hint": "当前对话绑定了单一数据源。如需对比不同数据源的数据，"
                        "请分别在对应数据源的对话中查询，再手动对比结果。"
                        "\nThis chat is bound to a single datasource. To compare data from different sources, "
                        "please query each datasource in its own chat and compare results manually.",
                "detected_sources": sources,
            }

    return {
        "is_cross_datasource": False,
        "hint": "",
        "detected_sources": [],
    }


# ========== 数据源能力矩阵 ==========

def get_ds_capabilities(ds_type: str) -> Dict[str, bool]:
    """获取数据源的能力矩阵"""
    ds = ds_type.lower() if ds_type else "database"

    if ds == "pdf":
        # PDF 只走文档问答路径
        return {
            "document_qa": True,       # PDF 核心能力
            "data_query": False,       # PDF 不走 SQL 路径
            "data_analysis": False,    # PDF 不支持数据分析
            "data_prediction": False,  # PDF 不支持数据预测
            "visualization": False,    # PDF 不生成图表
            "sql_generation": False,   # PDF 不走 SQL 路径
            "batch_processing": False,
            "realtime_refresh": False,
            "chart_drilldown": False,
        }
    elif ds == "excel":
        return {
            "document_qa": False,
            "data_query": True,
            "data_analysis": True,
            "data_prediction": True,
            "visualization": True,
            "sql_generation": True,    # 数据已导入PG，统一走SQL路径
            "batch_processing": False,
            "realtime_refresh": False,
            "chart_drilldown": False,
        }
    elif ds == "csv":
        return {
            "document_qa": False,
            "data_query": True,
            "data_analysis": True,
            "data_prediction": True,
            "visualization": True,
            "sql_generation": True,    # 数据已导入PG，统一走SQL路径
            "batch_processing": True,   # CSV核心：批量处理
            "realtime_refresh": False,
            "chart_drilldown": False,
        }
    else:
        # database (pg/mysql/oracle)
        return {
            "document_qa": False,
            "data_query": True,
            "data_analysis": True,
            "data_prediction": True,
            "visualization": True,
            "sql_generation": True,     # 原生SQL执行
            "batch_processing": False,
            "realtime_refresh": True,   # 数据库核心：实时刷新
            "chart_drilldown": True,    # 数据库核心：图表钻取
        }


def build_provenance_from_doc_chunks(
    chunks: List[Dict[str, Any]],
    source_type: str = "pdf",
) -> List[ProvenanceRecord]:
    """从文档检索结果构建溯源凭证"""
    records = []
    for chunk in chunks:
        record = ProvenanceRecord(
            source_type=source_type,
            source_name=chunk.get("source_name", chunk.get("filename", "")),
            page_number=chunk.get("page_number"),
            section_title=chunk.get("section_title", ""),
            similarity_score=chunk.get("similarity", 0),
        )
        if chunk.get("chunk_type") == "table":
            record.table_index = chunk.get("table_index")
        records.append(record)
    return records


def build_provenance_from_sql(
    sql: str,
    execution_time: float = 0.0,
    ds_name: str = "",
    cache_status: str = "miss",
) -> ProvenanceRecord:
    """从SQL执行结果构建溯源凭证"""
    from datetime import datetime
    return ProvenanceRecord(
        source_type="database",
        source_name=ds_name,
        sql_statement=sql,
        execution_time=execution_time,
        data_update_time=datetime.now().isoformat(),
        cache_status=cache_status,
    )


def build_provenance_from_excel(
    sheet_name: str = "",
    row_range: str = "",
    source_name: str = "",
) -> ProvenanceRecord:
    """从Excel数据构建溯源凭证"""
    return ProvenanceRecord(
        source_type="excel",
        source_name=source_name,
        sheet_name=sheet_name,
        row_range=row_range,
    )


def build_provenance_from_csv(
    row_range: str = "",
    batch_index: int = 0,
    source_name: str = "",
    processing_rules: List[str] = None,
) -> ProvenanceRecord:
    """从CSV数据构建溯源凭证"""
    return ProvenanceRecord(
        source_type="csv",
        source_name=source_name,
        row_range=row_range,
        batch_index=batch_index,
        processing_rules=processing_rules or [],
    )
