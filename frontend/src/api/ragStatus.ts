import { request } from '@/utils/request'

export interface EmbeddingStatus {
  status: 'active' | 'inactive'
  model_name: string
  loaded: boolean
}

export interface LLMStatus {
  status: 'active' | 'inactive'
  model_name: string | null
  latency_ms: number | null
  error: string | null
}

export interface Stats {
  count: number
  last_updated: string | null
}

export interface RAGStatusResponse {
  embedding: EmbeddingStatus
  llm: LLMStatus
  terminology: Stats
  training: Stats
}

export const ragStatusApi = {
  /**
   * 获取 RAG 系统状态
   * 包括：向量嵌入模型状态、LLM 连接状态、术语库统计、知识库统计
   */
  getStatus: (): Promise<RAGStatusResponse> =>
    request.get('/system/rag/status', { requestOptions: { silent: true } }),
}
