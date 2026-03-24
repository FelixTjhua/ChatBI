<script setup lang="ts">
import BaseAnswer from './BaseAnswer.vue'
import PdfAnswerBlock from './PdfAnswerBlock.vue'
import { Chat, chatApi, ChatInfo, type ChatMessage, ChatRecord, questionApi } from '@/api/chat.ts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ChartBlock from '@/views/chat/chat-block/ChartBlock.vue'
import MdComponent from '@/views/chat/component/MdComponent.vue'
import AddChartDialog from '@/views/dashboard/components/AddChartDialog.vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus-secondary'
import icon_into_item_outlined from '@/assets/svg/icon_into-item_outlined.svg'
import icon_down_outlined from '@/assets/svg/icon_down_outlined.svg'
import { Icon } from '@/components/icon-custom'

const { t } = useI18n()

// RAG 处理阶段状态
type ProcessStage = 'idle' | 'query' | 'rag' | 'sql' | 'execute' | 'chart' | 'direct' | 'analysis' | 'predict' | 'done'
const processStage = ref<ProcessStage>('idle')

// 是否为直接回答路径（非SQL）
const isDirectAnswerPath = ref(false)

// 延迟分析加载状态：data_query 路由的 inline-analysis 在 finish 之后执行，
// 此 ref 控制图表下方的"正在生成分析报告"加载指示器
const deferredAnalysisLoading = ref(false)

// 延迟预测加载状态：预测意图在图表展示后执行预测报告生成，
// 此 ref 控制图表下方的"正在生成预测报告"加载指示器
const deferredPredictLoading = ref(false)

// RAG 检索结果 - 优先从流式数据获取，否则从历史记录获取
const ragResults = ref<{
  terminologies: any[]
  sql_examples: any[]
  custom_prompts?: any[]
} | null>(null)

// 分层推荐问题（三层推荐系统：pre/mid/post）
const layeredRecommendations = ref<{
  mid: Array<{ question: string; type: string; layer: string }>
  post: Array<{ question: string; type: string; layer: string }>
} | null>(null)

// 先定义 props
const props = withDefaults(
  defineProps<{
    recordId?: number
    chatList?: Array<ChatInfo>
    currentChatId?: number
    currentChat?: ChatInfo
    message?: ChatMessage
    loading?: boolean
    reasoningName: 'sql_answer' | 'chart_answer' | Array<'sql_answer' | 'chart_answer'>
    inputType?: 'manual' | 'recommend'
  }>(),
  {
    recordId: undefined,
    chatList: () => [],
    currentChatId: undefined,
    currentChat: () => new ChatInfo(),
    message: undefined,
    loading: false,
    inputType: 'manual',
  }
)

// 然后监听 message.record 变化，从历史记录加载 RAG 结果
watch(
  () => props.message?.record,
  (newRecord) => {
    if (newRecord?.rag_results && !ragResults.value) {
      // 从历史记录加载 RAG 结果
      ragResults.value = newRecord.rag_results
    }
  },
  { immediate: true, deep: true }
)

// 动态计算场景类型，根据意图和数据源类型决定
const dynamicScenarioType = computed<'sql' | 'sql_analysis' | 'sql_prediction' | 'general_chat'>(() => {
  const intent = props.message?.record?.intent
  
  // PDF数据源始终走general_chat（文档问答路径）
  if (props.currentChat?.ds_type === 'pdf') return 'general_chat'
  
  // 9种细粒度意图 → 前端场景类型映射
  // 非数据查询类意图 → general_chat（直接回答路径）
  if (intent === 'irrelevant_query' || intent === 'term_explanation' || intent === 'ambiguous_query') return 'general_chat'
  // 兼容旧意图
  if (intent === 'summarization' || intent === 'general_chat' || intent === 'document_qa') return 'general_chat'
  
  // 统计分析/对比分析/趋势分析意图 → sql_analysis（SQL→Chart→完整分析，注入分析提示词）
  if (intent === 'statistical_analysis' || intent === 'comparison_analysis' || intent === 'trend_analysis' || intent === 'analysis') return 'sql_analysis'
  // 预测意图 → sql_prediction
  if (intent === 'prediction') return 'sql_prediction'
  
  // 数据查询类意图（fact_query, follow_up）
  const dataQueryIntents = ['fact_query', 'follow_up', 'data_query']
  if (dataQueryIntents.includes(intent) && (props.message?.record?.analysis || deferredAnalysisLoading.value) && !props.message?.record?.analysis_record_id) {
    return 'sql_analysis'
  }
  
  // 直接回答路径（非SQL）也视为一般对话
  if (isDirectAnswerPath.value && !intent) return 'general_chat'
  
  return 'sql'
})

// 判断是否为 PDF 数据源的直接回答（使用专用 PdfAnswerBlock 展示）
const isPdfAnswer = computed(() => {
  if (!props.message?.record?.direct_answer) return false
  // 方式1：RAG 结果中有 design_intent = document_qa
  const rag = ragResults.value as any
  if (rag?.design_intent === 'document_qa') return true
  // 方式2：RAG 结果中有 document_chunks（PDF 检索片段）
  if (rag?.document_chunks?.length > 0) return true
  // 方式3：RAG 结果中有 pdf_source_summary
  if (rag?.pdf_source_summary) return true
  // 方式4：当前 chat 的 ds_type 为 pdf
  if (props.currentChat?.ds_type === 'pdf') return true
  // 方式5：回答文本中包含来源标注（兜底检测，防止 ragResults 丢失时来源标注作为纯文本渲染）
  const answer = props.message.record.direct_answer
  if (answer && (/【来源[:：]/.test(answer) || /\[Source[:：]/i.test(answer))) return true
  return false
})

const emits = defineEmits([
  'finish',
  'error',
  'stop',
  'scrollBottom',
  'clickQuestion',
  'update:loading',
  'update:chatList',
  'update:currentChat',
  'update:currentChatId',
])

const index = computed(() => {
  if (props.message?.index) {
    return props.message.index
  }
  if (props.message?.index === 0) {
    return 0
  }
  return -1
})

const _currentChatId = computed({
  get() {
    return props.currentChatId
  },
  set(v) {
    emits('update:currentChatId', v)
  },
})

const _currentChat = computed({
  get() {
    return props.currentChat
  },
  set(v) {
    emits('update:currentChat', v)
  },
})

const _chatList = computed({
  get() {
    return props.chatList
  },
  set(v) {
    emits('update:chatList', v)
  },
})

const _loading = computed({
  get() {
    return props.loading
  },
  set(v) {
    emits('update:loading', v)
  },
})

// 监听loading状态和message.isTyping变化
// 确保只有当前正在处理的消息才显示处理阶段
watch(
  [() => props.loading, () => props.message?.isTyping, () => props.message?.record?.id],
  ([newLoading, newIsTyping, _recordId]) => {
    // 如果不是当前正在输入的消息，确保 processStage 为 idle
    if (!newIsTyping) {
      // 如果消息已经完成（有finish标记或有错误），重置状态
      if (
        props.message?.record?.finish ||
        props.message?.record?.error ||
        processStage.value === 'done'
      ) {
        if (!deferredAnalysisLoading.value && !deferredPredictLoading.value) {
          processStage.value = 'idle'
        }
      }
      return
    }

    // 当前消息正在输入，且 loading 为 true，启动处理阶段
    if (newIsTyping && newLoading && processStage.value === 'idle') {
      processStage.value = 'query'
    }

    // 当 loading 变为 false 时，检查是否需要重置
    if (!newLoading && processStage.value !== 'idle' && processStage.value !== 'done') {
      if (props.message?.record?.error) {
        processStage.value = 'idle'
      }
    }
  },
  { immediate: true }
)

const stopFlag = ref(false)

const sendMessage = async () => {
  stopFlag.value = false
  _loading.value = true

  // 重置状态
  processStage.value = 'query'
  isDirectAnswerPath.value = false
  ragResults.value = null
  deferredAnalysisLoading.value = false
  deferredPredictLoading.value = false

  if (index.value < 0) {
    _loading.value = false
    processStage.value = 'idle'
    return
  }

  const currentRecord: ChatRecord = _currentChat.value.records[index.value]

  let error: boolean = false
  if (_currentChatId.value === undefined) {
    error = true
  }
  if (error) {
    _loading.value = false
    processStage.value = 'idle'
    return
  }

  // 将 ragFallbackTimer 提升到 try 外部，
  // 确保 catch 块也能清除定时器，防止错误后定时器仍触发导致幽灵进度指示器
  let ragFallbackTimer: ReturnType<typeof setTimeout> | null = null

  try {
    const controller: AbortController = new AbortController()
    const param = {
      question: currentRecord.question,
      chat_id: _currentChatId.value,
      rag_enabled: true, // RAG始终启用
      input_type: props.inputType, // 提问方式：manual=手动输入, recommend=推荐问题点击
    }
    
    const response = await questionApi.add(param, controller)
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')

    let sql_answer = ''
    let chart_answer = ''

    let tempResult = ''

    // 移除硬编码的1500ms setTimeout
    // 改为由后端SSE事件驱动阶段切换（rag_results/sql-result/direct-answer事件）
    // 仅保留一个更长的安全兜底超时（8秒），防止后端异常时前端永远卡在RAG阶段
    ragFallbackTimer = setTimeout(() => {
      if (processStage.value === 'rag' || processStage.value === 'query') {
        if (isDirectAnswerPath.value) {
          processStage.value = 'direct'
        } else {
          processStage.value = 'sql'
        }
      }
    }, 8000)

    while (true) {
      if (stopFlag.value) {
        controller.abort()
        processStage.value = 'idle'
        clearTimeout(ragFallbackTimer)
        break
      }

      const { done, value } = await reader.read()
      if (done) {
        clearTimeout(ragFallbackTimer)
        // 处理 tempResult 中残留的未解析数据（与 RecommendQuestion.vue 对齐）
        // 当 reader.read() 返回 done=true 时，tempResult 可能还有不带尾部 \n\n 的消息
        if (tempResult.trim()) {
          const lastMatch = tempResult.match(/data:\{.*\}/g)
          if (lastMatch) {
            for (const str of lastMatch) {
              try {
                const data = JSON.parse(str.replace('data:{', '{'))
                if (data.type === 'finish') {
                  currentRecord.finish = true
                  emits('finish', currentRecord.id)
                } else if (data.type === 'rag_results' && data.data) {
                  ragResults.value = data.data
                  if (currentRecord) currentRecord.rag_results = ragResults.value
                } else if (data.type === 'thinking_stage' && data.data && currentRecord) {
                  if (!currentRecord.thinking_process) {
                    currentRecord.thinking_process = { question: currentRecord.question, rag_enabled: true, stages: {} }
                  }
                  currentRecord.thinking_process.stages = currentRecord.thinking_process.stages || {}
                  currentRecord.thinking_process.stages[data.stage] = data.data
                }
              } catch { /* ignore parse errors for residual data */ }
            }
          }
          tempResult = ''
        }
        // 安全兜底：直接回答路径完成但内容为空时，提供回退信息
        if (isDirectAnswerPath.value && !currentRecord.direct_answer) {
          if (currentRecord.analysis_reasoning_content) {
            // LLM只输出了推理内容但没有最终回答，将推理内容作为回答展示
            currentRecord.direct_answer = currentRecord.analysis_reasoning_content
            currentRecord.analysis = currentRecord.direct_answer
          } else {
            // 完全没有内容，显示友好提示
            currentRecord.direct_answer = t('chat.direct_answer_empty_fallback')
            currentRecord.analysis = currentRecord.direct_answer
          }
        }
        _loading.value = false
        processStage.value = 'done'
        // 延迟分析/预测加载期间不重置 processStage 到 idle
        // 原代码无条件在1.5s后重置，导致进度条显示"完成"但Step 6仍在加载
        // 现在：如果有延迟加载任务，等待其完成后再重置
        if (deferredAnalysisLoading.value || deferredPredictLoading.value) {
          // 延迟加载进行中，由 inline_analysis_finish / inline_predict_finish 事件触发重置
          const unwatch = watch(
            [deferredAnalysisLoading, deferredPredictLoading],
            ([aLoading, pLoading]) => {
              if (!aLoading && !pLoading) {
                unwatch()
                setTimeout(() => {
                  processStage.value = 'idle'
                }, 1500)
              }
            },
          )
        } else {
          // 无延迟加载任务，正常1.5s后重置
          setTimeout(() => {
            processStage.value = 'idle'
          }, 1500)
        }
        break
      }

      let chunk = decoder.decode(value, { stream: true })
      tempResult += chunk

      // 使用 \n\n 分隔符解析 SSE 事件（与 RecommendQuestion.vue 对齐）
      // 原正则 /data:.*}\n\n/g 在 data 字段包含 } 时会截断或误匹配
      const events = tempResult.split('\n\n')
      // 最后一个元素可能是不完整的事件，保留到下次处理
      tempResult = events.pop() || ''

      if (events.length === 0) {
        continue
      }

      for (const event of events) {
        const trimmed = event.trim()
        if (!trimmed || !trimmed.startsWith('data:')) continue
        const jsonStr = trimmed.slice(5).trim() // 去掉 "data:" 前缀
        if (!jsonStr) continue

            let data
            try {
              data = JSON.parse(jsonStr)
            } catch (err) {
              throw err
            }

            if (data.code && data.code !== 200) {
              // 设置错误信息到record
              currentRecord.error = data.msg || data.content || 'Unknown error'
              _loading.value = false
              processStage.value = 'idle'
              clearTimeout(ragFallbackTimer)
              emits('error')
              return
            }

            switch (data.type) {
              case 'id':
                currentRecord.id = data.id
                _currentChat.value.records[index.value].id = data.id
                break
              case 'info':
                // Server info message
                break
              case 'brief':
                _currentChat.value.brief = data.brief
                _chatList.value.forEach((c: Chat) => {
                  if (c.id === _currentChat.value.id) {
                    c.brief = _currentChat.value.brief
                  }
                })
                break
              case 'error':
                currentRecord.error = data.content || data.msg || 'Unknown error'
                // error事件必须设置_loading=false并return，防止while循环继续等待
                _loading.value = false
                processStage.value = 'idle'
                emits('error')
                return
              case 'rag_results':
                // 接收 RAG 检索结果
                // 内联分析/预测会发送第二次rag_results，需要合并custom_prompts而非覆盖
                if (ragResults.value && data.data) {
                  // 合并custom_prompts（追加新类型的提示词，避免覆盖SQL路径的结果）
                  const existingPrompts = ragResults.value.custom_prompts || []
                  const newPrompts = data.data.custom_prompts || []
                  const existingTypes = new Set(existingPrompts.map((p: any) => p.type))
                  const mergedPrompts = [...existingPrompts]
                  for (const np of newPrompts) {
                    if (!existingTypes.has(np.type)) {
                      mergedPrompts.push(np)
                    }
                  }
                  // 合并术语（取并集）
                  const existingTerms = ragResults.value.terminologies || []
                  const newTerms = data.data.terminologies || []
                  const existingTermWords = new Set(existingTerms.map((t: any) => t.word))
                  const mergedTerms = [...existingTerms]
                  for (const nt of newTerms) {
                    if (!existingTermWords.has(nt.word)) {
                      mergedTerms.push(nt)
                    }
                  }
                  ragResults.value = {
                    ...ragResults.value,
                    terminologies: mergedTerms,
                    custom_prompts: mergedPrompts,
                    custom_prompt_checked: true,
                  }
                } else {
                  ragResults.value = data.data
                }
                // 保存到record中
                if (currentRecord) {
                  currentRecord.rag_results = ragResults.value
                  
                  // 将rag_results转换为thinking_process的rag_retrieval阶段
                  if (!currentRecord.thinking_process) {
                    currentRecord.thinking_process = {
                      question: currentRecord.question,
                      rag_enabled: ragResults.value?.rag_enabled !== false,
                      stages: {}
                    }
                  }
                  
                  // 添加/更新rag_retrieval阶段
                  currentRecord.thinking_process.stages = currentRecord.thinking_process.stages || {}
                  const ragEnabled = ragResults.value?.rag_enabled !== false
                  // 保留已有的 rag_retrieval 嵌套数据（表检索信息来自 thinking_stage 事件）
                  // 内联分析/预测会再次发送 rag_results，如果直接覆盖会丢失表检索数据
                  const existingRagStage = currentRecord.thinking_process.stages.rag_retrieval || {}
                  currentRecord.thinking_process.stages.rag_retrieval = {
                    ...existingRagStage,
                    stage: 'rag_retrieval',
                    status: ragEnabled ? 'completed' : 'skipped',
                    timestamp: new Date().toISOString(),
                    rag_enabled: ragEnabled,
                    terminologies: ragResults.value?.terminologies || existingRagStage.terminologies || [],
                    sql_examples: ragResults.value?.sql_examples || existingRagStage.sql_examples || [],
                    custom_prompts: ragResults.value?.custom_prompts || existingRagStage.custom_prompts || [],
                    terminology_quality: ragResults.value?.terminology_quality || existingRagStage.terminology_quality || {},
                    example_quality: ragResults.value?.example_quality || existingRagStage.example_quality || {},
                    rag_impact: ragResults.value?.rag_impact || existingRagStage.rag_impact || {}
                  }
                }
                // RAG 检索完成
                // 如果后端标记 rag_enabled=false（纯寒暄），直接跳过 rag 阶段
                if (data.data?.rag_enabled === false && processStage.value === 'rag') {
                  isDirectAnswerPath.value = true
                  processStage.value = 'direct'
                }
                // 收到 rag_results 意味着查询理解已完成，推进到 RAG 检索阶段
                if (processStage.value === 'query') {
                  processStage.value = 'rag'
                }
                break
              case 'intent':
                // 接收意图检测结果
                if (currentRecord) {
                  currentRecord.intent = data.intent
                }
                // 检测是否为直接回答路径（新9种意图中的非SQL类）
                const directAnswerIntents = ['summarization', 'general_chat', 'irrelevant_query', 'term_explanation', 'ambiguous_query', 'document_qa']
                if (data.intent && directAnswerIntents.includes(data.intent)) {
                  isDirectAnswerPath.value = true
                  // RAG已完成，推进到直接回答阶段
                  if (processStage.value === 'rag' || processStage.value === 'query') {
                    processStage.value = 'direct'
                  }
                } else {
                  // SQL路径：RAG已完成，推进到SQL生成阶段
                  if (processStage.value === 'rag' || processStage.value === 'query') {
                    processStage.value = 'sql'
                  }
                }
                break
              case 'datasource':
                // 接收数据源选择结果，更新ds_type
                if (data.ds_type) {
                  _currentChat.value.ds_type = data.ds_type
                }
                if (data.datasource_name) {
                  _currentChat.value.datasource_name = data.datasource_name
                }
                if (data.engine_type) {
                  _currentChat.value.engine_type = data.engine_type
                }
                if (data.id) {
                  _currentChat.value.datasource = data.id
                }
                break
              case 'datasource-result':
                // 数据源选择推理过程（reasoning_content），无需前端展示
                break
              case 'direct-answer':
                // 接收直接回答（非SQL路径：总结、概括、一般对话、文档理解等）
                isDirectAnswerPath.value = true
                if (data.reasoning_content) {
                  // 直接回答的推理内容存到analysis_reasoning_content（而非sql_reasoning_content）
                  if (!currentRecord.analysis_reasoning_content) {
                    currentRecord.analysis_reasoning_content = ''
                  }
                  currentRecord.analysis_reasoning_content += data.reasoning_content
                }
                if (data.content) {
                  if (!currentRecord.direct_answer) {
                    currentRecord.direct_answer = ''
                  }
                  currentRecord.direct_answer += data.content
                  // 同时存到analysis字段以便复用已有的展示逻辑
                  currentRecord.analysis = currentRecord.direct_answer
                }
                processStage.value = 'direct' // 直接回答生成阶段
                break
              case 'thinking_stage':
                // 接收思考过程阶段数据并保存到record
                if (currentRecord && data.data) {
                  // 初始化thinking_process
                  if (!currentRecord.thinking_process) {
                    currentRecord.thinking_process = {
                      question: currentRecord.question,
                      rag_enabled: true,
                      stages: {}
                    }
                  }
                  
                  // 保存阶段数据
                  currentRecord.thinking_process.stages = currentRecord.thinking_process.stages || {}
                  currentRecord.thinking_process.stages[data.stage] = data.data
                  
                  // SQL生成阶段完成时：如果sql_answer为空但sql_generating_content有内容（Gemini等无reasoning模型），
                  // 将content格式化后设为sql_answer，让完成状态下Step 2通过MdComponent展示
                  if (data.stage === 'sql_generation' && data.data?.status === 'completed') {
                    if (!currentRecord.sql_answer && currentRecord.sql_generating_content) {
                      // 尝试从原始LLM输出中提取可读文本
                      let rawContent = currentRecord.sql_generating_content.trim()
                      // 去除可能的markdown代码块包裹
                      const jsonBlockMatch = rawContent.match(/```(?:json)?\s*([\s\S]*?)\s*```/)
                      if (jsonBlockMatch) {
                        rawContent = jsonBlockMatch[1].trim()
                      }
                      try {
                        const parsed = JSON.parse(rawContent)
                        if (parsed && typeof parsed === 'object') {
                          const parts: string[] = []
                          if (parsed.message) parts.push(parsed.message)
                          if (parsed.sql) parts.push('```sql\n' + parsed.sql + '\n```')
                          currentRecord.sql_answer = parts.length > 0 ? parts.join('\n\n') : currentRecord.sql_generating_content
                        } else {
                          currentRecord.sql_answer = currentRecord.sql_generating_content
                        }
                      } catch {
                        // 不是JSON，直接使用原始文本
                        currentRecord.sql_answer = currentRecord.sql_generating_content
                      }
                    }
                  }
                }
                break
              case 'sql-result':
                // 收到 SQL 推理内容，进入 SQL 生成阶段
                if (processStage.value === 'rag' || processStage.value === 'query') {
                  processStage.value = 'sql'
                }
                // 实时累积 SQL 思考过程
                if (data.reasoning_content) {
                  sql_answer += data.reasoning_content
                  _currentChat.value.records[index.value].sql_answer = sql_answer
                  // 同时更新 sql_reasoning_content 字段（用于历史记录）
                  _currentChat.value.records[index.value].sql_reasoning_content = sql_answer
                }
                // 实时累积 SQL 生成内容（用于展示生成过程）
                if (data.content) {
                  if (!_currentChat.value.records[index.value].sql_generating_content) {
                    _currentChat.value.records[index.value].sql_generating_content = ''
                  }
                  _currentChat.value.records[index.value].sql_generating_content += data.content
                }
                break
              case 'sql':
                // SQL 生成完成，进入执行阶段
                processStage.value = 'execute'
                _currentChat.value.records[index.value].sql = data.content
                break
              case 'sql-data':
                // SQL 执行完成，进入图表生成阶段
                processStage.value = 'chart'
                getChatData(_currentChat.value.records[index.value].id)
                // 缓存降级时显示提示
                if (data.cache_warning && currentRecord) {
                  currentRecord.cache_warning = data.cache_warning
                }
                break
              case 'chart-result':
                // 实时累积图表生成思考过程
                if (data.reasoning_content) {
                  chart_answer += data.reasoning_content
                  _currentChat.value.records[index.value].chart_answer = chart_answer
                  // 同时更新 chart_reasoning_content 字段（用于历史记录）
                  _currentChat.value.records[index.value].chart_reasoning_content = chart_answer
                }
                break
              case 'chart':
                _currentChat.value.records[index.value].chart = data.content
                break
              case 'smart-answer':
                // 将进度阶段设为 chart，让进度指示器显示"生成图表"步骤已到达
                processStage.value = 'chart'
                currentRecord.smart_answer = data.content
                // 保存chart配置（带smart_output标记，历史加载时识别）
                if (data.chart) {
                  currentRecord.chart = data.chart
                }
                break
              case 'finish':
                processStage.value = 'done'
                currentRecord.finish = true
                emits('finish', currentRecord.id)
                break
              // 分析和预测结果直接在同一个流中返回，不再需要前端发起二次请求
              case 'inline_analysis_start':
                // 统一 UX：分析意图在图表展示后开始生成分析报告
                // 无论 finish 是否已发送，都显示"正在生成分析报告"加载指示器
                if (!currentRecord.finish) {
                  processStage.value = 'analysis'
                  // 图表已展示（sql-data 已到达），在图表下方显示分析加载指示器
                  deferredAnalysisLoading.value = true
                } else {
                  // finish 已发送，图表已展示 → 在图表下方显示分析加载指示器
                  deferredAnalysisLoading.value = true
                }
                break
              case 'inline-analysis-result':
                // 内联分析结果：直接累积到当前record的analysis字段
                if (data.reasoning_content) {
                  if (!currentRecord.analysis_reasoning_content) {
                    currentRecord.analysis_reasoning_content = ''
                  }
                  currentRecord.analysis_reasoning_content += data.reasoning_content
                }
                if (data.content) {
                  if (!currentRecord.analysis) {
                    currentRecord.analysis = ''
                  }
                  currentRecord.analysis += data.content
                }
                break
              case 'inline_analysis_finish':
                // 内联分析完成 → 关闭延迟加载指示器
                deferredAnalysisLoading.value = false
                // 记录 data_analysis 阶段为 completed，让思考过程步骤显示✓
                if (currentRecord) {
                  if (!currentRecord.thinking_process) {
                    currentRecord.thinking_process = { question: currentRecord.question, rag_enabled: true, stages: {} }
                  }
                  if (!currentRecord.thinking_process.stages) {
                    currentRecord.thinking_process.stages = {}
                  }
                  currentRecord.thinking_process.stages.data_analysis = {
                    ...(currentRecord.thinking_process.stages.data_analysis || {}),
                    status: 'completed',
                  }
                }
                break;
              case 'inline_analysis_error':
                // 内联分析失败，关闭加载指示器，不影响图表展示
                deferredAnalysisLoading.value = false
                break
              case 'inline_predict_start':
                // 统一 UX：预测意图在图表展示后开始生成预测报告
                // 在图表下方显示"正在生成预测报告"加载指示器
                if (!currentRecord.finish) {
                  processStage.value = 'predict'
                }
                deferredPredictLoading.value = true
                break
              case 'inline-predict-result':
                // 内联预测结果分离JSON数据行和报告文本
                // generate_predict输出格式：第一行是JSON数组（预测数据），后续行是预测报告
                // 健壮的JSON检测
                if (data.reasoning_content) {
                  if (!currentRecord.predict_reasoning_content) {
                    currentRecord.predict_reasoning_content = ''
                  }
                  currentRecord.predict_reasoning_content += data.reasoning_content
                  // 同步到predict_thinking（与PredictAnswer.vue对齐）
                  currentRecord.predict_thinking = currentRecord.predict_reasoning_content
                }
                if (data.content) {
                  // 使用临时变量累积完整内容，分离第一行JSON和后续报告
                  if (!currentRecord._predict_full_text) {
                    currentRecord._predict_full_text = ''
                  }
                  currentRecord._predict_full_text += data.content
                  
                  const trimmedFull = currentRecord._predict_full_text.trim()
                  
                  if (trimmedFull.includes('\n')) {
                    const splitIdx = trimmedFull.indexOf('\n')
                    const firstLine = trimmedFull.substring(0, splitIdx).trim()
                    let reportText = trimmedFull.substring(splitIdx + 1).trim()
                    
                    // 第一行如果是JSON数组/对象，不放入predict展示字段
                    if (firstLine.startsWith('[') || firstLine.startsWith('{')) {
                      // 报告文本中可能残留JSON片段（LLM输出不稳定）
                      // 移除报告开头的JSON行（连续的以[或{开头的行）
                      const reportLines = reportText.split('\n')
                      const cleanLines: string[] = []
                      let passedJsonPrefix = false
                      for (const line of reportLines) {
                        const tl = line.trim()
                        if (!passedJsonPrefix && (tl.startsWith('[') || tl.startsWith('{') || tl.startsWith(']') || tl === '')) {
                          continue // 跳过报告开头的JSON残留行和空行
                        }
                        passedJsonPrefix = true
                        cleanLines.push(line)
                      }
                      reportText = cleanLines.join('\n').trim()
                      currentRecord.predict = reportText
                      currentRecord.predict_content = reportText
                    } else {
                      // 非JSON格式，全部作为报告展示
                      currentRecord.predict = trimmedFull
                      currentRecord.predict_content = trimmedFull
                    }
                  } else {
                    // 还没遇到换行符，暂不更新predict（等待完整的第一行）
                    // 但如果内容明显不是JSON开头，直接展示
                    if (trimmedFull && !trimmedFull.startsWith('[') && !trimmedFull.startsWith('{')) {
                      currentRecord.predict = trimmedFull
                      currentRecord.predict_content = trimmedFull
                    }
                  }
                }
                break
              case 'inline_predict_finish':
                // 内联预测完成 → 关闭延迟加载指示器
                deferredPredictLoading.value = false
                // 内联预测完成 → 等待finish事件
                // 最终处理 - 如果predict仍为空，从_predict_full_text做最终分离
                // 使用与流式处理相同的JSON清理逻辑
                if (!currentRecord.predict && currentRecord._predict_full_text) {
                  const fullText = currentRecord._predict_full_text.trim()
                  if (fullText) {
                    if (fullText.includes('\n')) {
                      const splitIdx = fullText.indexOf('\n')
                      const fl = fullText.substring(0, splitIdx).trim()
                      let rpt = fullText.substring(splitIdx + 1).trim()
                      if (fl.startsWith('[') || fl.startsWith('{')) {
                        // 第一行是JSON，清理报告中的JSON残留
                        const reportLines = rpt.split('\n')
                        const cleanLines: string[] = []
                        let passedJsonPrefix = false
                        for (const line of reportLines) {
                          const tl = line.trim()
                          if (!passedJsonPrefix && (tl.startsWith('[') || tl.startsWith('{') || tl.startsWith(']') || tl === '')) {
                            continue
                          }
                          passedJsonPrefix = true
                          cleanLines.push(line)
                        }
                        rpt = cleanLines.join('\n').trim()
                        currentRecord.predict = rpt || ''
                        currentRecord.predict_content = rpt || ''
                      } else {
                        currentRecord.predict = fullText
                        currentRecord.predict_content = fullText
                      }
                    } else if (!fullText.startsWith('[') && !fullText.startsWith('{')) {
                      currentRecord.predict = fullText
                      currentRecord.predict_content = fullText
                    }
                  }
                }
                // 清理临时字段
                delete currentRecord._predict_full_text
                // 确保 data_prediction 阶段标记为 completed，让思考过程步骤6亮起
                // 与 inline_analysis_finish 对齐：即使后端 thinking_stage 事件丢失，前端也能兜底
                if (currentRecord) {
                  if (!currentRecord.thinking_process) {
                    currentRecord.thinking_process = { question: currentRecord.question, rag_enabled: true, stages: {} }
                  }
                  if (!currentRecord.thinking_process.stages) {
                    currentRecord.thinking_process.stages = {}
                  }
                  currentRecord.thinking_process.stages.data_prediction = {
                    ...(currentRecord.thinking_process.stages.data_prediction || {}),
                    stage: 'data_prediction',
                    status: 'completed',
                  }
                }
                break;
              case 'inline_predict_unavailable':
                // 预测不可用：数据不满足条件，显示原因提示，关闭加载指示器
                deferredPredictLoading.value = false
                if (data.reason) {
                  currentRecord.predict_unavailable_reason = data.reason
                }
                break
              case 'inline_predict_error':
                // 内联预测失败，关闭加载指示器，不影响图表展示
                deferredPredictLoading.value = false
                break
              case 'prediction_confidence':
                // 内联预测置信度评分（由prediction_service生成）
                // 保存到record中供后续展示
                if (currentRecord && data.data) {
                  currentRecord.prediction_confidence = data.data
                }
                break
              case 'layered_recommendations':
                // 接收分层推荐问题（三层推荐系统的mid/post层）
                if (data.data) {
                  layeredRecommendations.value = {
                    mid: data.data.mid || [],
                    post: data.data.post || [],
                  }
                  // 保存到record中，以便历史记录恢复
                  if (currentRecord) {
                    currentRecord.layered_recommendations = layeredRecommendations.value
                  }
                }
                break
            }
            await nextTick()
          }
    }
  } catch (error) {
    if (ragFallbackTimer) clearTimeout(ragFallbackTimer)
    deferredAnalysisLoading.value = false
    deferredPredictLoading.value = false
    if (!currentRecord.error) {
      currentRecord.error = ''
    }
    if (currentRecord.error.trim().length !== 0) {
      currentRecord.error = currentRecord.error + '\n'
    }
    currentRecord.error = currentRecord.error + 'Error:' + error
    processStage.value = 'idle'
    emits('error')
  } finally {
    _loading.value = false
  }
}

const loadingData = ref(false)

// 用于取消上一次 getChatData 请求，防止快速切换时旧请求覆盖新数据
let getChatDataAbortController: AbortController | null = null

function getChatData(recordId?: number) {
  if (!recordId) return
  
  // 取消上一次未完成的请求
  if (getChatDataAbortController) {
    getChatDataAbortController.abort()
  }
  getChatDataAbortController = new AbortController()
  const currentAbort = getChatDataAbortController
  
  loadingData.value = true
  chatApi
    .get_chart_data(recordId, { signal: currentAbort.signal })
    .then((response) => {
      // 双重防护：检查请求是否已被取消 + 检查 recordId 是否仍匹配当前消息
      if (currentAbort.signal.aborted) return
      if (props.message?.record?.id === recordId) {
        props.message.record.data = response
      }
      // 同时尝试更新 _currentChat 中的记录（兼容其他引用）
      _currentChat.value.records.forEach((record) => {
        if (record.id === recordId) {
          record.data = response
        }
      })
    })
    .catch((err) => {
      // 被取消的请求不提示错误
      if (currentAbort.signal.aborted) return
      ElMessage.error(t('common.load_failed'))
    })
    .finally(() => {
      if (!currentAbort.signal.aborted) {
        loadingData.value = false
        emits('scrollBottom')
      }
    })
}

function stop() {
  stopFlag.value = true
  _loading.value = false
  // 停止时清理延迟加载状态，防止 F1 watcher 永远等待
  deferredAnalysisLoading.value = false
  deferredPredictLoading.value = false
  emits('stop')
}

onBeforeUnmount(() => {
  // 组件卸载时取消未完成的数据请求，防止更新已销毁的组件
  if (getChatDataAbortController) {
    getChatDataAbortController.abort()
    getChatDataAbortController = null
  }
  stop()
})

// ========== 添加到仪表板（多类型洞察卡片）==========
const insightDialogRef = ref<InstanceType<typeof AddChartDialog> | null>(null)

// 判断当前回答是否同时包含图表和文本（分析/预测）
const hasChartAndAnalysis = computed(() => {
  const record = props.message?.record
  if (!record) return false
  return !record.direct_answer && !record.smart_answer && record.chart && record.analysis && !record.analysis_record_id
})
const hasChartAndPrediction = computed(() => {
  const record = props.message?.record
  if (!record) return false
  return !record.direct_answer && record.chart && record.predict && !record.predict_record_id
})
const hasChartOnly = computed(() => {
  const record = props.message?.record
  if (!record) return false
  return !record.direct_answer && !record.smart_answer && record.chart && record.data?.data?.length
})

function buildInsightComponent(cardType: string) {
  const record = props.message?.record
  if (!record) return null

  let chartBaseInfo: any = {}
  try { chartBaseInfo = JSON.parse(record.chart || '{}') } catch {}

  const base = {
    id: `insight-${Date.now()}`,
    component: 'InsightCard',
    style: { left: 20, top: 20, width: 620, height: 420, rotate: 0 },
    propValue: {
      cardType,
      question: record.question || '',
      recordId: record.id,
      datasourceId: (record as any)?.datasource || null,
      dsType: props.currentChat?.ds_type || null,
    } as any,
  }

  // 填充图表数据的通用函数
  const fillChartData = (defaultType = 'bar') => {
    base.propValue.chartType = chartBaseInfo.type || defaultType
    base.propValue.data = record.data?.data || []
    base.propValue.fields = record.data?.fields || []
    // table 类型用 columns，其他类型用 axis
    if (chartBaseInfo.columns) {
      base.propValue.columns = chartBaseInfo.columns || []
    }
    if (chartBaseInfo.axis) {
      base.propValue.xAxis = chartBaseInfo.axis.x ? [chartBaseInfo.axis.x] : []
      base.propValue.yAxis = chartBaseInfo.axis.y ? [chartBaseInfo.axis.y] : []
      base.propValue.series = chartBaseInfo.axis.series ? [chartBaseInfo.axis.series] : []
    }
  }

  if (cardType === 'chart') {
    // 仅图表
    base.propValue.title = chartBaseInfo.title || t('dashboard.type_chart')
    fillChartData()
  } else if (cardType === 'analysis') {
    // 图表 + 分析文本（组合）
    base.propValue.title = chartBaseInfo.title || t('dashboard.type_analysis')
    base.propValue.content = record.analysis || ''
    fillChartData()
  } else if (cardType === 'analysis_text_only') {
    // 仅分析文本（无图表）
    base.propValue.cardType = 'analysis'
    base.propValue.title = chartBaseInfo.title || t('dashboard.type_analysis')
    base.propValue.content = record.analysis || ''
    // 不填充图表数据
  } else if (cardType === 'prediction') {
    // 图表 + 预测文本（组合）
    base.propValue.title = chartBaseInfo.title || t('dashboard.type_prediction')
    base.propValue.content = record.predict || ''
    fillChartData('line')
  } else if (cardType === 'prediction_text_only') {
    // 仅预测文本（无图表）
    base.propValue.cardType = 'prediction'
    base.propValue.title = chartBaseInfo.title || t('dashboard.type_prediction')
    base.propValue.content = record.predict || ''
    // 不填充图表数据
  } else if (cardType === 'data_table') {
    base.propValue.title = t('dashboard.type_data_table')
    base.propValue.data = record.data?.data || []
    base.propValue.fields = record.data?.fields || []
    base.propValue.sql = record.sql || ''
    base.style.width = 700
  } else if (cardType === 'document_qa') {
    base.propValue.title = t('dashboard.type_document_qa')
    base.propValue.content = record.direct_answer || ''
    const rag = ragResults.value as any
    if (rag?.document_chunks) {
      base.propValue.sources = rag.document_chunks
    }
    base.style.height = 360
  }

  return base
}

function addInsightToDashboard(cardType: string) {
  const component = buildInsightComponent(cardType)
  if (component) {
    insightDialogRef.value?.open(component)
  }
}


onMounted(() => {
  // 直接回答类型不需要加载图表数据
  if (props.message?.record?.id && props.message?.record?.finish && !props.message?.record?.direct_answer) {
    // 历史记录：检查是否为智能输出（smart_output）的记录
    const chartStr = props.message?.record?.chart
    if (chartStr && !props.message.record.smart_answer) {
      try {
        const chartObj = typeof chartStr === 'string' ? JSON.parse(chartStr) : chartStr
        if (chartObj?.smart_output && chartObj?.title) {
          props.message.record.smart_answer = chartObj.title
        }
      } catch {
        // 不是JSON格式，忽略
      }
    }

    // 历史记录：如果intent是非SQL类型，将analysis字段映射为direct_answer
    const intent = props.message?.record?.intent
    const directAnswerIntents = ['summarization', 'general_chat', 'irrelevant_query', 'term_explanation', 'ambiguous_query', 'document_qa']
    // 兜底：intent 为空但记录有 analysis 且无 sql/chart（说明是直接回答路径，intent 保存失败）
    const isDirectByContent = !intent && props.message.record.analysis && !props.message.record.sql && !props.message.record.chart
    if ((intent && directAnswerIntents.includes(intent)) || isDirectByContent) {
      if (props.message.record.analysis && !props.message.record.direct_answer) {
        // analysis字段可能是JSON格式（包含content和reasoning_content）
        let analysisContent = props.message.record.analysis
        try {
          const parsed = JSON.parse(analysisContent)
          if (parsed && typeof parsed === 'object' && parsed.content) {
            analysisContent = parsed.content
            // 同时恢复推理内容
            if (parsed.reasoning_content && !props.message.record.analysis_reasoning_content) {
              props.message.record.analysis_reasoning_content = parsed.reasoning_content
            }
          }
        } catch {
          // 不是JSON格式，直接使用原始字符串（兼容旧数据）
        }
        props.message.record.direct_answer = analysisContent
        isDirectAnswerPath.value = true
      }
    } else {
      // 智能输出记录不需要加载图表数据
      if (!props.message.record.smart_answer) {
        // 仅在数据尚未加载时请求，避免与 index.vue 的 loadRecordData 重复请求
        if (!props.message.record.data) {
          loadingData.value = true  // 立即设置加载状态，避免短暂显示"暂无数据"
          getChatData(props.message.record.id)
        }
      }
      
      // 历史记录：解析内联分析结果的JSON格式
      // 数据查询类意图的记录，analysis字段是JSON格式 {'content': ..., 'reasoning_content': ...}
      const sqlIntents = ['analysis', 'data_query', 'statistical_analysis', 'fact_query', 'comparison_analysis', 'trend_analysis', 'follow_up']
      if (sqlIntents.includes(intent) && props.message.record.analysis && !props.message.record.analysis_record_id) {
        try {
          const parsed = JSON.parse(props.message.record.analysis)
          if (parsed && typeof parsed === 'object' && parsed.content) {
            props.message.record.analysis = parsed.content
            if (parsed.reasoning_content && !props.message.record.analysis_reasoning_content) {
              props.message.record.analysis_reasoning_content = parsed.reasoning_content
            }
          }
        } catch {
          // 不是JSON格式，直接使用原始字符串
        }
      }
      // 历史记录：解析内联预测结果的JSON格式
      if (intent === 'prediction' && props.message.record.predict && !props.message.record.predict_record_id) {
        try {
          const parsed = JSON.parse(props.message.record.predict)
          if (parsed && typeof parsed === 'object' && parsed.content) {
            props.message.record.predict = parsed.content
            if (parsed.reasoning_content && !props.message.record.predict_reasoning_content) {
              props.message.record.predict_reasoning_content = parsed.reasoning_content
            }
          }
        } catch {
          // 不是JSON格式，直接使用原始字符串
        }
      }
    }
  }
  // 兜底：finish 为 false 但有 chart/sql 的历史记录（流中断导致 finish 未设置）
  // 仍然需要加载数据，否则会永远显示"暂无数据"
  else if (props.message?.record?.id && !props.message?.record?.finish && 
           !props.message?.record?.direct_answer && props.message?.record?.chart &&
           !props.message?.record?.data && !props.message?.isTyping) {
    loadingData.value = true
    getChatData(props.message.record.id)
  }
  // 后端 Fix 32 将 prediction_confidence 持久化到 thinking_process.stages.data_prediction
  // SSE 流式接收时存到 record.prediction_confidence，但刷新后该字段丢失
  if (props.message?.record && !props.message.record.prediction_confidence) {
    const tp = props.message.record.thinking_process
    const predStage = tp?.stages?.data_prediction
    if (predStage?.prediction_confidence) {
      props.message.record.prediction_confidence = predStage.prediction_confidence
    }
  }

  // 加载历史分层推荐问题
  if (props.message?.record?.layered_recommendations) {
    layeredRecommendations.value = props.message.record.layered_recommendations
  } else if (props.message?.record?.thinking_process?.stages) {
    // 从 thinking_process 恢复分层推荐问题（兜底）
    // format_record 已提取 layered_recommendations，此处为双重保障
    const stages = props.message.record.thinking_process.stages
    if (typeof stages === 'object' && !Array.isArray(stages)) {
      const lr: any = {}
      for (const layer of ['pre', 'mid', 'post']) {
        const recStage = stages[`recommendation_${layer}`]
        if (recStage?.extra_data?.questions?.length || recStage?.questions?.length) {
          const extra = recStage.extra_data || recStage
          const questions = extra.questions || []
          const types = extra.types || []
          lr[layer] = questions.map((q: string, i: number) => ({
            question: q, type: types[i] || '', layer
          }))
        }
      }
      if (Object.keys(lr).length > 0) {
        layeredRecommendations.value = lr
      }
    }
  }

  // 加载历史 RAG 检索结果并同步到thinking_process
  if (props.message?.record?.rag_results) {
    try {
      const parsedRagResults = typeof props.message.record.rag_results === 'string' 
        ? JSON.parse(props.message.record.rag_results)
        : props.message.record.rag_results
      
      ragResults.value = parsedRagResults
      
      // 确保历史记录也有thinking_process
      const currentRecord = props.message.record
      if (currentRecord && parsedRagResults && !currentRecord.thinking_process?.stages?.rag_retrieval) {
        if (!currentRecord.thinking_process) {
          currentRecord.thinking_process = {
            question: currentRecord.question,
            rag_enabled: parsedRagResults.rag_enabled !== false,
            stages: {}
          }
        }
        
        currentRecord.thinking_process.stages = currentRecord.thinking_process.stages || {}
        const histRagEnabled = parsedRagResults.rag_enabled !== false
        currentRecord.thinking_process.stages.rag_retrieval = {
          stage: 'rag_retrieval',
          status: histRagEnabled ? 'completed' : 'skipped',
          timestamp: new Date().toISOString(),
          rag_enabled: histRagEnabled,
          terminologies: parsedRagResults.terminologies || [],
          sql_examples: parsedRagResults.sql_examples || [],
          custom_prompts: parsedRagResults.custom_prompts || [],
          terminology_quality: parsedRagResults.terminology_quality || {},
          example_quality: parsedRagResults.example_quality || {},
          rag_impact: parsedRagResults.rag_impact || {}
        }
      }
    } catch {
      // Failed to parse RAG results from history
    }
  }
})

defineExpose({ sendMessage, index: () => index.value, stop })
</script>

<template>
  <BaseAnswer 
    v-if="message" 
    :message="message" 
    :reasoning-name="reasoningName" 
    :loading="_loading"
    :rag-results="ragResults"
    :scenario-type="dynamicScenarioType"
    :process-stage="processStage"
    :hide-citation="false"
    :deferred-analysis-loading="deferredAnalysisLoading"
    :deferred-predict-loading="deferredPredictLoading"
  >
    <!-- 🧠 智能输出：单行极值结果，自然语言直接回答 -->
    <div v-if="message?.record?.smart_answer" class="smart-answer-block">
      <span class="smart-answer-text">{{ message.record.smart_answer }}</span>
    </div>

    <!-- 缓存降级提示（设计文档"容错处理"） -->
    <div v-if="message?.record?.cache_warning" class="cache-warning-banner">
      <span class="cw-icon">⚠️</span>
      <span class="cw-text">{{ message.record.cache_warning }}</span>
    </div>

    <ChartBlock
      v-show="!message?.record?.direct_answer && !message?.record?.smart_answer"
      style="margin-top: 6px"
      :message="message"
      :record-id="recordId"
      :loading-data="loadingData"
    />
    <!-- 内联分析结果展示（分析意图自动触发，不需要单独的AnalysisAnswer组件） -->
    <!--  延迟分析加载指示器：data_query 路由的分析在 finish 后执行，图表下方显示加载状态 -->
    <div v-if="deferredAnalysisLoading && !message?.record?.analysis" class="deferred-analysis-loading">
      <span class="dal-icon">📈</span>
      <span class="dal-text">{{ t('chat.generating_analysis') }}</span>
      <span class="dal-dots"><span></span><span></span><span></span></span>
    </div>
    <div v-show="!message?.record?.direct_answer && !message?.record?.smart_answer && message?.record?.analysis && !message?.record?.analysis_record_id" class="inline-analysis-block">
      <MdComponent :message="message.record.analysis" />
      <!-- 分析内容正在流入时，底部显示生成中提示 -->
      <div v-if="deferredAnalysisLoading" class="dal-streaming-hint">
        <span class="dal-streaming-dots"><span></span><span></span><span></span></span>
        <span class="dal-streaming-text">{{ t('chat.generating_analysis') }}...</span>
      </div>
    </div>
    <!-- 内联预测结果展示（预测意图自动触发） -->
    <!--  延迟预测加载指示器：预测意图在图表展示后执行，图表下方显示加载状态 -->
    <div v-if="deferredPredictLoading && !message?.record?.predict" class="deferred-analysis-loading">
      <span class="dal-icon">🔮</span>
      <span class="dal-text">{{ t('chat.generating_prediction') }}</span>
      <span class="dal-dots"><span></span><span></span><span></span></span>
    </div>
    <div v-show="!message?.record?.direct_answer && message?.record?.predict && !message?.record?.predict_record_id" class="inline-predict-block">
      <MdComponent :message="message.record.predict" />
      <!-- 预测内容正在流入时，底部显示生成中提示 -->
      <div v-if="deferredPredictLoading" class="dal-streaming-hint">
        <span class="dal-streaming-dots"><span></span><span></span><span></span></span>
        <span class="dal-streaming-text">{{ t('chat.generating_prediction') }}...</span>
      </div>
    </div>

    <!-- 预测不可用提示 -->
    <div v-if="message?.record?.predict_unavailable_reason" class="predict-unavailable-hint">
      <span class="hint-icon">⚠️</span>
      <span class="hint-text">{{ t('chat.predict_unavailable') }}{{ message.record.predict_unavailable_reason }}</span>
    </div>
    <!-- 直接回答展示（非SQL路径：总结、概括、一般对话等） -->
    <!-- PDF 数据源：使用专用 PdfAnswerBlock（含来源溯源、页码引用） -->
    <PdfAnswerBlock
      v-if="isPdfAnswer"
      :answer="message.record.direct_answer"
      :rag-results="ragResults"
    />
    <!-- 非 PDF 数据源：普通直接回答 -->
    <div v-else-if="message?.record?.direct_answer" class="direct-answer-block">
      <MdComponent :message="message.record.direct_answer" />
    </div>
    <slot></slot>
    <template #tool>
      <!-- ========== 统一"添加到洞察"按钮区域（支持图表+文本组合保存） ========== -->
      <!--  修复 UX-SAVE：finish 在 step5（图表完成）时就设为 true，但分析/预测文本可能仍在流式生成中
           必须同时检查 deferredAnalysisLoading/deferredPredictLoading，防止用户保存不完整的文本 -->
      <!-- 场景1：图表 + 分析文本 → 下拉菜单提供3种保存方式 -->
      <div v-if="hasChartAndAnalysis && message?.record?.finish && !deferredAnalysisLoading && !deferredPredictLoading" class="insight-save-btn">
        <el-dropdown trigger="click" popper-class="insight-dropdown-popper" @command="addInsightToDashboard">
          <el-button text size="small" class="insight-btn">
            <el-icon size="14"><icon_into_item_outlined /></el-icon>
            <span>{{ t('dashboard.save_to_dashboard') }}</span>
            <el-icon size="12" style="margin-left: 2px;"><icon_down_outlined /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="analysis">📊 {{ t('dashboard.save_chart_and_text') }}</el-dropdown-item>
              <el-dropdown-item command="chart">📈 {{ t('dashboard.save_chart_only') }}</el-dropdown-item>
              <el-dropdown-item command="analysis_text_only">📝 {{ t('dashboard.save_text_only') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <!-- 场景2：图表 + 预测文本 → 下拉菜单提供3种保存方式 -->
      <div v-else-if="hasChartAndPrediction && message?.record?.finish && !deferredAnalysisLoading && !deferredPredictLoading" class="insight-save-btn">
        <el-dropdown trigger="click" popper-class="insight-dropdown-popper" @command="addInsightToDashboard">
          <el-button text size="small" class="insight-btn">
            <el-icon size="14"><icon_into_item_outlined /></el-icon>
            <span>{{ t('dashboard.save_to_dashboard') }}</span>
            <el-icon size="12" style="margin-left: 2px;"><icon_down_outlined /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="prediction">🔮 {{ t('dashboard.save_chart_and_text') }}</el-dropdown-item>
              <el-dropdown-item command="chart">📈 {{ t('dashboard.save_chart_only') }}</el-dropdown-item>
              <el-dropdown-item command="prediction_text_only">📝 {{ t('dashboard.save_text_only') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <!-- 场景3：仅图表（无分析/预测文本） → 直接保存按钮 -->
      <div v-else-if="hasChartOnly && !message?.record?.direct_answer && message?.record?.finish && !deferredAnalysisLoading && !deferredPredictLoading" class="insight-save-btn">
        <el-tooltip :content="t('dashboard.save_chart_only')" placement="top">
          <el-button text size="small" class="insight-btn" @click="addInsightToDashboard('chart')">
            <el-icon size="14"><icon_into_item_outlined /></el-icon>
            <span>{{ t('dashboard.save_to_dashboard') }}</span>
          </el-button>
        </el-tooltip>
      </div>
      <!-- 直接回答/文档问答：添加到仪表板 -->
      <div v-if="message?.record?.direct_answer && message?.record?.finish" class="insight-save-btn">
        <el-tooltip :content="t('dashboard.save_qa')" placement="top">
          <el-button text size="small" class="insight-btn" @click="addInsightToDashboard('document_qa')">
            <el-icon size="14"><icon_into_item_outlined /></el-icon>
            <span>{{ t('dashboard.save_to_dashboard') }}</span>
          </el-button>
        </el-tooltip>
      </div>
      <slot name="tool"></slot>
    </template>
    <template #footer>
      <slot name="footer"></slot>
    </template>
  </BaseAnswer>
  <AddChartDialog ref="insightDialogRef" />
</template>

<style scoped lang="less">
.direct-answer-block {
  padding: 16px 20px;
  background: rgba(139, 92, 246, 0.04);
  border: 1px solid rgba(139, 92, 246, 0.12);
  border-radius: 12px;
  margin-top: 6px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 14px;
  line-height: 1.7;
  
  :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
    color: rgba(255, 255, 255, 0.95);
    margin-top: 16px;
    margin-bottom: 8px;
  }
  
  :deep(ul), :deep(ol) {
    padding-left: 20px;
    margin: 8px 0;
  }
  
  :deep(li) {
    margin: 4px 0;
  }
  
  :deep(strong) {
    color: #c4b5fd;
  }
  
  :deep(p) {
    margin: 8px 0;
  }
}

.inline-analysis-block,
.inline-predict-block {
  padding: 16px 20px;
  background: rgba(139, 92, 246, 0.04);
  border: 1px solid rgba(139, 92, 246, 0.12);
  border-radius: 12px;
  margin-top: 10px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 14px;
  line-height: 1.7;
  
  .inline-section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(139, 92, 246, 0.1);
    
    .section-icon {
      font-size: 16px;
    }
    
    .section-title {
      font-size: 14px;
      font-weight: 600;
      color: #c4b5fd;
    }
  }
  
  :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
    color: rgba(255, 255, 255, 0.95);
    margin-top: 16px;
    margin-bottom: 8px;
  }
  
  :deep(ul), :deep(ol) {
    padding-left: 20px;
    margin: 8px 0;
  }
  
  :deep(li) {
    margin: 4px 0;
  }
  
  :deep(strong) {
    color: #c4b5fd;
  }
  
  :deep(p) {
    margin: 8px 0;
  }
}

.predict-unavailable-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.2);
  border-radius: 12px;
  margin-top: 10px;
  
  .hint-icon {
    font-size: 16px;
    flex-shrink: 0;
  }
  
  .hint-text {
    font-size: 13px;
    color: rgba(245, 158, 11, 0.9);
  }
}

.deferred-analysis-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  background: rgba(139, 92, 246, 0.04);
  border: 1px solid rgba(139, 92, 246, 0.12);
  border-radius: 12px;
  margin-top: 10px;
  animation: fadeIn 0.3s ease;

  .dal-icon {
    font-size: 18px;
    flex-shrink: 0;
  }

  .dal-text {
    font-size: 13px;
    color: rgba(196, 181, 253, 0.9);
    font-weight: 500;
  }

  .dal-dots {
    display: inline-flex;
    gap: 3px;
    margin-left: 2px;

    span {
      width: 5px;
      height: 5px;
      border-radius: 50%;
      background: rgba(139, 92, 246, 0.6);
      animation: dalBounce 1.4s ease-in-out infinite;

      &:nth-child(2) { animation-delay: 0.2s; }
      &:nth-child(3) { animation-delay: 0.4s; }
    }
  }
}

@keyframes dalBounce {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1.2); }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.dal-streaming-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid rgba(139, 92, 246, 0.08);

  .dal-streaming-dots {
    display: inline-flex;
    gap: 3px;

    span {
      width: 4px;
      height: 4px;
      border-radius: 50%;
      background: rgba(139, 92, 246, 0.5);
      animation: dalBounce 1.4s ease-in-out infinite;

      &:nth-child(2) { animation-delay: 0.2s; }
      &:nth-child(3) { animation-delay: 0.4s; }
    }
  }

  .dal-streaming-text {
    font-size: 12px;
    color: rgba(196, 181, 253, 0.6);
  }
}

.cache-warning-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.2);
  border-radius: 10px;
  margin-top: 8px;

  .cw-icon {
    font-size: 15px;
    flex-shrink: 0;
  }

  .cw-text {
    font-size: 12px;
    color: rgba(253, 224, 71, 0.85);
    line-height: 1.4;
  }
}

.smart-answer-block {
  padding: 16px 20px;
  background: rgba(139, 92, 246, 0.06);
  border: 1px solid rgba(139, 92, 246, 0.15);
  border-radius: 12px;
  margin-top: 6px;
  
  .smart-answer-text {
    font-size: 15px;
    color: rgba(255, 255, 255, 0.92);
    line-height: 1.6;
  }
}

.layered-recommendations-block {
  margin-top: 14px;
  
  .lr-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    
    .lr-icon { font-size: 16px; }
    .lr-title {
      font-size: 13px;
      font-weight: 600;
      color: rgba(255, 255, 255, 0.8);
    }
  }
  
  .lr-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
  
  .lr-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    background: rgba(139, 92, 246, 0.06);
    border: 1px solid rgba(139, 92, 246, 0.15);
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
    
    &:hover {
      background: rgba(139, 92, 246, 0.12);
      border-color: rgba(139, 92, 246, 0.3);
      transform: translateY(-1px);
    }
    
    .lr-layer-badge { font-size: 14px; flex-shrink: 0; }
    .lr-text {
      flex: 1;
      font-size: 13px;
      color: rgba(255, 255, 255, 0.85);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .lr-arrow {
      font-size: 12px;
      color: rgba(139, 92, 246, 0.5);
      flex-shrink: 0;
      transition: transform 0.2s;
    }
    
    &:hover .lr-arrow {
      transform: translateX(3px);
      color: rgba(139, 92, 246, 0.8);
    }
  }
}

.insight-save-btn {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
  .insight-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    color: #a78bfa;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 6px;
    transition: all 0.2s;
    &:hover {
      color: #c4b5fd;
      background: rgba(139, 92, 246, 0.1);
    }
    span { font-size: 12px; }
  }
}

</style>

<style lang="less">
/* 下拉菜单全局样式（el-dropdown popper 渲染在 body 下，scoped 无法覆盖） */
.insight-dropdown-popper {
  background: #1e1433 !important;
  border: 1px solid rgba(139, 92, 246, 0.3) !important;
  border-radius: 8px !important;

  .el-dropdown-menu,
  .ed-dropdown-menu {
    background: transparent !important;
    border: none !important;
    padding: 4px 0 !important;
  }

  .el-dropdown-menu__item,
  .ed-dropdown-menu__item {
    color: #e2e8f0 !important;
    font-size: 13px !important;
    padding: 10px 16px !important;
    line-height: 1.4 !important;

    &:hover,
    &:focus {
      background: rgba(139, 92, 246, 0.2) !important;
      color: #f8fafc !important;
    }
  }

  .el-popper__arrow,
  .ed-popper__arrow {
    display: none !important;
  }
}
</style>
