"""统一三阶段 RAG 执行器 (Unified 3-Stage RAG Executor)"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from common.utils.utils import ChatBILogUtil


# ========== 5 大意图常量 ==========

class DesignIntent:
    """5 类意图"""
    DOCUMENT_QA = "document_qa"
    DATA_QUERY = "data_query"
    DATA_ANALYSIS = "data_analysis"
    DATA_PREDICTION = "data_prediction"
    VISUALIZATION = "visualization"

    ALL = (DOCUMENT_QA, DATA_QUERY, DATA_ANALYSIS, DATA_PREDICTION, VISUALIZATION)


# ========== 组件可用性矩阵 ==========

# ========== 组件可用性矩阵 ==========
COMPONENT_MATRIX = {
    #                        术语库(R)   SQL提示词(A)  SQL示例库(R)  分析提示词(A)   预测提示词(A)   可视化(G)       约束条件
    "pdf":      {"terminology": False, "sql_prompt": False,   "sql_examples": False,   "analysis_prompt": False,   "prediction_prompt": False,   "antv_g2": False,  "constraints": {}},
    "excel":    {"terminology": True,  "sql_prompt": True,    "sql_examples": True,    "analysis_prompt": True,    "prediction_prompt": True,    "antv_g2": True,   "constraints": {"single_table": True}},
    "csv":      {"terminology": True,  "sql_prompt": True,    "sql_examples": True,    "analysis_prompt": True,    "prediction_prompt": True,    "antv_g2": True,   "constraints": {"single_table": True}},
    "database": {"terminology": True,  "sql_prompt": True,    "sql_examples": True,    "analysis_prompt": True,    "prediction_prompt": True,    "antv_g2": True,   "constraints": {}},
}


def get_available_components(ds_type: str, has_table: bool = True) -> Dict[str, bool]:
    """根据数据源类型返回 6 大组件的可用性"""
    key = ds_type.lower() if ds_type else "database"
    if key not in COMPONENT_MATRIX:
        # pg/mysql/oracle → database
        key = "database"
    row = COMPONENT_MATRIX[key]
    result = {}
    for comp, val in row.items():
        if comp == "constraints":
            result[comp] = val  # 保持 dict 类型
        else:
            result[comp] = bool(val)
    return result


# ========== 细粒度意图 → 5 大意图映射 ==========

def map_to_design_intent(fine_intent: str, ds_type: str = "database") -> str:
    """将 QueryRewriter 的 9 种细粒度意图映射到5 类意图"""
    # PDF所有意图统一走文档问答
    if ds_type and ds_type.lower() == "pdf":
        return DesignIntent.DOCUMENT_QA
    
    _map = {
        "fact_query": DesignIntent.DATA_QUERY,
        "comparison_analysis": DesignIntent.DATA_ANALYSIS,
        "statistical_analysis": DesignIntent.DATA_ANALYSIS,
        "trend_analysis": DesignIntent.DATA_ANALYSIS,
        "prediction": DesignIntent.DATA_PREDICTION,
        "follow_up": DesignIntent.DATA_QUERY,
        "ambiguous_query": DesignIntent.DATA_QUERY,
        "irrelevant_query": DesignIntent.DATA_QUERY,
    }
    if fine_intent == "term_explanation":
        return DesignIntent.DATA_QUERY
    return _map.get(fine_intent, DesignIntent.DATA_QUERY)


# ========== 三阶段结果数据结构 ==========

@dataclass
class RetrieveResult:
    """阶段1：检索结果"""
    # 通用
    intent: str = ""                          # 5 大意图之一
    fine_intent: str = ""                     # 9 种细粒度意图
    sub_intents: List[str] = field(default_factory=list)  # 复合意图拆解
    rewritten_query: str = ""                 # 重写后的查询
    extracted_keywords: List[str] = field(default_factory=list)
    rewrite_applied: bool = False

    # 检索召回
    terminology_results: List[Dict] = field(default_factory=list)
    sql_example_results: List[Dict] = field(default_factory=list)
    doc_chunk_results: List[Dict] = field(default_factory=list)  # PDF 文本/表格片段
    custom_prompts: List[Dict] = field(default_factory=list)

    # 溯源
    source_pages: List[int] = field(default_factory=list)       # PDF 页码
    source_sections: List[str] = field(default_factory=list)    # PDF 章节

    # 前置推荐问题
    pre_recommendations: List[Dict] = field(default_factory=list)

    # 跨数据源检测提示
    cross_datasource_hint: Dict[str, Any] = field(default_factory=dict)

    # 元数据
    ds_type: str = ""
    retrieval_time_ms: float = 0.0


@dataclass
class AugmentResult:
    """阶段2：增强结果"""
    # 增强后的 Prompt 片段
    augmented_system_prompt: str = ""
    augmented_user_prompt: str = ""
    terminologies_xml: str = ""
    sql_examples_xml: str = ""
    schema_xml: str = ""

    # 可视化判定
    visualization_detected: bool = False
    visualization_chart_type: str = ""
    visualization_reason: str = ""

    # 使用的组件
    components_used: Dict[str, bool] = field(default_factory=dict)

    # 中置推荐问题
    mid_recommendations: List[Dict] = field(default_factory=list)

    # 上下文压缩信息
    compression_applied: bool = False
    original_token_count: int = 0
    compressed_token_count: int = 0


@dataclass
class GenerateResult:
    """阶段3：生成结果"""
    # 核心输出
    text_answer: str = ""
    sql: str = ""
    data: Any = None
    chart_config: Dict = field(default_factory=dict)

    # 分析/预测
    analysis_text: str = ""
    prediction_text: str = ""
    prediction_data: Any = None

    # 可视化
    antv_g2_config: Optional[Dict] = None

    # 溯源
    provenance: List[Dict] = field(default_factory=list)

    # 后置推荐问题
    post_recommendations: List[Dict] = field(default_factory=list)

    # 后置验证配置（抗幻觉）
    # 生成阶段准备验证规则，由 LLMService 在 LLM 输出后执行
    validation_rules: Dict[str, Any] = field(default_factory=dict)

    # 元数据
    generation_time_ms: float = 0.0
    token_usage: Dict = field(default_factory=dict)


@dataclass
class PipelineContext:
    """三阶段共享上下文"""
    question: str = ""
    ds_type: str = ""
    ds_name: str = ""
    has_table: bool = True
    oid: int = 1
    ds_id: Optional[int] = None
    dialogue_history: List[Dict] = field(default_factory=list)
    available_components: Dict[str, bool] = field(default_factory=dict)
    # 接收外部查询分解结果，避免 decompose_complex_query 结果被丢弃
    decompose_result: Optional[Dict] = None
    lang: str = "zh"


# ========== 统一三阶段执行器 ==========

class UnifiedRAGExecutor:
    """统一三阶段 RAG 执行器"""

    # ================================================================
    @staticmethod
    def retrieve(
        ctx: PipelineContext,
        session=None,
        terminologies: List[Dict] = None,
        rewrite_result: Dict = None,
    ) -> RetrieveResult:
        """统一检索阶段"""
        t0 = time.time()
        result = RetrieveResult(ds_type=ctx.ds_type)

        # --- 1. 意图识别 ---
        from apps.chat.thinking.query_rewriter import QueryRewriter
        if rewrite_result:
            rewrite_out = rewrite_result
        else:
            rewrite_out = QueryRewriter.rewrite(ctx.question, terminologies, ds_type=ctx.ds_type)
        result.fine_intent = rewrite_out.get("intent", "fact_query")
        result.intent = map_to_design_intent(result.fine_intent, ctx.ds_type)
        result.rewritten_query = rewrite_out.get("rewritten", ctx.question)
        result.extracted_keywords = rewrite_out.get("extracted_keywords", [])
        result.rewrite_applied = rewrite_out.get("rewrite_applied", False)

        ChatBILogUtil.info(
            f"[RAG-Retrieve] ds={ctx.ds_type} fine_intent={result.fine_intent} "
            f"design_intent={result.intent} rewrite={result.rewrite_applied}"
        )

        # --- 2. 复合意图拆解 ---
        from apps.chat.thinking.unified_rag_pipeline import decompose_complex_intent, detect_cross_datasource_hint
        result.sub_intents = decompose_complex_intent(ctx.question, result.intent, ctx.ds_type)

        # 合并外部 decompose_complex_query 的子任务到 sub_intents
        if ctx.decompose_result and ctx.decompose_result.get('is_complex'):
            sub_tasks = ctx.decompose_result.get('sub_tasks', [])
            if len(sub_tasks) >= 2:
                # 将子任务映射为对应的意图类型，合并到 sub_intents
                for task in sub_tasks:
                    task_intent = map_to_design_intent(
                        QueryRewriter._detect_intent(task, ds_type=ctx.ds_type),
                        ctx.ds_type
                    )
                    if task_intent not in result.sub_intents:
                        result.sub_intents.append(task_intent)

        # 检测跨数据源需求，提示用户当前版本限制
        result.cross_datasource_hint = detect_cross_datasource_hint(ctx.question)

        # --- 3. 按数据源+意图检索 ---
        components = ctx.available_components or get_available_components(ctx.ds_type, ctx.has_table)
        ctx.available_components = components

        # 3a. 术语库检索（Database/Excel/CSV启用，PDF不需要）
        if components.get("terminology") and session:
            try:
                from apps.terminology.crud.terminology import select_terminology_by_word_with_details
                result.terminology_results = select_terminology_by_word_with_details(
                    session, result.rewritten_query, ctx.oid, ctx.ds_id
                ) or []
            except Exception as e:
                ChatBILogUtil.error(f"[RAG-Retrieve] Terminology retrieval failed: {e}")

        # 术语检索完成后，用术语增强查询再用于后续检索
        if result.terminology_results:
            try:
                enhanced_query = QueryRewriter.post_expand_with_terminologies(
                    result.rewritten_query, result.terminology_results
                )
                if enhanced_query != result.rewritten_query:
                    ChatBILogUtil.info(
                        f"[RAG-Retrieve] Post-terminology expansion: "
                        f"'{result.rewritten_query[:50]}' -> '{enhanced_query[:50]}'"
                    )
                    result.rewritten_query = enhanced_query
                    result.rewrite_applied = True

                    # 术语扩展后重新检测意图
                    new_fine_intent = QueryRewriter._detect_intent(enhanced_query, ds_type=ctx.ds_type)
                    if new_fine_intent != result.fine_intent:
                        ChatBILogUtil.info(
                            f"[RAG-Retrieve] Intent changed after terminology expansion: "
                            f"{result.fine_intent} -> {new_fine_intent}"
                        )
                        result.fine_intent = new_fine_intent
                        result.intent = map_to_design_intent(new_fine_intent, ctx.ds_type)
            except Exception as e:
                ChatBILogUtil.error(f"[RAG-Retrieve] Post-terminology expansion failed: {e}")

        # 3b. SQL 示例库检索（所有数据源统一启用，文档问答意图和通用对话意图除外）
        _general_chat_intents = {'term_explanation', 'irrelevant_query', 'ambiguous_query', 'document_qa'}
        _skip_sql_retrieval = (
            result.intent == DesignIntent.DOCUMENT_QA
            or result.fine_intent in _general_chat_intents
        )
        if components.get("sql_examples") and session and not _skip_sql_retrieval:
            try:
                from apps.data_training.crud.data_training import select_training_by_question_with_details
                result.sql_example_results = select_training_by_question_with_details(
                    session, result.rewritten_query, ctx.oid, ctx.ds_id
                ) or []
                # Excel/CSV 单表场景过滤掉含复杂 JOIN 的 SQL 示例
                if ctx.ds_type in ("excel", "csv") and result.sql_example_results:
                    filtered = []
                    for ex in result.sql_example_results:
                        sql_upper = (ex.get("sql", "") or ex.get("description", "")).upper()
                        question_text = (ex.get("question", "") or "").upper()
                        # 排除含多表 JOIN 或子查询的复杂 SQL
                        has_join = " JOIN " in sql_upper or " JOIN " in question_text
                        has_subquery = sql_upper.count("SELECT") > 1
                        # 排除 question 中包含多表关联描述的示例
                        has_multi_table_hint = any(kw in question_text for kw in [
                            '关联', '联表', '多表', 'JOIN', '连接查询',
                            'CROSS', 'INNER JOIN', 'LEFT JOIN', 'RIGHT JOIN',
                        ])
                        if not has_join and not has_subquery and not has_multi_table_hint:
                            filtered.append(ex)
                    if len(filtered) < len(result.sql_example_results):
                        ChatBILogUtil.info(
                            f"[RAG-Retrieve] Filtered {len(result.sql_example_results) - len(filtered)} "
                            f"complex SQL examples for {ctx.ds_type} single-table scenario"
                        )
                    result.sql_example_results = filtered
            except Exception as e:
                ChatBILogUtil.error(f"[RAG-Retrieve] SQL example retrieval failed: {e}")

        # 3c. 文档知识库检索（PDF 核心路径 + Excel/CSV 语义分块）
        from apps.chat.thinking.ds_component_router import DOCUMENT_TYPES
        _doc_retrieval_types = tuple(DOCUMENT_TYPES)
        if ctx.ds_type in _doc_retrieval_types and session:
            try:
                from apps.datasource.document_retrieval import search_document_chunks
                # 主查询检索
                _doc_top_k = 5
                _doc_threshold = 0.35
                result.doc_chunk_results = search_document_chunks(
                    session, result.rewritten_query, ctx.oid, top_k=_doc_top_k,
                    similarity_threshold=_doc_threshold, ds_id=ctx.ds_id,
                ) or []

                # 扩展查询补充检索（多路召回提升覆盖率）
                expanded_queries = rewrite_out.get("expanded_queries", [])
                seen_ids = {c.get("id") for c in result.doc_chunk_results if c.get("id")}

                for eq in expanded_queries[:2]:
                    try:
                        extra = search_document_chunks(
                            session, eq, ctx.oid, top_k=3,
                            similarity_threshold=0.30, ds_id=ctx.ds_id,
                        ) or []
                        for ec in extra:
                            if ec.get("id") not in seen_ids:
                                result.doc_chunk_results.append(ec)
                                seen_ids.add(ec.get("id"))
                    except Exception:
                        pass

                # 按相似度降序排列，截取 Top-K
                result.doc_chunk_results.sort(
                    key=lambda c: c.get("similarity", 0), reverse=True
                )
                _max_doc_chunks = 8
                result.doc_chunk_results = result.doc_chunk_results[:_max_doc_chunks]

                # 提取溯源信息（页码、章节）
                for chunk in result.doc_chunk_results:
                    if chunk.get("page_number") is not None:
                        result.source_pages.append(chunk["page_number"])
                    if chunk.get("section_title"):
                        result.source_sections.append(chunk["section_title"])

                ChatBILogUtil.info(
                    f"[RAG-Retrieve][{ctx.ds_type.upper()}] Retrieved {len(result.doc_chunk_results)} chunks, "
                    f"pages={sorted(set(result.source_pages))}, "
                    f"top_sim={result.doc_chunk_results[0]['similarity'] if result.doc_chunk_results else 0}"
                )
            except Exception as e:
                ChatBILogUtil.error(f"[RAG-Retrieve] Document chunk retrieval failed: {e}")

        # --- 4. 重排序 + 上下文压缩 ---
        try:
            from apps.chat.thinking.rag_reranker import RAGReranker
            if result.terminology_results:
                result.terminology_results = RAGReranker.rerank_terminologies(
                    result.terminology_results, result.rewritten_query
                )
            if result.sql_example_results:
                result.sql_example_results = RAGReranker.rerank_sql_examples(
                    result.sql_example_results, result.rewritten_query
                )
        except Exception as e:
            ChatBILogUtil.error(f"[RAG-Retrieve] Reranking failed: {e}")

        # --- 5. 前置推荐问题 ---
        try:
            from apps.chat.thinking.recommendation_engine import RecommendationEngine
            # 从session中提取实际的表名和字段名，而非传空列表
            _pre_table_names = []
            _pre_field_names = []
            if session and ctx.ds_id:
                try:
                    from apps.datasource.models.datasource import CoreTable, CoreField
                    _pre_tables = session.query(CoreTable).filter(
                        CoreTable.ds_id == ctx.ds_id,
                        CoreTable.checked == True
                    ).limit(5).all()
                    for _pt in _pre_tables:
                        _tname = _pt.custom_comment or _pt.table_comment or _pt.table_name
                        if _tname:
                            _pre_table_names.append(_tname)
                        _pre_fields = session.query(CoreField).filter(
                            CoreField.table_id == _pt.id,
                            CoreField.checked == True
                        ).limit(10).all()
                        for _pf in _pre_fields:
                            _fname = _pf.custom_comment or _pf.field_comment or _pf.field_name
                            if _fname:
                                _pre_field_names.append(_fname)
                except Exception as e:
                    ChatBILogUtil.error(f"[RAG-Retrieve] Failed to extract table/field names for pre-recommendations: {e}")
            result.pre_recommendations = RecommendationEngine.generate_pre_recommendations(
                ds_type=ctx.ds_type,
                table_names=_pre_table_names,
                field_names=_pre_field_names,
                # 传入 PDF 文档的章节标题，让前置推荐问题能基于真实文档内容
                section_titles=list(set(result.source_sections)) if result.source_sections else None,
                has_prediction_capability=(result.intent == DesignIntent.DATA_PREDICTION),
                has_table=ctx.has_table,
                lang=ctx.lang,
            )
        except Exception as e:
            ChatBILogUtil.error(f"[RAG-Retrieve] Pre-recommendation failed: {e}")

        result.retrieval_time_ms = (time.time() - t0) * 1000
        ChatBILogUtil.info(
            f"[RAG-Retrieve] Completed in {result.retrieval_time_ms:.0f}ms: "
            f"terms={len(result.terminology_results)} sql_ex={len(result.sql_example_results)} "
            f"doc_chunks={len(result.doc_chunk_results)}"
        )
        return result


    # ================================================================
    @staticmethod
    def augment(
        ctx: PipelineContext,
        retrieve_result: RetrieveResult,
        db_schema: str = "",
        custom_prompt: str = "",
        dialogue_tracker=None,
    ) -> AugmentResult:
        """统一增强阶段（按数据源类型适配组件）"""
        t0 = time.time()
        aug = AugmentResult()
        components = ctx.available_components or get_available_components(ctx.ds_type, ctx.has_table)
        aug.components_used = components

        intent = retrieve_result.intent

        # --- 1. 构建术语 XML ---
        if retrieve_result.terminology_results:
            from apps.chat.task.llm import build_terminology_template_from_details
            aug.terminologies_xml = build_terminology_template_from_details(
                retrieve_result.terminology_results, ds_type=ctx.ds_type
            )
            ChatBILogUtil.info(
                f"[RAG-Augment] terminologies_xml built: len={len(aug.terminologies_xml or '')}, "
                f"has_tag={'<terminology>' in (aug.terminologies_xml or '')}, "
                f"input_count={len(retrieve_result.terminology_results)}"
            )
        else:
            ChatBILogUtil.info("[RAG-Augment] No terminology_results from retrieve, skipping XML build")

        # --- 2. 构建 SQL 示例 XML（所有数据源统一启用）---
        if components.get("sql_examples") and retrieve_result.sql_example_results:
            from apps.chat.task.llm import build_training_template_from_details
            aug.sql_examples_xml = build_training_template_from_details(
                retrieve_result.sql_example_results
            )
            ChatBILogUtil.info(
                f"[RAG-Augment] sql_examples_xml built: len={len(aug.sql_examples_xml or '')}, "
                f"has_tag={'<sql-example>' in (aug.sql_examples_xml or '')}, "
                f"input_count={len(retrieve_result.sql_example_results)}"
            )
        else:
            ChatBILogUtil.info(
                f"[RAG-Augment] SQL examples skipped: "
                f"component_enabled={components.get('sql_examples')}, "
                f"results_count={len(retrieve_result.sql_example_results)}"
            )

        # --- 3. Schema ---
        aug.schema_xml = db_schema

        # --- 4. 上下文压缩 ---
        try:
            from apps.chat.thinking.context_compressor import ContextCompressor
            compressed = ContextCompressor.compress_with_reranking(
                schema=aug.schema_xml,
                terminologies=aug.terminologies_xml,
                sql_examples=aug.sql_examples_xml,
                question=ctx.question,
                terminology_results=retrieve_result.terminology_results or [],
                sql_example_results=retrieve_result.sql_example_results or [],
            )
            stats = compressed.get("stats", {})
            aug.original_token_count = stats.get("original_length", 0)
            aug.compressed_token_count = stats.get("compressed_length", 0)
            aug.compression_applied = compressed.get("compression_applied", False)
            if aug.compression_applied:
                aug.schema_xml = compressed.get("schema", aug.schema_xml)
                aug.terminologies_xml = compressed.get("terminologies", aug.terminologies_xml)
                aug.sql_examples_xml = compressed.get("sql_examples", aug.sql_examples_xml)
                ChatBILogUtil.info(
                    f"[RAG-Augment] After compression: "
                    f"terminologies_xml_len={len(aug.terminologies_xml or '')}, "
                    f"sql_examples_xml_len={len(aug.sql_examples_xml or '')}"
                )
        except Exception as e:
            ChatBILogUtil.error(f"[RAG-Augment] Context compression failed: {e}")

        # --- 5. 按意图选择 Prompt ---
        doc_chunks_for_prompt = retrieve_result.doc_chunk_results
        if ctx.ds_type == "pdf" and doc_chunks_for_prompt:
            max_doc_chars = 4000
            max_doc_chunks = 8  # 与 _build_system_prompt 中的 doc_chunks[:8] 保持一致
            total_chars = 0
            capped_chunks = []
            for chunk in doc_chunks_for_prompt[:max_doc_chunks]:
                chunk_len = len(chunk.get("text", ""))
                if total_chars + chunk_len > max_doc_chars and capped_chunks:
                    break
                capped_chunks.append(chunk)
                total_chars += chunk_len
            if len(capped_chunks) < len(doc_chunks_for_prompt):
                ChatBILogUtil.info(
                    f"[RAG-Augment] PDF chunk budget: {len(doc_chunks_for_prompt)} -> {len(capped_chunks)} "
                    f"chunks ({total_chars} chars, max={max_doc_chars})"
                )
            doc_chunks_for_prompt = capped_chunks

        aug.augmented_system_prompt = _build_system_prompt(
            intent=intent,
            ds_type=ctx.ds_type,
            components=components,
            terminologies_xml=aug.terminologies_xml,
            sql_examples_xml=aug.sql_examples_xml,
            schema_xml=aug.schema_xml,
            custom_prompt=custom_prompt,
            doc_chunks=doc_chunks_for_prompt,
            lang=ctx.lang,
        )

        aug.augmented_user_prompt = _build_user_prompt(
            question=ctx.question,
            intent=intent,
            ds_type=ctx.ds_type,
            dialogue_tracker=dialogue_tracker,
            sub_intents=retrieve_result.sub_intents,
            lang=ctx.lang,
        )

        # --- 6. 可视化意图判定 ---
        try:
            from apps.chat.thinking.visualization_intent import VisualizationIntentDetector
            # 从 doc_chunks 或 schema 中推断数据特征
            inferred_features = {}
            if db_schema:
                schema_lower = db_schema.lower()
                time_keywords = ['date', 'time', '日期', '时间', 'month', '月', 'year', '年', 'created_at', 'updated_at']
                if any(kw in schema_lower for kw in time_keywords):
                    inferred_features['has_time_column'] = True
                numeric_keywords = ['int', 'float', 'decimal', 'numeric', 'double', 'bigint', 'amount', '金额', '数量']
                if any(kw in schema_lower for kw in numeric_keywords):
                    inferred_features['has_numeric_column'] = True
                varchar_keywords = ['varchar', 'text', 'char', 'name', '名称', '类型', '类别']
                if any(kw in schema_lower for kw in varchar_keywords):
                    inferred_features['has_categorical_column'] = True
            viz = VisualizationIntentDetector.detect(
                question=ctx.question,
                data_features=inferred_features if inferred_features else None,
                ds_type=ctx.ds_type,
                lang=ctx.lang,
            )
            aug.visualization_detected = viz.needs_visualization
            aug.visualization_chart_type = viz.chart_type or ""
            aug.visualization_reason = viz.reason or ""
        except Exception as e:
            ChatBILogUtil.error(f"[RAG-Augment] Visualization detection failed: {e}")

        # --- 7. 中置推荐问题 ---
        try:
            from apps.chat.thinking.recommendation_engine import RecommendationEngine
            aug.mid_recommendations = RecommendationEngine.generate_mid_recommendations(
                question=ctx.question,
                intent=retrieve_result.fine_intent,
                ds_type=ctx.ds_type,
                retrieval_results={
                    "terminologies": retrieve_result.terminology_results,
                    "sql_examples": retrieve_result.sql_example_results,
                    "doc_chunks": retrieve_result.doc_chunk_results,
                },
                has_visualization=aug.visualization_detected,
                has_table=ctx.has_table,
                lang=ctx.lang,
            )
        except Exception as e:
            ChatBILogUtil.error(f"[RAG-Augment] Mid-recommendation failed: {e}")

        augment_time = (time.time() - t0) * 1000
        ChatBILogUtil.info(
            f"[RAG-Augment] Completed in {augment_time:.0f}ms: "
            f"intent={intent} viz={aug.visualization_detected} "
            f"compression={aug.compression_applied} components={list(k for k,v in components.items() if v)}"
        )
        return aug


    # ================================================================
    @staticmethod
    def generate_config(
        ctx: PipelineContext,
        retrieve_result: RetrieveResult,
        augment_result: AugmentResult,
    ) -> GenerateResult:
        """生成阶段配置（不执行 LLM 调用，仅准备参数）"""
        gen = GenerateResult()
        intent = retrieve_result.intent

        # --- 1. 溯源凭证 ---
        gen.provenance = _build_provenance(ctx, retrieve_result)

        # --- 2. 可视化配置 ---
        if augment_result.visualization_detected:
            gen.antv_g2_config = {
                "chart_type": augment_result.visualization_chart_type,
                "reason": augment_result.visualization_reason,
            }

        # --- 3. 后置推荐问题 ---
        try:
            from apps.chat.thinking.recommendation_engine import RecommendationEngine
            gen.post_recommendations = RecommendationEngine.generate_post_recommendations(
                question=ctx.question,
                chart_type=augment_result.visualization_chart_type or "table",
                intent=retrieve_result.fine_intent,
                ds_type=ctx.ds_type,
                has_table=ctx.has_table,
                lang=ctx.lang,
            )
        except Exception as e:
            ChatBILogUtil.error(f"[RAG-Generate] Post-recommendation failed: {e}")

        # --- 4. 构建后置验证规则（抗幻觉） ---
        gen.validation_rules = _build_validation_rules(
            intent=intent,
            ds_type=ctx.ds_type,
            retrieve_result=retrieve_result,
        )

        return gen
    # ================================================================
    @staticmethod
    def execute_pdf_pipeline(
        question: str,
        session=None,
        oid: int = 1,
        ds_id: int = None,
        ds_name: str = "",
        custom_prompt: str = "",
        dialogue_tracker=None,
        terminologies: List[Dict] = None,
        lang: str = "zh",
        has_table: bool = False,
    ) -> Dict[str, Any]:
        """PDF 文档 RAG 完整处理流程（纯文档问答路径）"""
        return UnifiedRAGExecutor.execute_pipeline(
            question=question,
            ds_type="pdf",
            ds_name=ds_name,
            has_table=False,  # PDF不走SQL路径，has_table固定为False
            oid=oid,
            ds_id=ds_id,
            session=session,
            db_schema="",     # PDF 不需要 Schema
            custom_prompt=custom_prompt,
            dialogue_tracker=dialogue_tracker,
            terminologies=terminologies,
            lang=lang,
        )

    # ================================================================
    @staticmethod
    def execute_excel_pipeline(
        question: str,
        session=None,
        oid: int = 1,
        ds_id: int = None,
        ds_name: str = "",
        db_schema: str = "",
        custom_prompt: str = "",
        dialogue_tracker=None,
        terminologies: List[Dict] = None,
        lang: str = "zh",
    ) -> Dict[str, Any]:
        """Excel 数据源 RAG 完整处理流程"""
        return UnifiedRAGExecutor.execute_pipeline(
            question=question,
            ds_type="excel",
            ds_name=ds_name,
            has_table=True,   # Excel 始终有表格数据
            oid=oid,
            ds_id=ds_id,
            session=session,
            db_schema=db_schema,
            custom_prompt=custom_prompt,
            dialogue_tracker=dialogue_tracker,
            terminologies=terminologies,
            lang=lang,
        )

    # ================================================================
    @staticmethod
    def execute_csv_pipeline(
        question: str,
        session=None,
        oid: int = 1,
        ds_id: int = None,
        ds_name: str = "",
        db_schema: str = "",
        custom_prompt: str = "",
        dialogue_tracker=None,
        terminologies: List[Dict] = None,
        lang: str = "zh",
    ) -> Dict[str, Any]:
        """CSV 数据源 RAG 完整处理流程"""
        return UnifiedRAGExecutor.execute_pipeline(
            question=question,
            ds_type="csv",
            ds_name=ds_name,
            has_table=True,   # CSV 始终有表格数据
            oid=oid,
            ds_id=ds_id,
            session=session,
            db_schema=db_schema,
            custom_prompt=custom_prompt,
            dialogue_tracker=dialogue_tracker,
            terminologies=terminologies,
            lang=lang,
        )

    # ================================================================
    @staticmethod
    def execute_database_pipeline(
        question: str,
        session=None,
        oid: int = 1,
        ds_id: int = None,
        ds_name: str = "",
        db_schema: str = "",
        custom_prompt: str = "",
        dialogue_tracker=None,
        terminologies: List[Dict] = None,
        lang: str = "zh",
    ) -> Dict[str, Any]:
        """数据库 RAG 完整处理流程（全启用6大组件，唯一执行真实SQL的场景）"""
        return UnifiedRAGExecutor.execute_pipeline(
            question=question,
            ds_type="database",
            ds_name=ds_name,
            has_table=True,
            oid=oid,
            ds_id=ds_id,
            session=session,
            db_schema=db_schema,
            custom_prompt=custom_prompt,
            dialogue_tracker=dialogue_tracker,
            terminologies=terminologies,
            lang=lang,
        )

    # ================================================================
    @staticmethod
    def execute_pipeline(
        question: str,
        ds_type: str,
        ds_name: str = "",
        has_table: bool = True,
        oid: int = 1,
        ds_id: int = None,
        session=None,
        db_schema: str = "",
        custom_prompt: str = "",
        dialogue_tracker=None,
        terminologies: List[Dict] = None,
        lang: str = "zh",
    ) -> Dict[str, Any]:
        """一次性执行完整三阶段流水线"""
        t0 = time.time()

        ctx = PipelineContext(
            question=question,
            ds_type=ds_type,
            ds_name=ds_name,
            has_table=has_table,
            oid=oid,
            ds_id=ds_id,
            available_components=get_available_components(ds_type, has_table),
            lang=lang,
        )

        # 阶段1
        retrieve = UnifiedRAGExecutor.retrieve(ctx, session, terminologies)

        # 阶段2
        augment = UnifiedRAGExecutor.augment(
            ctx, retrieve, db_schema, custom_prompt, dialogue_tracker
        )

        # 阶段3
        generate = UnifiedRAGExecutor.generate_config(ctx, retrieve, augment)

        total = (time.time() - t0) * 1000
        ChatBILogUtil.info(
            f"[RAG-Pipeline] Total {total:.0f}ms | "
            f"ds={ds_type} intent={retrieve.intent}({retrieve.fine_intent}) "
            f"sub={retrieve.sub_intents} viz={augment.visualization_detected}"
        )

        return {
            "context": ctx,
            "retrieve": retrieve,
            "augment": augment,
            "generate": generate,
            "intent": retrieve.intent,
            "fine_intent": retrieve.fine_intent,
            "sub_intents": retrieve.sub_intents,
            "pipeline_time_ms": total,
        }


# ========== 内部辅助函数 ==========

def _build_system_prompt(
    intent: str,
    ds_type: str,
    components: Dict[str, bool],
    terminologies_xml: str = "",
    sql_examples_xml: str = "",
    schema_xml: str = "",
    custom_prompt: str = "",
    doc_chunks: List[Dict] = None,
    lang: str = "zh",
) -> str:
    """按意图 + 数据源构建系统提示词（全启用6大组件，按需适配）

    PDF 文档问答 → 约束型文档提示词（仅依据资料回答、不编造、标注来源）
    Excel/CSV    → 数据分析提示词 + SQL示例（数据已导入PG，执行真实SQL）
    Database     → SQL 生成提示词 + SQL 示例（真实SQL执行）
    """
    parts = []
    _is_en = lang.lower().startswith('en') if lang else False

    # ========== PDF 文档问答意图：完整约束型 Prompt ==========
    if intent == DesignIntent.DOCUMENT_QA and ds_type == "pdf":
        if _is_en:
            parts.append(
                "You are a professional document Q&A assistant (ChatBI).\n"
                "Your task is to answer user questions based on the retrieved PDF document content below.\n\n"
                "【Core Rules — Must Be Strictly Followed】\n"
                "1. Only answer based on the content provided in <document-knowledge>. Do not fabricate or speculate on information not present in the document.\n"
                "2. You must cite sources: page numbers and section titles, in the format [Source: filename-Page X-Section 'Y'].\n"
                '3. If the document does not contain relevant content, honestly answer "No relevant content found in the document" and suggest the user rephrase their question.\n'
                "4. You may summarize, generalize, compare, and explain document content, but core facts must come from the original document.\n"
                "5. Use clear Markdown formatting to organize your answer (headings, lists, bold, blockquotes, etc.).\n\n"
                "【Supported Answer Types】\n"
                "- Citation: Directly quote document text with source attribution\n"
                "- Summary: Summarize document content\n"
                "- Explanation: Explain technical terms or concepts from the document\n"
                "- Comparison: Compare different parts of the document\n"
            )
        else:
            parts.append(
                "你是一个专业的文档问答助手（ChatBI）。\n"
                "你的任务是基于以下检索到的 PDF 文档内容回答用户问题。\n\n"
                "【核心规则 — 必须严格遵守】\n"
                "1. 仅依据 <document-knowledge> 中提供的文档资料回答，不得编造或臆测文档中不存在的信息。\n"
                "2. 回答时必须标注来源：引用的页码、章节标题，格式如【来源: 文件名-第X页-章节「Y」】。\n"
                '3. 如果文档中没有与问题相关的内容，请诚实回答"文档中未找到相关内容"，并建议用户换一种方式提问。\n'
                "4. 可以对文档内容进行总结、归纳、对比、解释，但核心事实必须来自文档原文。\n"
                "5. 使用清晰的 Markdown 格式组织回答（标题、列表、加粗、引用块等）。\n\n"
                "【支持的回答类型】\n"
                "- 引用型：直接引用文档原文并标注来源\n"
                "- 摘要型：对文档内容进行概括总结\n"
                "- 解释型：解释文档中的专业术语或概念\n"
                "- 对比型：对比文档中不同部分的内容\n"
            )

        # 注入文档片段（按顺序拼接，带完整溯源标注）
        if doc_chunks:
            chunk_entries = []
            # doc_chunks 已在 augment() 阶段经过预算控制截断，
            _sorted_doc = sorted(
                doc_chunks,
                key=lambda c: (c.get("page_number") or 9999, c.get("chunk_index", 0))
            )
            for i, c in enumerate(_sorted_doc):
                source_name = c.get("source_name", c.get("filename", ""))
                page = c.get("page_number", "?")
                section = c.get("section_title", "")
                sim = c.get("similarity", 0)
                chunk_type = c.get("chunk_type", "text")
                if _is_en:
                    type_label = "Table Data" if chunk_type == "table" else "Text"
                    header = (
                        f"[Chunk {i+1}] [Source: {source_name}-Page {page}"
                        f"{'-Section \"' + section + '\"' if section else ''}"
                        f"-{type_label}-Relevance {sim:.0%}]"
                    )
                else:
                    type_label = "表格数据" if chunk_type == "table" else "文本"
                    header = (
                        f"[片段{i+1}] 【来源: {source_name}-第{page}页"
                        f"{'-章节「' + section + '」' if section else ''}"
                        f"-{type_label}-相关度{sim:.0%}】"
                    )
                chunk_entries.append(f"{header}\n{c.get('text', '')}")

            _doc_intro = (
                "Below are the most relevant content chunks retrieved from the PDF document:"
                if _is_en else
                "以下是从 PDF 文档中检索到的与用户问题最相关的内容片段："
            )
            parts.append(
                f"\n<document-knowledge>\n"
                f"{'=' * 40}\n"
                f"{_doc_intro}\n"
                f"{'=' * 40}\n\n"
                + "\n\n".join(chunk_entries)
                + f"\n</document-knowledge>"
            )
        else:
            _no_doc = (
                "(No relevant document content retrieved)"
                if _is_en else
                "（未检索到与问题相关的文档内容）"
            )
            parts.append(
                f"\n<document-knowledge>\n{_no_doc}\n</document-knowledge>"
            )

        # 术语库（仅结构化数据源使用，PDF不需要；此处保留兜底，实际PDF不会传入terminologies_xml）
        if terminologies_xml:
            parts.append(f"\n<terminologies>\n{terminologies_xml}\n</terminologies>")

        # PDF不注入自定义提示词：三种提示词类型（SQL生成、数据分析、数据预测）
        # 都是针对结构化数据操作的，PDF不走SQL路径，不做数据分析/预测

        return "\n".join(parts)

    # ========== 非 PDF 文档问答的其他意图 ==========

    # 角色定义
    if intent == DesignIntent.DOCUMENT_QA:
        parts.append(
            "You are a professional document Q&A assistant. Please answer based on the document content below, with verifiable sources."
            if _is_en else
            "你是一个专业的文档问答助手。请基于以下文档内容回答用户问题，回答必须有据可查。"
        )
    elif intent == DesignIntent.DATA_PREDICTION:
        parts.append(
            "You are a data prediction analyst. Please make trend predictions and projections based on historical data.\n\n"
            "【Output Rules】\n"
            "1. All predictions must be based on actual historical data from the query results. Do not fabricate data points.\n"
            "2. Clearly state the prediction method used (e.g., linear trend, moving average).\n"
            "3. Include confidence level or uncertainty range when possible.\n"
            "4. If historical data is insufficient for reliable prediction, state this clearly."
            if _is_en else
            "你是一个数据预测分析师。请基于历史数据进行趋势预测和推算。\n\n"
            "【输出规则】\n"
            "1. 所有预测必须基于查询结果中的实际历史数据，不得编造数据点。\n"
            "2. 明确说明使用的预测方法（如线性趋势、移动平均等）。\n"
            "3. 尽可能给出置信度或不确定性范围。\n"
            "4. 如果历史数据不足以进行可靠预测，请明确说明。"
        )
    elif intent == DesignIntent.DATA_ANALYSIS:
        parts.append(
            "You are a data analyst. Please perform statistical, comparative, proportional, or distribution analysis on the data.\n\n"
            "【Output Rules】\n"
            "1. All analytical conclusions must be supported by actual data from the query results. Do not fabricate numbers or percentages.\n"
            "2. When citing specific values, ensure they match the query results exactly.\n"
            "3. Use clear Markdown formatting (tables, lists, bold) to organize your analysis.\n"
            "4. If the data is insufficient to draw a conclusion, state this clearly rather than speculating."
            if _is_en else
            "你是一个数据分析师。请对数据进行统计分析、对比分析、占比分析或分布分析。\n\n"
            "【输出规则】\n"
            "1. 所有分析结论必须基于查询结果中的实际数据，不得编造数值或百分比。\n"
            "2. 引用具体数值时，确保与查询结果完全一致。\n"
            "3. 使用清晰的 Markdown 格式（表格、列表、加粗）组织分析内容。\n"
            "4. 如果数据不足以得出结论，请明确说明而非臆测。"
        )
    elif intent == DesignIntent.VISUALIZATION:
        parts.append(
            "You are a data visualization expert. Please generate appropriate AntV G2 chart configurations."
            if _is_en else
            "你是一个数据可视化专家。请生成适合的 AntV G2 图表配置。"
        )
    else:
        parts.append(
            "You are a data query assistant. Please generate precise data queries based on the user's question."
            if _is_en else
            "你是一个数据查询助手。请根据用户问题生成精确的数据查询。"
        )

    # 仅在有实际内容时注入 RAG 知识段，避免空标签浪费上下文

    # 注入术语库（所有数据源，仅非空时注入）
    if terminologies_xml and terminologies_xml.strip():
        _term_hint = "Please refer to the following business terminology:" if _is_en else "请参考以下商业术语规范表述："
        parts.append(f"\n<terminologies>\n{_term_hint}\n{terminologies_xml}\n</terminologies>")

    # 注入 SQL 示例（所有数据源统一启用，仅非空时注入）
    if components.get("sql_examples") and sql_examples_xml and sql_examples_xml.strip():
        parts.append(f"\n<sql-examples>\n{sql_examples_xml}\n</sql-examples>")

    # 注入 Schema（仅非空时注入）
    if schema_xml and schema_xml.strip():
        parts.append(f"\n<database-schema>\n{schema_xml}\n</database-schema>")

    # 注入文档片段（非 PDF 的 DOCUMENT_QA 兜底）
    # doc_chunks 已在 augment() 阶段截断，此处不再重复截取
    if intent == DesignIntent.DOCUMENT_QA and doc_chunks:
        # 按页码排序
        _sorted_doc2 = sorted(
            doc_chunks,
            key=lambda c: (c.get("page_number") or 9999, c.get("chunk_index", 0))
        )
        if _is_en:
            chunk_text = "\n\n".join(
                f"[Source: {c.get('source_name', '')} Page {c.get('page_number', '?')} "
                f"Section \"{c.get('section_title', '')}\" Similarity={c.get('similarity', 0):.2f}]\n{c.get('text', '')}"
                for c in _sorted_doc2
            )
        else:
            chunk_text = "\n\n".join(
                f"[来源: {c.get('source_name', '')} 第{c.get('page_number', '?')}页 "
                f"章节「{c.get('section_title', '')}」 相似度={c.get('similarity', 0):.2f}]\n{c.get('text', '')}"
                for c in _sorted_doc2
            )
        parts.append(f"\n<document-knowledge>\n{chunk_text}\n</document-knowledge>")

    # 自定义提示词
    if custom_prompt:
        parts.append(f"\n<custom-instructions>\n{custom_prompt}\n</custom-instructions>")

    return "\n".join(parts)


def _build_user_prompt(
    question: str,
    intent: str,
    ds_type: str,
    dialogue_tracker=None,
    sub_intents: List[str] = None,
    lang: str = "zh",
) -> str:
    """构建用户提示词（含对话上下文 + 子任务分解提示）"""
    parts = []
    _is_en = lang.lower().startswith('en') if lang else False

    # 注入对话上下文
    if dialogue_tracker:
        try:
            ctx = dialogue_tracker.get_dialogue_context(max_turns=3)
            if ctx.get("total_turns", 0) > 0:
                if _is_en:
                    ctx_lines = [f"Dialogue turns: {ctx['total_turns']}"]
                    if ctx.get("current_topic"):
                        ctx_lines.append(f"Current topic: {ctx['current_topic']}")
                    if ctx.get("active_entities"):
                        ctx_lines.append(f"Active entities: {', '.join(ctx['active_entities'][:5])}")
                    recent = ctx.get("recent_questions", [])
                    if len(recent) > 1:
                        ctx_lines.append(f"Recent questions: {'; '.join(recent[-3:])}")
                else:
                    ctx_lines = [f"对话轮次: {ctx['total_turns']}"]
                    if ctx.get("current_topic"):
                        ctx_lines.append(f"当前话题: {ctx['current_topic']}")
                    if ctx.get("active_entities"):
                        ctx_lines.append(f"活跃实体: {', '.join(ctx['active_entities'][:5])}")
                    recent = ctx.get("recent_questions", [])
                    if len(recent) > 1:
                        ctx_lines.append(f"近期问题: {'; '.join(recent[-3:])}")
                parts.append(f"<dialogue-context>\n{chr(10).join(ctx_lines)}\n</dialogue-context>")
        except Exception:
            pass

    # 将子任务分解结果注入 prompt，引导 LLM 分步执行
    if sub_intents and len(sub_intents) > 1:
        if _is_en:
            _intent_labels = {
                "document_qa": "Answer questions based on document content",
                "data_query": "Query relevant data",
                "data_analysis": "Perform statistical analysis on data",
                "data_prediction": "Make trend predictions based on historical data",
                "visualization": "Generate data visualization charts",
            }
            steps = "\n".join(
                f"  {i+1}. {_intent_labels.get(task, task)}"
                for i, task in enumerate(sub_intents)
            )
            parts.append(
                f"<task-decomposition>\n"
                f"This question has been decomposed into the following sub-tasks. Please complete them in order:\n{steps}\n"
                f"</task-decomposition>"
            )
        else:
            _intent_labels = {
                "document_qa": "基于文档内容回答问题",
                "data_query": "查询相关数据",
                "data_analysis": "对数据进行统计分析",
                "data_prediction": "基于历史数据进行趋势预测",
                "visualization": "生成数据可视化图表",
            }
            steps = "\n".join(
                f"  {i+1}. {_intent_labels.get(task, task)}"
                for i, task in enumerate(sub_intents)
            )
            parts.append(
                f"<task-decomposition>\n"
                f"该问题已分解为以下子任务，请按顺序逐步完成：\n{steps}\n"
                f"</task-decomposition>"
            )

    # PDF 文档问答：强化约束提示
    if intent == DesignIntent.DOCUMENT_QA and ds_type == "pdf":
        # 根据检索质量动态调整约束强度
        # 低相关度时明确告知 LLM 信息可能不足，避免"脑补"
        if _is_en:
            parts.append(
                "Please strictly answer the following question based on the <document-knowledge> content above.\n"
                "Requirements: accurate, readable, traceable — cite sources (page numbers and sections).\n"
                "If the document does not contain relevant information, clearly state 'No relevant content found in the document' and do not fabricate answers.\n"
                "If the retrieved content has low relevance to the question, note at the beginning: 'The following is based on limited document matches; further verification is recommended.'"
            )
        else:
            parts.append(
                "请严格基于上方 <document-knowledge> 中的文档内容回答以下问题。\n"
                "回答要求：准确、可读、可溯源，标注引用来源（页码和章节）。\n"
                "如果文档中没有相关信息，请明确说明「文档中未找到相关内容」，不要编造答案。\n"
                "如果检索到的内容与问题相关度不高，请在回答开头注明「以下内容基于有限的文档匹配，建议进一步核实」。"
            )
        parts.append(f"\n{question}")
        return "\n".join(parts)

    # 其他意图提示
    if _is_en:
        intent_hints = {
            DesignIntent.DOCUMENT_QA: "Please answer based on document content, citing source pages and sections.",
            DesignIntent.DATA_QUERY: "Please generate a precise data query.",
            DesignIntent.DATA_ANALYSIS: "Please perform in-depth data analysis (statistical, comparative, proportional, distribution).",
            DesignIntent.DATA_PREDICTION: "Please make trend predictions and projections based on historical data.",
            DesignIntent.VISUALIZATION: "Please generate appropriate AntV G2 chart configurations.",
        }
    else:
        intent_hints = {
            DesignIntent.DOCUMENT_QA: "请基于文档内容回答，标注来源页码和章节。",
            DesignIntent.DATA_QUERY: "请生成精确的数据查询。",
            DesignIntent.DATA_ANALYSIS: "请进行深度数据分析（统计、对比、占比、分布）。",
            DesignIntent.DATA_PREDICTION: "请基于历史数据进行趋势预测和推算。",
            DesignIntent.VISUALIZATION: "请生成适合的 AntV G2 图表配置。",
        }
    hint = intent_hints.get(intent, "")
    if hint:
        parts.append(hint)

    parts.append(question)
    return "\n".join(parts)


def _build_provenance(ctx: PipelineContext, retrieve: RetrieveResult) -> List[Dict]:
    """构建溯源凭证

    PDF 溯源：页码、章节、表格编号、检索相似度、片段类型
    Excel 溯源：Sheet名、行号、列号、数据处理规则
    CSV 溯源：批次号、行号、数据处理规则
    Database 溯源：SQL语句、执行时间、缓存状态
    """
    provenance = []

    if ctx.ds_type == "pdf":
        for chunk in retrieve.doc_chunk_results[:8]:
            entry = {
                "source_type": "pdf",
                "source_name": chunk.get("source_name", chunk.get("filename", ctx.ds_name)),
                "page_number": chunk.get("page_number"),
                "section_title": chunk.get("section_title", ""),
                "chunk_type": chunk.get("chunk_type", "text"),
                "similarity": chunk.get("similarity", 0),
            }
            # 表格片段附加表格索引
            if chunk.get("chunk_type") == "table" and chunk.get("table_index") is not None:
                entry["table_index"] = chunk["table_index"]
            provenance.append(entry)

        # 汇总溯源摘要
        if provenance:
            # avg_similarity 应包含全部 chunk，之前 provenance[:-1] 遗漏了最后一条
            chunk_count = len(provenance)
            pages = sorted(set(p.get("page_number") for p in provenance if p.get("page_number")))
            sections = list(dict.fromkeys(
                p.get("section_title") for p in provenance if p.get("section_title")
            ))
            provenance.append({
                "source_type": "pdf_summary",
                "total_chunks": chunk_count,
                "pages_referenced": pages,
                "sections_referenced": sections[:5],
                "avg_similarity": round(
                    sum(p.get("similarity", 0) for p in provenance[:chunk_count]) / max(chunk_count, 1), 4
                ),
            })
    elif ctx.ds_type == "excel":
        _is_en = ctx.lang.lower().startswith('en') if ctx.lang else False
        _excel_prov = {
            "source_type": "excel",
            "source_name": ctx.ds_name,
            "description": "Query based on Excel data table" if _is_en else "基于 Excel 数据表查询",
            "terminology_count": len(retrieve.terminology_results),
            "sql_example_count": len(retrieve.sql_example_results),
        }
        if hasattr(ctx, 'table_names') and ctx.table_names:
            _excel_prov['table_names'] = ctx.table_names
        provenance.append(_excel_prov)
    elif ctx.ds_type == "csv":
        _is_en = ctx.lang.lower().startswith('en') if ctx.lang else False
        _csv_prov = {
            "source_type": "csv",
            "source_name": ctx.ds_name,
            "description": "Query based on CSV batch processing" if _is_en else "基于 CSV 数据批量处理",
            "terminology_count": len(retrieve.terminology_results),
            "sql_example_count": len(retrieve.sql_example_results),
        }
        if hasattr(ctx, 'table_names') and ctx.table_names:
            _csv_prov['table_names'] = ctx.table_names
        provenance.append(_csv_prov)
    else:
        _is_en = ctx.lang.lower().startswith('en') if ctx.lang else False
        _db_prov = {
            "source_type": "database",
            "source_name": ctx.ds_name,
            "description": "Query based on database SQL" if _is_en else "基于数据库 SQL 查询",
            "terminology_count": len(retrieve.terminology_results),
            "sql_example_count": len(retrieve.sql_example_results),
        }
        if hasattr(ctx, 'table_names') and ctx.table_names:
            _db_prov['table_names'] = ctx.table_names
        provenance.append(_db_prov)

    return provenance


# ========== 后置验证规则构建 + 验证执行 ==========

def _build_validation_rules(
    intent: str,
    ds_type: str,
    retrieve_result: 'RetrieveResult',
) -> Dict[str, Any]:
    """根据意图和数据源类型构建后置验证规则

    抗幻觉策略：
    - SQL 场景：检查 SQL 语法关键字、表名是否在 Schema 中
    - PDF 文档问答：检查回答是否引用了检索到的片段内容
    - 分析/预测：检查结论中的数值是否在合理范围内
    """
    rules: Dict[str, Any] = {
        "enabled": True,
        "checks": [],
    }

    if intent in (DesignIntent.DATA_QUERY, DesignIntent.DATA_ANALYSIS,
                  DesignIntent.DATA_PREDICTION, DesignIntent.VISUALIZATION):
        rules["checks"].append({
            "type": "sql_syntax",
            "description": "Check if generated SQL contains basic syntax structure / 检查生成的 SQL 是否包含基本语法结构",
        })

    if intent == DesignIntent.DOCUMENT_QA and ds_type == "pdf":
        # 收集检索到的关键词，用于验证回答是否基于检索内容
        source_keywords = set()
        for chunk in retrieve_result.doc_chunk_results[:5]:
            text = chunk.get("text", "")
            # 提取片段中的关键名词（中文：2-4字词；英文：3字母以上单词）
            cn_words = re.findall(r'[\u4e00-\u9fff]{2,4}', text[:300])
            en_words = re.findall(r'[a-zA-Z]{3,}', text[:300])
            source_keywords.update(cn_words[:10])
            source_keywords.update(w.lower() for w in en_words[:10])
            # 过滤通用词，减少误匹配
            generic = {'the', 'and', 'for', 'that', 'this', 'with', 'from', 'are', 'was',
                       '的', '了', '在', '是', '有', '和', '与', '及', '等', '为', '中',
                       '对', '将', '从', '到', '以', '可', '被', '所', '其', '也',
                       # 过滤高频业务通用词，避免 source_grounding 误判
                       # 这些词在几乎所有商业文档中都会出现，匹配它们不能证明回答基于检索内容
                       '数据', '分析', '报告', '系统', '管理', '信息', '服务', '方案',
                       '企业', '公司', '业务', '项目', '工作', '技术', '平台', '产品',
                       '市场', '行业', '发展', '建设', '实现', '提供', '支持', '需求',
                       '通过', '进行', '使用', '包括', '相关', '主要', '重要', '基于',
                       'data', 'analysis', 'report', 'system', 'management', 'information',
                       'service', 'business', 'project', 'company', 'market', 'product',
                       'development', 'technology', 'platform', 'solution', 'process',
                       'based', 'include', 'provide', 'support', 'require', 'through'}
            source_keywords -= generic
        rules["checks"].append({
            "type": "source_grounding",
            "description": "Check if answer is grounded in retrieved document content / 检查回答是否基于检索到的文档内容",
            "source_keywords": list(source_keywords)[:30],
            "min_overlap": 3,  # 至少引用3个源关键词
        })
        # 低相关度时标记需要谨慎
        if retrieve_result.doc_chunk_results:
            avg_sim = sum(
                c.get("similarity", 0) for c in retrieve_result.doc_chunk_results
            ) / len(retrieve_result.doc_chunk_results)
            if avg_sim < 0.5:
                rules["checks"].append({
                    "type": "low_confidence_warning",
                    "description": "Low retrieval relevance, answer may be inaccurate / 检索相关度较低，回答可能不够准确",
                    "avg_similarity": round(avg_sim, 4),
                })

    return rules


def validate_generation_result(
    answer: str,
    sql: str = "",
    validation_rules: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """执行后置验证，返回验证结果"""
    result = {"passed": True, "warnings": [], "confidence": "high"}

    if not validation_rules or not validation_rules.get("enabled"):
        return result

    for check in validation_rules.get("checks", []):
        check_type = check.get("type", "")

        if check_type == "sql_syntax" and sql:
            # 基本 SQL 语法检查
            sql_upper = sql.upper().strip()
            # 验证规则应只允许 SELECT/WITH 开头的查询
            if not any(sql_upper.startswith(kw) for kw in ["SELECT", "WITH"]):
                result["warnings"].append("Generated SQL does not start with SELECT or WITH / 生成的 SQL 不以 SELECT 或 WITH 开头")
                result["confidence"] = "low"
            # 检查是否有未闭合的括号
            if sql.count("(") != sql.count(")"):
                result["warnings"].append("SQL has unclosed parentheses / SQL 括号未闭合")
                result["confidence"] = "low"
                result["passed"] = False

        elif check_type == "source_grounding" and answer:
            # 检查回答是否引用了检索到的源内容关键词
            source_keywords = check.get("source_keywords", [])
            min_overlap = check.get("min_overlap", 3)
            if source_keywords:
                overlap = sum(1 for kw in source_keywords if kw in answer)
                if overlap < min_overlap:
                    result["warnings"].append(
                        f"Low overlap between answer and retrieved content ({overlap}/{min_overlap}), possible hallucination / "
                        f"回答与检索内容重叠度较低（{overlap}/{min_overlap}），可能存在幻觉"
                    )
                    result["confidence"] = "medium" if overlap > 0 else "low"

        elif check_type == "low_confidence_warning":
            avg_sim = check.get("avg_similarity", 0)
            result["warnings"].append(
                f"Average retrieval relevance only {avg_sim:.0%}, please verify accuracy / "
                f"检索平均相关度仅 {avg_sim:.0%}，建议用户核实回答准确性"
            )
            if result["confidence"] == "high":
                result["confidence"] = "medium"

    return result


# ========== 意图路由决策 ==========

def get_execution_path(intent: str, ds_type: str) -> Dict[str, bool]:
    """根据 5 大意图 + 数据源类型，返回应执行的处理路径"""
    ds = ds_type.lower() if ds_type else "database"

    # PDF所有意图统一走直接回答路径
    if ds == "pdf":
        return {
            "sql_generation": False,
            "direct_answer": True,
            "analysis": False,
            "prediction": False,
            "visualization": False,
        }

    if intent == DesignIntent.DOCUMENT_QA:
        return {
            "sql_generation": False,
            "direct_answer": True,
            "analysis": False,
            "prediction": False,
            "visualization": False,
        }

    if intent == DesignIntent.DATA_QUERY:
        return {
            "sql_generation": True,  # Excel/CSV 也走 SQL（数据已导入 PG）
            "direct_answer": False,
            "analysis": False,
            "prediction": False,
            "visualization": False,  # 可视化由增强阶段叠加
        }

    if intent == DesignIntent.DATA_ANALYSIS:
        return {
            "sql_generation": True,   # 先查数据再分析
            "direct_answer": False,
            "analysis": True,
            "prediction": False,
            "visualization": True,    # 分析通常伴随可视化
        }

    if intent == DesignIntent.DATA_PREDICTION:
        return {
            "sql_generation": True,   # 先查历史数据
            "direct_answer": False,
            "analysis": False,
            "prediction": True,
            "visualization": True,    # 预测通常伴随趋势图
        }

    if intent == DesignIntent.VISUALIZATION:
        return {
            "sql_generation": True,   # 先查数据再可视化
            "direct_answer": False,
            "analysis": False,
            "prediction": False,
            "visualization": True,
        }

    # 兜底
    return {
        "sql_generation": True,
        "direct_answer": False,
        "analysis": False,
        "prediction": False,
        "visualization": False,
    }


# ========== PDF 文档上下文格式化 ==========

def format_pdf_context(doc_chunks: List[Dict], max_chars: int = 4000, lang: str = "zh") -> str:
    """将检索到的 PDF 文档片段格式化为 LLM 上下文"""
    if not doc_chunks:
        return ""

    # 按页码+片段位置排序，确保 LLM 上下文中文档片段按原文顺序排列
    sorted_chunks = sorted(
        doc_chunks,
        key=lambda c: (c.get("page_number") or 9999, c.get("chunk_index", 0))
    )

    _is_en = lang.lower().startswith('en') if lang else False
    entries = []
    total_len = 0

    for i, chunk in enumerate(sorted_chunks):
        source = chunk.get("source_name", chunk.get("filename", ""))
        page = chunk.get("page_number", "?")
        section = chunk.get("section_title", "")
        sim = chunk.get("similarity", 0)
        chunk_type = chunk.get("chunk_type", "text")
        text = chunk.get("text", "")

        # 溯源标注
        if _is_en:
            tag_parts = [f"Source: {source}"]
            if page != "?":
                tag_parts.append(f"Page {page}")
            if section:
                tag_parts.append(f"Section \"{section}\"")
            if chunk_type == "table":
                tag_parts.append("Table Data")
            tag_parts.append(f"Relevance {sim:.0%}")
            source_tag = "[" + " - ".join(tag_parts) + "]"
            entry = f"[Chunk {i+1}] {source_tag}\n{text}"
        else:
            tag_parts = [f"来源: {source}"]
            if page != "?":
                tag_parts.append(f"第{page}页")
            if section:
                tag_parts.append(f"章节「{section}」")
            if chunk_type == "table":
                tag_parts.append("表格数据")
            tag_parts.append(f"相关度{sim:.0%}")
            source_tag = "【" + "-".join(tag_parts) + "】"
            entry = f"[片段{i+1}] {source_tag}\n{text}"

        if total_len + len(entry) > max_chars:
            break

        entries.append(entry)
        total_len += len(entry)

    return "\n\n".join(entries)


def get_pdf_source_summary(doc_chunks: List[Dict]) -> Dict[str, Any]:
    """从 PDF 检索结果生成来源摘要（供前端展示）"""
    if not doc_chunks:
        return {
            "total_chunks": 0, "pages": [], "sections": [],
            "avg_similarity": 0, "has_tables": False, "source_files": [],
        }

    pages = sorted(set(
        c.get("page_number") for c in doc_chunks if c.get("page_number") is not None
    ))
    sections = list(dict.fromkeys(
        c.get("section_title") for c in doc_chunks if c.get("section_title")
    ))
    sims = [c.get("similarity", 0) for c in doc_chunks]
    has_tables = any(c.get("chunk_type") == "table" for c in doc_chunks)
    source_files = list(dict.fromkeys(
        c.get("source_name", c.get("filename", "")) for c in doc_chunks
        if c.get("source_name") or c.get("filename")
    ))

    return {
        "total_chunks": len(doc_chunks),
        "pages": pages,
        "sections": sections[:5],
        "avg_similarity": round(sum(sims) / max(len(sims), 1), 4),
        "has_tables": has_tables,
        "source_files": source_files,
    }
