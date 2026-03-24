"""思考过程集成模块（Thinking Process Integration）"""
from typing import Dict, List, Optional
from common.utils.utils import ChatBILogUtil
from .rag_thinking import (
    RAGThinkingProcess,
    record_datasource_selection,
    record_rag_retrieval,
    record_schema_retrieval,
    record_sql_generation,
    record_sql_execution,
    record_chart_generation,
    record_data_analysis,
    record_data_prediction,
)


def record_query_understanding_stage(
    thinking: RAGThinkingProcess,
    original_query: str,
    rewritten_query: str,
    intent: str,
    rewrite_applied: bool,
    extracted_keywords: List[str] = None,
    dialogue_turn: int = 1,
    context_references: List[Dict] = None,
    ds_type: str = '',
    ds_name: str = '',
    intent_keywords: List[str] = None,
):
    """记录查询理解阶段（合并了查询重写+对话上下文）"""
    try:
        stage = thinking.start_stage("query_understanding")
        stage.extra_data = {
            "original_query": original_query,
            "rewritten_query": rewritten_query,
            "intent": intent,
            "intent_keywords": intent_keywords or [],
            "rewrite_applied": rewrite_applied,
            "extracted_keywords": extracted_keywords or [],
            "dialogue_turn": dialogue_turn,
            "context_references": context_references or [],
            "ds_type": ds_type,
            "ds_name": ds_name,
        }
        stage.complete()
    except Exception as e:
        # 记录日志而非静默吞掉异常
        ChatBILogUtil.error(f"[thinking_integration] record_query_understanding_stage failed: {e}")




def record_context_compression_stage(
    thinking: RAGThinkingProcess,
    compression_stats: Dict
):
    """记录上下文压缩阶段"""
    try:
        stage = thinking.start_stage("context_compression")
        stage.extra_data = {
            "original_length": compression_stats.get("original_length", 0),
            "compressed_length": compression_stats.get("compressed_length", 0),
            "compression_ratio": compression_stats.get("compression_ratio", 1.0),
            "compression_applied": compression_stats.get("compression_applied",
                                                         compression_stats.get("compression_ratio", 1.0) < 1.0),
            # 新增字段：Token预算与跳过原因
            "estimated_tokens": compression_stats.get("estimated_tokens", 0),
            "token_budget": compression_stats.get("token_budget", 0),
            "budget_allocation": compression_stats.get("budget_allocation", {}),
            "compression_skipped": compression_stats.get("compression_skipped", False),
            "reason": compression_stats.get("reason", ""),
            "dynamic_budget": compression_stats.get("dynamic_budget", False),
        }
        stage.complete()
    except Exception as e:
        ChatBILogUtil.error(f"[thinking_integration] record_context_compression_stage failed: {e}")


def record_query_decomposition_stage(
    thinking: RAGThinkingProcess,
    is_complex: bool,
    sub_tasks: List[str],
    task_type: str
):
    """记录子问题分解阶段（18步流程·步骤9）

    展示系统对复杂多维度分析请求的分步处理策略。
    """
    try:
        stage = thinking.start_stage("query_decomposition")
        stage.extra_data = {
            "is_complex": is_complex,
            "sub_tasks": sub_tasks[:5],
            "task_type": task_type,
            "sub_task_count": len(sub_tasks),
        }
        stage.complete()
    except Exception as e:
        ChatBILogUtil.error(f"[thinking_integration] record_query_decomposition_stage failed: {e}")


def record_prompt_construction_stage(
    thinking: RAGThinkingProcess,
    prompt_type: str,
    system_prompt_preview: str,
    user_prompt_preview: str,
    model_name: str = '',
    rag_components: Dict = None,
    message_count: int = 0,
    total_prompt_length: int = 0,
    component_counts: Dict = None,
    custom_prompts: List[Dict] = None,
    system_prompt_length: int = 0,
    user_prompt_length: int = 0,
):
    """记录提示词构建阶段 — 展示发送给LLM的完整提示词结构"""
    try:
        # 在 sql_analysis/sql_prediction 流程中，prompt_construction 会被调用两次：
        prev_custom_prompts = []
        prev_rag_components = {}
        prev_component_counts = {}
        prev_total_length = 0
        existing = thinking.get_stage("prompt_construction")
        if existing:
            # get_stage 返回 to_dict()，extra_data 嵌套在 existing["extra_data"] 中
            ex = existing.get("extra_data") or {}
            prev_custom_prompts = ex.get("custom_prompts") or []
            prev_rag_components = ex.get("rag_components") or {}
            prev_component_counts = ex.get("component_counts") or {}
            prev_total_length = ex.get("total_prompt_length") or 0
        
        # 合并 custom_prompts：本次的 + 前一次的，按 type 去重（本次优先）
        merged_custom_prompts = []
        seen_types = set()
        for cp in list(custom_prompts or []):
            cp_type = cp.get('type')
            if cp_type and cp_type not in seen_types:
                seen_types.add(cp_type)
                merged_custom_prompts.append(cp)
        for prev_cp in prev_custom_prompts:
            if prev_cp.get('type') not in seen_types:
                seen_types.add(prev_cp.get('type'))
                merged_custom_prompts.append(prev_cp)
        
        # 合并 rag_components：前一次的为基础，本次的覆盖（保留前一次的 schema 等）
        merged_rag_components = dict(prev_rag_components)
        for k, v in (rag_components or {}).items():
            if isinstance(v, bool) and isinstance(merged_rag_components.get(k), bool):
                merged_rag_components[k] = merged_rag_components[k] or v
            else:
                merged_rag_components[k] = v
        
        # 合并 component_counts：
        merged_component_counts = dict(prev_component_counts)
        for k, v in (component_counts or {}).items():
            if isinstance(v, list):
                # 列表字段：保留非空的那个
                if v or not merged_component_counts.get(k):
                    merged_component_counts[k] = v
            elif isinstance(v, (int, float)):
                # 数值字段：取 MAX，避免第二次调用的 0 覆盖第一次的真实值
                prev_val = merged_component_counts.get(k, 0)
                if isinstance(prev_val, (int, float)):
                    merged_component_counts[k] = max(prev_val, v)
                else:
                    merged_component_counts[k] = v
            else:
                merged_component_counts[k] = v
        
        # system/user prompt 长度：优先使用调用方传入的精确值（含 dialogue-context 等额外消息）
        # 如果未传入（=0），则从 preview 字符串长度推算（兼容旧调用方式）
        _sys_len = system_prompt_length if system_prompt_length > 0 else (len(system_prompt_preview) if system_prompt_preview else 0)
        _user_len = user_prompt_length if user_prompt_length > 0 else (len(user_prompt_preview) if user_prompt_preview else 0)
        if existing:
            ex = existing.get("extra_data") or {}
            _sys_len = max(_sys_len, ex.get("system_prompt_length") or 0)
            _user_len = max(_user_len, ex.get("user_prompt_length") or 0)
        
        # total_prompt_length 必须与 system_prompt_length + user_prompt_length 保持一致
        merged_total_length = _sys_len + _user_len
        
        # system_prompt_preview 合并策略
        _merged_sys_preview = system_prompt_preview or ""
        _merged_user_preview = user_prompt_preview or ""
        if existing:
            ex = existing.get("extra_data") or {}
            _prev_sys = ex.get("system_prompt_preview") or ""
            _prev_user = ex.get("user_prompt_preview") or ""
            # system_prompt_preview：优先保留包含 <m-schema> 的版本
            # 前端依赖 <m-schema> 标签判断 isSqlPath 并提取 schema 内容
            _prev_has_schema = '<m-schema>' in _prev_sys
            _curr_has_schema = '<m-schema>' in _merged_sys_preview
            if _prev_has_schema and not _curr_has_schema:
                _merged_sys_preview = _prev_sys
            elif not _prev_has_schema and _curr_has_schema:
                pass  # 保留当前的
            elif len(_prev_sys) > len(_merged_sys_preview):
                _merged_sys_preview = _prev_sys
            # user_prompt_preview：保留最长的
            if len(_prev_user) > len(_merged_user_preview):
                _merged_user_preview = _prev_user
        
        stage = thinking.start_stage("prompt_construction")
        stage.extra_data = {
            "prompt_type": prompt_type,
            "system_prompt_preview": _merged_sys_preview,
            "user_prompt_preview": _merged_user_preview,
            "system_prompt_length": _sys_len,
            "user_prompt_length": _user_len,
            "model_name": model_name,
            "rag_components": merged_rag_components,
            "component_counts": merged_component_counts,
            "message_count": message_count,
            "total_prompt_length": merged_total_length,
            "custom_prompts": merged_custom_prompts,
        }
        stage.complete()
    except Exception as e:
        ChatBILogUtil.error(f"[thinking_integration] record_prompt_construction_stage failed: {e}")





def record_execution_stage(
    thinking: RAGThinkingProcess,
    row_count: int,
    execution_time: float,
    sql: str = ""
):
    """记录SQL执行阶段
    
     新增 sql 参数，允许传入已执行的 SQL 语句，
    避免 record_sql_execution 中 sql="" 导致信息丢失。
    """
    try:
        record_sql_execution(
            thinking=thinking,
            sql=sql,
            execution_time=execution_time,
            row_count=row_count,
            success=True
        )
    except Exception as e:
        ChatBILogUtil.error(f"[thinking_integration] record_execution_stage failed: {e}")


def record_chart_stage(
    thinking: RAGThinkingProcess,
    chart_type: str,
    reasoning: str,
    generation_time: float = 0.0,
    token_usage: Dict = None
):
    """记录图表生成阶段"""
    try:
        record_chart_generation(
            thinking=thinking,
            chart_type=chart_type,
            reasoning=reasoning,
            rag_context={},
            generation_time=generation_time,
            token_usage=token_usage
        )
    except Exception as e:
        ChatBILogUtil.error(f"[thinking_integration] record_chart_stage failed: {e}")


def record_analysis_stage(
    thinking: RAGThinkingProcess,
    analysis: str,
    reasoning: str,
    generation_time: float = 0.0,
    token_usage: Dict = None
):
    """记录数据分析阶段"""
    try:
        record_data_analysis(
            thinking=thinking,
            analysis=analysis,
            reasoning=reasoning,
            rag_context={},
            generation_time=generation_time,
            token_usage=token_usage
        )
    except Exception as e:
        ChatBILogUtil.error(f"[thinking_integration] record_analysis_stage failed: {e}")


def record_prediction_stage(
    thinking: RAGThinkingProcess,
    prediction: str,
    reasoning: str,
    generation_time: float = 0.0,
    token_usage: Dict = None
):
    """记录数据预测阶段（ 新增：与分析阶段对称，支持预测思考过程记录）"""
    try:
        record_data_prediction(
            thinking=thinking,
            prediction=prediction,
            reasoning=reasoning,
            rag_context={},
            generation_time=generation_time,
            token_usage=token_usage
        )
    except Exception as e:
        ChatBILogUtil.error(f"[thinking_integration] record_prediction_stage failed: {e}")


def record_smart_output_stage(
    thinking: RAGThinkingProcess,
    decision: Dict,
    row_count: int = 0,
    field_count: int = 0
):
    """记录智能输出格式决策阶段

    展示系统如何根据SQL执行结果的实际数据特征，
    智能决定最优输出格式（自然语言/表格/图表类型）。
    """
    try:
        stage = thinking.start_stage("smart_output")
        stage.extra_data = {
            "format_type": decision.get('format_type', 'keep'),
            "reason": decision.get('reason', ''),
            "confidence": decision.get('confidence', 0),
            "skip_chart": decision.get('skip_chart', False),
            "override_chart_type": decision.get('override_chart_type', ''),
            "row_count": row_count,
            "field_count": field_count,
        }
        stage.complete()
    except Exception as e:
        ChatBILogUtil.error(f"[thinking_integration] record_smart_output_stage failed: {e}")






def record_visualization_intent_stage(
    thinking: RAGThinkingProcess,
    intent_result: Dict
):
    """记录可视化意图判定阶段。"""
    try:
        stage = thinking.start_stage("visualization_intent")
        stage.extra_data = {
            "needs_visualization": intent_result.get("needs_visualization", False),
            "chart_type": intent_result.get("chart_type", "table"),
            "reason": intent_result.get("reason", ""),
            "dimensions": intent_result.get("dimensions", {}),
            "confidence": intent_result.get("confidence", 0),
        }
        stage.complete()
    except Exception as e:
        ChatBILogUtil.error(f"[thinking_integration] record_visualization_intent_stage failed: {e}")


def record_recommendation_stage(
    thinking: RAGThinkingProcess,
    layer: str,
    recommendations: list
):
    """记录智能推荐问题生成阶段。"""
    try:
        stage_name = f"recommendation_{layer}"
        stage = thinking.start_stage(stage_name)
        stage.extra_data = {
            "layer": layer,
            "count": len(recommendations),
            "questions": [r.get("question", "") for r in recommendations[:5]],
            "types": [r.get("type", "") for r in recommendations[:5]],
        }
        stage.complete()
    except Exception as e:
        ChatBILogUtil.error(f"[thinking_integration] record_recommendation_stage failed: {e}")


def record_provenance_stage(
    thinking: RAGThinkingProcess,
    provenance_records: List[Dict]
):
    """记录溯源凭证生成阶段"""
    try:
        stage = thinking.start_stage("provenance")
        stage.extra_data = {
            "record_count": len(provenance_records),
            "records": provenance_records[:10],
            "source_types": list(set(
                r.get("source_type", "") for r in provenance_records
            )),
        }
        stage.complete()
    except Exception as e:
        ChatBILogUtil.error(f"[thinking_integration] record_provenance_stage failed: {e}")


def record_antv_g2_config_stage(
    thinking: RAGThinkingProcess,
    chart_type: str,
    dimensions: Dict,
    dynamic_refresh: bool = False,
    drilldown_enabled: bool = False,
    has_prediction: bool = False,
):
    """记录AntV G2可视化配置生成阶段"""
    try:
        stage = thinking.start_stage("antv_g2_config")
        stage.extra_data = {
            "chart_type": chart_type,
            "dimensions": dimensions,
            "dynamic_refresh": dynamic_refresh,
            "drilldown_enabled": drilldown_enabled,
            "has_prediction": has_prediction,
        }
        stage.complete()
    except Exception as e:
        ChatBILogUtil.error(f"[thinking_integration] record_antv_g2_config_stage failed: {e}")
