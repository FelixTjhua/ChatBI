"""思考过程模块（Thinking Process Module）"""

from .rag_thinking import (
    RAGThinkingProcess,
    RAGRetrievalResult,
    LLMGenerationResult,
    ExecutionResult,
    ThinkingStage,
    RAGQualityMetrics,
    record_rag_retrieval,
    record_datasource_selection,
    record_schema_retrieval,
    record_sql_generation,
    record_sql_execution,
    record_chart_generation,
    record_data_analysis,
    record_data_prediction
)
from .rag_evaluator import RAGEvaluator, RetrievalMetrics, GenerationMetrics, EndToEndMetrics, EvaluationReport
from .rag_evidence_filter import filter_rag_evidence
from .dialogue_state import DialogueStateTracker, DialogueIntent, DialogueTurn
from .unified_rag_executor import (
    DesignIntent,
    UnifiedRAGExecutor,
    PipelineContext,
    RetrieveResult,
    AugmentResult,
    GenerateResult,
    get_available_components,
    get_execution_path,
    map_to_design_intent,
    format_pdf_context,
    get_pdf_source_summary,
)

__all__ = [
    # 思考过程核心（记录处理流程）
    'RAGThinkingProcess',
    'RAGRetrievalResult',
    'LLMGenerationResult',
    'ExecutionResult',
    'ThinkingStage',
    'RAGQualityMetrics',
    'record_rag_retrieval',
    'record_datasource_selection',
    'record_schema_retrieval',
    'record_sql_generation',
    'record_sql_execution',
    'record_chart_generation',
    'record_data_analysis',
    'record_data_prediction',
    # RAG离线评估（系统管理面板使用，非实时处理流程）
    'RAGEvaluator',
    'RetrievalMetrics',
    'GenerationMetrics',
    'EndToEndMetrics',
    'EvaluationReport',
    # RAG证据质量过滤
    'filter_rag_evidence',
    # 多轮对话状态追踪（步骤1"问题理解"的内部子模块）
    'DialogueStateTracker',
    'DialogueIntent',
    'DialogueTurn',
    # 统一三阶段 RAG 执行器
    'DesignIntent',
    'UnifiedRAGExecutor',
    'PipelineContext',
    'RetrieveResult',
    'AugmentResult',
    'GenerateResult',
    'get_available_components',
    'get_execution_path',
    'map_to_design_intent',
    'format_pdf_context',
    'get_pdf_source_summary',
]
