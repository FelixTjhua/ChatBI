import { request } from '@/utils/request'

/**
 * RAG评估API
 * 对应后端 backend/apps/system/api/rag_evaluation.py
 * 
 */

export interface RetrievalMetrics {
  precision_at_k: Record<string, number>
  recall_at_k: Record<string, number>
  mrr: number
  ndcg: number
  avg_similarity: number
  high_quality_ratio: number
  total_retrieved: number
  relevant_count: number
}

export interface GenerationMetrics {
  sql_execution_success: boolean
  sql_syntax_valid: boolean
  response_length: number
  generation_time: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  token_efficiency: number
  hallucination_score: number
  rag_context_used: boolean
  rag_utilization: number
  contextual_relevance: number
  specificity: number
  completeness: number
  missing_rate: number
  align_score: number
}

export interface EndToEndMetrics {
  task_completed: boolean
  steps_completed: number
  total_steps: number
  total_latency: number
  stage_latencies: Record<string, number>
  retry_count: number
  error_count: number
}

export interface EvaluationReport {
  question: string
  chat_id: number
  record_id: number
  overall_score: number
  grade: string
  retrieval_metrics: RetrievalMetrics | null
  generation_metrics: GenerationMetrics | null
  end_to_end_metrics: EndToEndMetrics | null
  recommendations: string[]
  timestamp: string
}

export interface EvaluationResponse {
  success: boolean
  report?: EvaluationReport
  error?: string
}

export interface BatchEvaluationResponse {
  success: boolean
  reports: EvaluationReport[]
  summary?: {
    total: number
    avg_score: number
    grade_distribution: Record<string, number>
    avg_grade: string
  }
  error?: string
}

export interface DialogueStateResponse {
  success: boolean
  state?: Record<string, any>
  context?: Record<string, any>
  turns?: Array<Record<string, any>>
  error?: string
}

export interface TrendDataPoint {
  date: string
  precision: number
  recall: number
  mrr: number
  ndcg: number
  avg_similarity: number
  sample_count: number
}

export interface EvaluationHistoryResponse {
  success: boolean
  trend_data: TrendDataPoint[]
  days: number
  total_records: number
  error?: string
}

export const ragEvaluationApi = {
  /** 评估单条聊天记录的RAG质量 */
  evaluate: (recordId: number): Promise<EvaluationResponse> =>
    request.post('/system/rag/evaluate', { record_id: recordId }),

  /** 批量评估会话中的聊天记录 */
  evaluateBatch: (chatId: number, limit: number = 10): Promise<BatchEvaluationResponse> =>
    request.post('/system/rag/evaluate/batch', { chat_id: chatId, limit }),

  /** 获取会话的对话状态追踪信息 */
  getDialogueState: (chatId: number): Promise<DialogueStateResponse> =>
    request.get(`/system/rag/dialogue-state/${chatId}`),

  /** 获取RAG评估质量指标历史趋势 */
  getEvaluationHistory: (days: number = 7): Promise<EvaluationHistoryResponse> =>
    request.get(`/system/rag/evaluation-history`, { params: { days } }),

  /** 获取最近的会话列表（用于评估面板下拉选择） */
  getRecentChats: (limit: number = 20): Promise<any> =>
    request.get('/system/rag/recent-chats', { params: { limit } }),

  /** 获取最近的聊天记录列表（用于单条评估下拉选择） */
  getRecentRecords: (limit: number = 20): Promise<any> =>
    request.get('/system/rag/recent-records', { params: { limit } }),
}
