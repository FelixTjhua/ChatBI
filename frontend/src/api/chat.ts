import { request } from '@/utils/request'
import { getDate } from '@/utils/utils.ts'

export const questionApi = {
  pager: (pageNumber: number, pageSize: number) =>
    request.get(`/chat/question/pager/${pageNumber}/${pageSize}`),
  /* add: (data: any) => new Promise((resolve, reject) => {
      request.post('/chat/question', data, { responseType: 'stream', timeout: 0, onDownloadProgress: p => {
        resolve(p)
      }}).catch(e => reject(e))
    }), */
  // add: (data: any) => request.post('/chat/question', data),
  add: (data: any, controller?: AbortController) =>
    request.fetchStream('/chat/question', data, controller),
  edit: (data: any) => request.put('/chat/question', data),
  delete: (id: number) => request.delete(`/chat/question/${id}`),
  query: (id: number) => request.get(`/chat/question/${id}`),
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  create_time?: Date | string
  content?: string | number
  record?: ChatRecord
  isTyping?: boolean
  isDeleting?: boolean  // 标记消息正在被删除
  first_chat?: boolean
  recommended_question?: string
  index: number
}

export class ChatRecord {
  id?: number
  chat_id?: number
  create_time?: Date | string
  finish_time?: Date | string
  question?: string
  sql_answer?: string  // SQL 生成的思考过程
  sql?: string
  data?: string | any
  chart_answer?: string  // 图表生成的思考过程
  chart?: string
  analysis?: string  // 分析结果内容
  analysis_thinking?: string  // 分析的思考过程
  predict?: string  // 预测报告文本（内联预测展示用）
  predict_thinking?: string  //  预测推理内容（与format_record的predict_thinking对齐）
  predict_content?: string  // 预测结果内容
  predict_data?: string | any
  finish?: boolean = false
  error?: string
  run_time: number = 0
  first_chat: boolean = false
  recommended_question?: string
  recommend_error?: string // 推荐问题的错误状态（JSON格式：{type, message}）
  analysis_record_id?: number
  predict_record_id?: number
  // 新增：从后端 reasoning_content 映射的字段
  sql_reasoning_content?: string  // 后端返回的 SQL 推理内容
  chart_reasoning_content?: string  // 后端返回的图表推理内容
  analysis_reasoning_content?: string  // 后端返回的分析推理内容
  predict_reasoning_content?: string  // 后端返回的预测推理内容
  // RAG 相关字段
  rag_enabled?: boolean  // RAG 永远开启，此字段仅用于历史兼容
  rag_results?: string | any
  // 思考过程字段
  thinking_process?: string | any  // 完整的思考过程（JSON 字符串或对象）
  // 意图路由字段
  intent?: string  // 检测到的用户意图：data_query, analysis, prediction, general_chat
  direct_answer?: string  // 直接回答内容（非SQL路径）
  smart_answer?: string  // 智能输出：单行极值结果的自然语言回答
  predict_unavailable_reason?: string  // 预测不可用原因（数据不满足时间序列条件）
  sql_generating_content?: string  // SQL生成过程中的实时内容（JSON模式LLM的content输出）
  input_type?: string  // 提问方式：manual=手动输入, recommend=推荐问题点击
  layered_recommendations?: any  // 分层推荐问题（三层推荐系统：pre/mid/post）
  prediction_confidence?: any  // 预测置信度评分（内联预测场景）
  cache_warning?: string  // 缓存降级提示（数据库查询使用过期缓存时）

  constructor() {
    // 使用 toChatRecord() 工厂方法从后端数据构造实例
    // 所有字段通过工厂方法逐字段赋值，避免 30+ 位置参数的脆弱构造函数
    this.finish = false
    this.run_time = 0
    this.first_chat = false
    this.rag_enabled = true
  }
}

export class Chat {
  id?: number
  create_time?: Date | string
  create_by?: number
  brief?: string
  chat_type?: string
  datasource?: number
  engine_type?: string
  ds_type?: string

  constructor()
  constructor(
    id: number,
    create_time: Date | string,
    create_by: number,
    brief: string,
    chat_type: string,
    datasource: number,
    engine_type: string
  )
  constructor(
    id?: number,
    create_time?: Date | string,
    create_by?: number,
    brief?: string,
    chat_type?: string,
    datasource?: number,
    engine_type?: string
  ) {
    this.id = id
    this.create_time = getDate(create_time)
    this.create_by = create_by
    this.brief = brief
    this.chat_type = chat_type
    this.datasource = datasource
    this.engine_type = engine_type
  }
}

export class ChatInfo extends Chat {
  datasource_name?: string
  datasource_exists: boolean = true
  records: Array<ChatRecord> = []

  constructor()
  constructor(chat: Chat)
  constructor(
    id: number,
    create_time: Date | string,
    create_by: number,
    brief: string,
    chat_type: string,
    datasource: number,
    engine_type: string,
    ds_type: string,
    datasource_name: string,
    datasource_exists: boolean,
    records: Array<ChatRecord>
  )
  constructor(
    param1?: number | Chat,
    create_time?: Date | string,
    create_by?: number,
    brief?: string,
    chat_type?: string,
    datasource?: number,
    engine_type?: string,
    ds_type?: string,
    datasource_name?: string,
    datasource_exists: boolean = true,
    records: Array<ChatRecord> = []
  ) {
    super()
    if (param1 !== undefined) {
      if (param1 instanceof Chat) {
        this.id = param1.id
        this.create_time = getDate(param1.create_time)
        this.create_by = param1.create_by
        this.brief = param1.brief
        this.chat_type = param1.chat_type
        this.datasource = param1.datasource
        this.engine_type = param1.engine_type
        this.ds_type = param1.ds_type
      } else {
        this.id = param1
        this.create_time = getDate(create_time)
        this.create_by = create_by
        this.brief = brief
        this.chat_type = chat_type
        this.datasource = datasource
        this.engine_type = engine_type
        this.ds_type = ds_type
      }
    }
    this.datasource_name = datasource_name
    this.datasource_exists = datasource_exists
    this.records = records
  }
}

// 使用 fromData 工厂方法替代脆弱的 30+ 位置参数构造函数
// 原代码依赖参数顺序，新增字段时极易出错（参数错位导致数据串列）
const toChatRecord = (data?: any): ChatRecord | undefined => {
  if (!data) {
    return undefined
  }
  const record = new ChatRecord()
  record.id = data.id
  record.chat_id = data.chat_id
  record.create_time = getDate(data.create_time)
  record.finish_time = getDate(data.finish_time)
  record.question = data.question
  record.sql_answer = data.sql_answer
  record.sql = data.sql
  record.data = data.data
  record.chart_answer = data.chart_answer
  record.chart = data.chart
  // 统一解析 analysis/predict 的 JSON 格式
  if (typeof data.analysis === 'string' && data.analysis) {
    try {
      const parsed = JSON.parse(data.analysis)
      if (parsed && typeof parsed === 'object' && parsed.content !== undefined) {
        record.analysis = parsed.content
        if (parsed.reasoning_content && !data.analysis_reasoning_content) {
          record.analysis_reasoning_content = parsed.reasoning_content
        }
      } else {
        record.analysis = data.analysis
      }
    } catch {
      record.analysis = data.analysis
    }
  } else {
    record.analysis = data.analysis
  }
  record.analysis_thinking = data.analysis_thinking
  if (typeof data.predict === 'string' && data.predict) {
    try {
      const parsed = JSON.parse(data.predict)
      if (parsed && typeof parsed === 'object' && parsed.content !== undefined) {
        record.predict = parsed.content
        if (parsed.reasoning_content && !data.predict_reasoning_content) {
          record.predict_reasoning_content = parsed.reasoning_content
        }
      } else {
        record.predict = data.predict
      }
    } catch {
      record.predict = data.predict
    }
  } else {
    record.predict = data.predict
  }
  record.predict_thinking = data.predict_thinking
  record.predict_content = data.predict_content
  record.predict_data = data.predict_data
  record.finish = !!data.finish
  record.error = data.error
  record.run_time = data.run_time ?? 0
  record.first_chat = !!data.first_chat
  record.recommended_question = data.recommended_question
  record.recommend_error = data.recommend_error
  record.analysis_record_id = data.analysis_record_id
  record.predict_record_id = data.predict_record_id
  record.sql_reasoning_content = data.sql_reasoning_content
  record.chart_reasoning_content = data.chart_reasoning_content
    // 仅在后端返回了非空值时覆盖（后端 JOIN chat_log 获取的值优先）
  if (data.analysis_reasoning_content) {
    record.analysis_reasoning_content = data.analysis_reasoning_content
  }
  if (data.predict_reasoning_content) {
    record.predict_reasoning_content = data.predict_reasoning_content
  }
  record.rag_enabled = data.rag_enabled !== undefined ? data.rag_enabled : true
  record.intent = data.intent
  record.direct_answer = data.direct_answer
  record.smart_answer = data.smart_answer
  record.predict_unavailable_reason = data.predict_unavailable_reason
  record.input_type = data.input_type
  record.layered_recommendations = data.layered_recommendations
  record.prediction_confidence = data.prediction_confidence
  record.cache_warning = data.cache_warning
  record.sql_generating_content = data.sql_generating_content
  // 解析 JSON 字符串字段
  if (typeof data.rag_results === 'string' && data.rag_results) {
    try { record.rag_results = JSON.parse(data.rag_results) } catch { record.rag_results = data.rag_results }
  } else {
    record.rag_results = data.rag_results
  }
  if (typeof data.thinking_process === 'string' && data.thinking_process) {
    try { record.thinking_process = JSON.parse(data.thinking_process) } catch { record.thinking_process = data.thinking_process }
  } else {
    record.thinking_process = data.thinking_process
  }
  return record
}
const toChatRecordList = (list: any = []): ChatRecord[] => {
  const records: Array<ChatRecord> = []
  for (let i = 0; i < list.length; i++) {
    const record = toChatRecord(list[i])
    if (record) {
      records.push(record)
    }
  }
  return records
}

export const chatApi = {
  toChatInfo: (data?: any): ChatInfo | undefined => {
    if (!data) {
      return undefined
    }
    return new ChatInfo(
      data.id,
      data.create_time,
      data.create_by,
      data.brief,
      data.chat_type,
      data.datasource,
      data.engine_type,
      data.ds_type,
      data.datasource_name,
      data.datasource_exists,
      toChatRecordList(data.records)
    )
  },
  toChatInfoList: (list: any[] = []): ChatInfo[] => {
    const infos: Array<ChatInfo> = []
    for (let i = 0; i < list.length; i++) {
      const chatInfo = chatApi.toChatInfo(list[i])
      if (chatInfo) {
        infos.push(chatInfo)
      }
    }
    return infos
  },
  list: (): Promise<Array<ChatInfo>> => {
    return request.get('/chat/list')
  },
  get: (id: number): Promise<ChatInfo> => {
    return request.get(`/chat/${id}`)
  },
  get_with_Data: (id: number): Promise<ChatInfo> => {
    return request.get(`/chat/${id}/with_data`)
  },
  get_chart_data: (record_id?: number, config?: any): Promise<any> => {
    return request.get(`/chat/record/${record_id}/data`, config)
  },
  get_chart_predict_data: (record_id?: number, config?: any): Promise<any> => {
    return request.get(`/chat/record/${record_id}/predict_data`, config)
  },
  startChat: (data: any): Promise<ChatInfo> => {
    return request.post('/chat/start', data)
  },
  renameChat: (chat_id: number | undefined, brief: string): Promise<string> => {
    return request.post('/chat/rename', { id: chat_id, brief: brief })
  },
  deleteChat: (id: number | undefined): Promise<string> => {
    return request.delete(`/chat/${id}`)
  },
  deleteRecord: (record_id: number | undefined): Promise<string> => {
    return request.delete(`/chat/record/${record_id}`)
  },
  analysis: (record_id: number | undefined, controller?: AbortController) => {
    // RAG 永远开启，不需要参数（对齐 SQLBot）
    return request.fetchStream(`/chat/record/${record_id}/analysis`, {}, controller)
  },
  predict: (record_id: number | undefined, controller?: AbortController) => {
    // RAG 永远开启，不需要参数（对齐 SQLBot）
    return request.fetchStream(`/chat/record/${record_id}/predict`, {}, controller)
  },
  recommendQuestions: (record_id: number | undefined, controller?: AbortController) => {
    return request.fetchStream(`/chat/recommend_questions/${record_id}`, {}, controller)
  },
  checkLLMModel: () => request.get('/system/aimodel/default', { requestOptions: { silent: true } }),
  export2Excel: (record_id: number | undefined) =>
    request.get(`/chat/record/${record_id}/excel/export`, {
      responseType: 'blob',
      requestOptions: { customError: true },
    }),
  export2Csv: (record_id: number | undefined) =>
    request.get(`/chat/record/${record_id}/csv/export`, {
      responseType: 'blob',
      requestOptions: { customError: true },
    }),
}
