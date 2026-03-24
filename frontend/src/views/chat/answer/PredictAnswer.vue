<script setup lang="ts">
import BaseAnswer from './BaseAnswer.vue'
import { chatApi, ChatInfo, type ChatMessage, ChatRecord } from '@/api/chat.ts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import MdComponent from '@/views/chat/component/MdComponent.vue'
import ChartBlock from '@/views/chat/chat-block/ChartBlock.vue'
import PredictProcessIndicator from '@/views/chat/PredictProcessIndicator.vue'
import { ElMessage, ElMessageBox } from 'element-plus-secondary'

import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    recordId?: number
    chatList?: Array<ChatInfo>
    currentChatId?: number
    currentChat?: ChatInfo
    message?: ChatMessage
    loading?: boolean
  }>(),
  {
    recordId: undefined,
    chatList: () => [],
    currentChatId: undefined,
    currentChat: () => new ChatInfo(),
    message: undefined,
    loading: false,
  }
)

const emits = defineEmits([
  'finish',
  'error',
  'scrollBottom',
  'stop',
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

// 预测处理阶段 - 更细粒度的状态追踪
// 新增 'augment' 阶段，对应上下文压缩与提示词注入
const processStage = ref<'idle' | 'query' | 'rag' | 'augment' | 'loading' | 'predicting' | 'generating' | 'chart' | 'done'>('idle')

// 映射内部阶段到 BaseAnswer 的 processStage 格式（驱动思考面板进度条）
const baseAnswerProcessStage = computed<'idle' | 'query' | 'rag' | 'predict' | 'done'>(() => {
  const s = processStage.value
  if (s === 'idle') return 'idle'
  if (s === 'done') return 'done'
  if (s === 'query') return 'query'
  if (s === 'rag') return 'rag'
  // loading/predicting/generating/chart 都属于"预测中"
  return 'predict'
})
const processProgress = ref(0) // 进度百分比 0-100
const processMessage = ref('') // 当前处理消息
const startTime = ref(0) // 开始时间
const elapsedTime = ref(0) // 已用时间（秒）

// 置信度评分数据
interface ConfidenceFactors {
  data_volume: number
  time_span: number
  trend_stability: number
  data_completeness: number
}
interface PredictionConfidence {
  score: number
  level: '高' | '中' | '低'
  factors: ConfidenceFactors
  prediction_interval: { lower: number | null; upper: number | null }
}
const confidenceData = ref<PredictionConfidence | null>(null)
const showFactorDetails = ref(false)

// 置信度等级对应的颜色
const confidenceLevelColor = computed(() => {
  if (!confidenceData.value) return '#909399'
  switch (confidenceData.value.level) {
    case '高': return '#10b981'
    case '中': return '#f59e0b'
    case '低': return '#ef4444'
    default: return '#909399'
  }
})

// 置信度等级对应的背景渐变
const confidenceLevelBg = computed(() => {
  if (!confidenceData.value) return 'rgba(144, 147, 153, 0.08)'
  switch (confidenceData.value.level) {
    case '高': return 'rgba(16, 185, 129, 0.08)'
    case '中': return 'rgba(245, 158, 11, 0.08)'
    case '低': return 'rgba(239, 68, 68, 0.08)'
    default: return 'rgba(144, 147, 153, 0.08)'
  }
})

// 置信度等级对应的边框色
const confidenceLevelBorder = computed(() => {
  if (!confidenceData.value) return 'rgba(144, 147, 153, 0.2)'
  switch (confidenceData.value.level) {
    case '高': return 'rgba(16, 185, 129, 0.25)'
    case '中': return 'rgba(245, 158, 11, 0.25)'
    case '低': return 'rgba(239, 68, 68, 0.25)'
    default: return 'rgba(144, 147, 153, 0.2)'
  }
})

// 因子得分对应的颜色
function getFactorColor(score: number): string {
  if (score >= 80) return '#10b981'
  if (score >= 50) return '#f59e0b'
  return '#ef4444'
}

// 新增：响应式的图表显示条件 - 直接使用 props.message.record
const shouldShowChart = computed(() => {
  // 关键修复：直接使用 props.message?.record，这是最直接的数据源
  const record = props.message?.record
  
  // predict_data可能是字符串或数组
  let hasPredictData = false
  if (record?.predict_data) {
    if (Array.isArray(record.predict_data)) {
      hasPredictData = record.predict_data.length > 0
    } else if (typeof record.predict_data === 'string') {
      // 字符串格式的JSON数组
      hasPredictData = record.predict_data.trim().length > 0 && 
                       record.predict_data.trim().startsWith('[')
    }
  }
  
  const hasData = !!record?.data
  const hasChart = !!record?.chart
  
  // 关键修复：预测模式下，必须同时有predict_data和data才显示图表
  // 避免过早显示空图表
  const result = hasChart && hasPredictData && hasData
  
  return result
})

// 新增：获取当前记录的 computed 属性（响应式）
const currentRecord = computed(() => {
  return _currentChat.value.records[index.value]
})

// 新增：监听 currentChat.records 的变化，同步到 message.record
// 但保留这个watch用于调试和确保数据一致性
watch(
  () => _currentChat.value.records[index.value],
  (newRecord, oldRecord) => {
    if (newRecord && props.message?.record && newRecord.id === props.message.record.id) {
      const predictDataChanged = newRecord.predict_data !== oldRecord?.predict_data
      const dataChanged = newRecord.data !== oldRecord?.data
      
      if (predictDataChanged || dataChanged) {
        // Data changed, Vue reactivity will handle UI updates
      }
    }
  },
  { deep: true, immediate: false }
)

// 实时更新已用时间
let timeInterval: any = null
const updateElapsedTime = () => {
  if (startTime.value > 0 && processStage.value !== 'done' && processStage.value !== 'idle') {
    elapsedTime.value = Math.floor((Date.now() - startTime.value) / 1000)
  }
}

const stopFlag = ref(false)
const sendMessage = async () => {
  stopFlag.value = false
  _loading.value = true
  processStage.value = 'query'
  processProgress.value = 0
  processMessage.value = ''
  startTime.value = Date.now()
  elapsedTime.value = 0
  
  // 启动时间计时器
  if (timeInterval) clearInterval(timeInterval)
  timeInterval = setInterval(updateElapsedTime, 1000)

  await nextTick()
  emits('scrollBottom')

  if (index.value < 0) {
    _loading.value = false
    processStage.value = 'idle'
    return
  }

  const currentRecord: ChatRecord = _currentChat.value.records[index.value]

  let error: boolean = false
  if (_currentChatId.value === undefined || currentRecord.predict_record_id === undefined) {
    error = true
  }
  if (error) {
    _loading.value = false
    processStage.value = 'idle'
    if (timeInterval) clearInterval(timeInterval)
    return
  }

  // UX优化：提前加载原始图表配置（不等预测完成），让图表能在predict_data到达后立即显示
  // 预测场景的chart配置来自 predict_record_id 指向的SQL查询记录
  if (currentRecord.predict_record_id) {
    const baseRecord = _currentChat.value.records.find(r => r.id === currentRecord.predict_record_id)
    if (baseRecord?.chart && !currentRecord.chart) {
      currentRecord.chart = baseRecord.chart
    }
  }

  try {
    const controller: AbortController = new AbortController()
    // RAG 永远开启，不需要参数（对齐 SQLBot）
    const response = await chatApi.predict(currentRecord.predict_record_id, controller)
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')

    let predict_answer = ''
    let predict_content = ''

    let tempResult = ''
    let hasStartedPrediction = false

    while (true) {
      if (stopFlag.value) {
        controller.abort()
        _loading.value = false
        processStage.value = 'done'
        processProgress.value = 0
        if (timeInterval) clearInterval(timeInterval)
        break
      }

      const { done, value } = await reader.read()
      if (done) {
        // 处理 tempResult 中残留的未解析数据（与 RecommendQuestion.vue 对齐）
        if (tempResult.trim()) {
          const lastMatch = tempResult.match(/data:\{.*\}/g)
          if (lastMatch) {
            for (const str of lastMatch) {
              try {
                const data = JSON.parse(str.replace('data:{', '{'))
                if (data.type === 'predict_finish') {
                  // 残留的 predict_finish 事件
                  processProgress.value = 100
                } else if (data.type === 'predict-result') {
                  if (data.content) {
                    predict_content += data.content
                    const lines = predict_content.split('\n')
                    const reportLines = lines.slice(1).join('\n').trim()
                    if (reportLines) {
                      _currentChat.value.records[index.value].predict = reportLines
                      _currentChat.value.records[index.value].predict_content = reportLines
                    }
                  }
                  if (data.reasoning_content) {
                    predict_answer += data.reasoning_content
                    _currentChat.value.records[index.value].predict_thinking = predict_answer
                    _currentChat.value.records[index.value].predict_reasoning_content = predict_answer
                  }
                } else if (data.type === 'prediction_confidence' && data.data) {
                  confidenceData.value = data.data as PredictionConfidence
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
        _loading.value = false
        processStage.value = 'done'
        if (processProgress.value < 100) {
          processProgress.value = 100
        }
        if (timeInterval) clearInterval(timeInterval)
        // 流结束时也需要 emit finish，否则父组件不知道预测已完成
        emits('finish', currentRecord.id)
        break
      }

      let chunk = decoder.decode(value, { stream: true })
      tempResult += chunk

      // 使用 \n\n 分隔符解析 SSE 事件（与 RecommendQuestion.vue 对齐）
      // 原正则 /data:.*}\n\n/g 在 data 字段包含 } 时会截断或误匹配
      const events = tempResult.split('\n\n')
      tempResult = events.pop() || ''

      if (events.length === 0) {
        continue
      }

      for (const event of events) {
        const trimmed = event.trim()
        if (!trimmed || !trimmed.startsWith('data:')) continue
        const jsonStr = trimmed.slice(5).trim()
        if (!jsonStr) continue

            let data
            try {
              data = JSON.parse(jsonStr)
            } catch (err) {
              throw err
            }

            if (data.code && data.code !== 200) {
              currentRecord.error = data.msg || data.content || 'Unknown error'
              _loading.value = false
              processStage.value = 'done'
              emits('error')
              return
            }

            switch (data.type) {
              case 'id':
                currentRecord.id = data.id
                _currentChat.value.records[index.value].id = data.id
                // 查询理解阶段（后端正在进行意图识别和查询重写）
                processStage.value = 'query'
                processProgress.value = 5
                processMessage.value = ''
                break
              case 'info':
                // Server info message - 可用于显示详细进度
                if (data.message) {
                  processMessage.value = data.message
                }
                break
              case 'rag_results':
                // 接收 RAG 检索结果（预测场景的术语/文档检索）
                // 保存到record中供思考过程面板展示
                if (currentRecord && data.data) {
                  currentRecord.rag_results = data.data
                  
                  // 同步到thinking_process.stages.rag_retrieval（对齐ChartAnswer.vue）
                  if (!currentRecord.thinking_process) {
                    currentRecord.thinking_process = {
                      question: currentRecord.question,
                      rag_enabled: data.data.rag_enabled !== false,
                      stages: {}
                    }
                  }
                  currentRecord.thinking_process.stages = currentRecord.thinking_process.stages || {}
                  const ragEnabledP = data.data.rag_enabled !== false
                  // 保留已有的 rag_retrieval 嵌套数据（表检索信息来自 thinking_stage 事件）
                  const existingRagStageP = currentRecord.thinking_process.stages.rag_retrieval || {}
                  currentRecord.thinking_process.stages.rag_retrieval = {
                    ...existingRagStageP,
                    stage: 'rag_retrieval',
                    status: ragEnabledP ? 'completed' : 'skipped',
                    timestamp: new Date().toISOString(),
                    rag_enabled: ragEnabledP,
                    terminologies: data.data.terminologies || existingRagStageP.terminologies || [],
                    sql_examples: data.data.sql_examples || existingRagStageP.sql_examples || [],
                    custom_prompts: data.data.custom_prompts || existingRagStageP.custom_prompts || [],
                    terminology_quality: data.data.terminology_quality || existingRagStageP.terminology_quality || {},
                    example_quality: data.data.example_quality || existingRagStageP.example_quality || {},
                    rag_impact: data.data.rag_impact || existingRagStageP.rag_impact || {}
                  }
                }
                break
              case 'thinking_stage':
                // 保存thinking_stage数据到thinking_process（之前只更新进度条，丢弃了阶段数据）
                // 对齐ChartAnswer.vue的实现，确保思考面板能展示所有阶段
                if (currentRecord && data.data) {
                  if (!currentRecord.thinking_process) {
                    currentRecord.thinking_process = {
                      question: currentRecord.question,
                      rag_enabled: true,
                      stages: {}
                    }
                  }
                  currentRecord.thinking_process.stages = currentRecord.thinking_process.stages || {}
                  currentRecord.thinking_process.stages[data.stage] = data.data
                }
                // 进度条更新
                if (data.stage === 'query_understanding') {
                  processStage.value = 'rag'
                  processProgress.value = 10
                  processMessage.value = ''
                } else if (data.stage === 'rag_retrieval') {
                  // RAG检索完成后进入上下文增强阶段（而非直接跳到预测）
                  processStage.value = 'augment'
                  processProgress.value = 20
                  processMessage.value = ''
                } else if (data.stage === 'context_compression' || data.stage === 'prompt_construction') {
                  // 上下文压缩和提示词构建都属于增强阶段
                  processStage.value = 'augment'
                  processProgress.value = 35
                } else if (data.stage === 'data_prediction') {
                  processStage.value = 'generating'
                  processProgress.value = 50
                }
                break
              case 'prediction_confidence':
                // 接收预测置信度评分数据
                if (data.data) {
                  confidenceData.value = data.data as PredictionConfidence
                }
                break
              case 'error':
                // 错误处理
                const errorMsg = data.content || data.msg || 'Unknown error'
                currentRecord.error = errorMsg
                // error事件必须设置_loading=false并return，否则while循环继续等待reader.read()导致卡死
                _loading.value = false
                processStage.value = 'done'
                processProgress.value = 0
                if (timeInterval) clearInterval(timeInterval)
                
                // 根据错误类型显示不同的引导消息
                if (errorMsg.includes('Insufficient data') || errorMsg.includes('至少需要') || errorMsg.includes('rows are required')) {
                  ElMessageBox.alert(
                    t('qa.predict_err_insufficient_data') + '\n\n' + t('qa.predict_err_insufficient_data_hint'),
                    t('qa.predict_err_insufficient_data_title'),
                    {
                      confirmButtonText: t('qa.predict_err_confirm'),
                      type: 'warning'
                    }
                  ).catch(() => {})
                } else if (errorMsg.includes('time series field') || errorMsg.includes('时间序列字段') || errorMsg.includes('date/time data')) {
                  ElMessageBox.alert(
                    t('qa.predict_err_no_time_field') + '\n\n' + t('qa.predict_err_no_time_field_hint'),
                    t('qa.predict_err_no_time_field_title'),
                    {
                      confirmButtonText: t('qa.predict_err_confirm'),
                      type: 'warning'
                    }
                  ).catch(() => {})
                } else if (errorMsg.includes('numeric field') || errorMsg.includes('数值字段') || errorMsg.includes('numeric data')) {
                  ElMessageBox.alert(
                    t('qa.predict_err_no_numeric_field') + '\n\n' + t('qa.predict_err_no_numeric_field_hint'),
                    t('qa.predict_err_no_numeric_field_title'),
                    {
                      confirmButtonText: t('qa.predict_err_confirm'),
                      type: 'warning'
                    }
                  ).catch(() => {})
                } else if (errorMsg.includes('has not generated chart') || errorMsg.includes('未生成图表')) {
                  ElMessageBox.alert(
                    t('qa.predict_err_no_chart'),
                    t('qa.predict_err_no_chart_title'),
                    {
                      confirmButtonText: t('qa.predict_err_confirm'),
                      type: 'info'
                    }
                  ).catch(() => {})
                } else if (errorMsg.includes('no data available') || errorMsg.includes('无数据')) {
                  ElMessageBox.alert(
                    t('qa.predict_err_no_data'),
                    t('qa.predict_err_no_data_title'),
                    {
                      confirmButtonText: t('qa.predict_err_confirm'),
                      type: 'warning'
                    }
                  ).catch(() => {})
                } else {
                  // 通用错误提示
                  ElMessage.error({
                    message: `${t('qa.predict_err_failed')}: ${errorMsg}`,
                    duration: 5000,
                    showClose: true
                  })
                }
                
                emits('error')
                return
              case 'predict-result':
                // 第一次收到预测结果，进入生成阶段
                if (!hasStartedPrediction) {
                  processStage.value = 'generating'
                  processProgress.value = 60
                  processMessage.value = ''
                  hasStartedPrediction = true
                }
                // 实时累积预测思考过程和内容
                if (data.reasoning_content) {
                  predict_answer += data.reasoning_content
                  // predict字段应存储预测报告文本，推理内容存到predict_thinking
                  _currentChat.value.records[index.value].predict_thinking = predict_answer
                  // 同时更新 predict_reasoning_content 字段（用于历史记录）
                  _currentChat.value.records[index.value].predict_reasoning_content = predict_answer
                }
                if (data.content) {
                  predict_content += data.content
                  
                  // 关键修复：实时分离预测数据和预测报告
                  // 第一行是JSON数组格式的预测数据，后续是预测报告
                  const lines = predict_content.split('\n')
                  const firstLine = lines[0].trim()
                  const reportLines = lines.slice(1).join('\n').trim()
                  
                  // predict字段存储预测报告文本（与ChartAnswer内联预测一致）
                  if (reportLines) {
                    _currentChat.value.records[index.value].predict = reportLines
                  }
                  
                  // 保存预测报告（后续行）到 predict_content 字段
                  if (reportLines) {
                    _currentChat.value.records[index.value].predict_content = reportLines
                  }
                  
                  // 根据内容长度动态更新进度
                  const contentProgress = Math.min(30, Math.floor(predict_content.length / 50))
                  processProgress.value = 60 + contentProgress
                }
                break
              case 'predict-failed':
                // predict-failed也需要设置_loading=false并return
                _loading.value = false
                processStage.value = 'done'
                processProgress.value = 0
                if (timeInterval) clearInterval(timeInterval)
                emits('error')
                return
              case 'predict-success':
                // 进入图表生成阶段
                processStage.value = 'chart'
                processProgress.value = 85
                processMessage.value = ''
                
                // 使用 nextTick 确保在获取数据前完成当前的DOM更新
                await nextTick()
                
                // 关键修复：等待数据加载完成后再标记为done
                await getChatPredictData(_currentChat.value.records[index.value].id)
                
                processProgress.value = 100
                processStage.value = 'done'
                emits('finish', currentRecord.id)
                // predict-success 后必须 return 跳出 while 循环，
                return
              case 'layered_recommendations':
                // 接收分层推荐问题（三层推荐系统的mid/post层）
                if (data.data && currentRecord) {
                  currentRecord.layered_recommendations = {
                    mid: data.data.mid || [],
                    post: data.data.post || [],
                  }
                }
                break
              case 'predict_finish':
                _loading.value = false
                processStage.value = 'done'
                processProgress.value = 100
                processMessage.value = ''
                if (timeInterval) clearInterval(timeInterval)
                // predict_finish也需要emit finish，否则父组件不知道预测已完成
                emits('finish', currentRecord.id)
                // predict_finish 后必须 return 跳出 while 循环
                return
            }
            await nextTick()
          }
    }
  } catch (error) {
    if (!currentRecord.error) {
      currentRecord.error = ''
    }
    if (currentRecord.error.trim().length !== 0) {
      currentRecord.error = currentRecord.error + '\n'
    }
    currentRecord.error = currentRecord.error + 'Error:' + error
    processStage.value = 'done'
    processProgress.value = 0
    if (timeInterval) clearInterval(timeInterval)
    emits('error')
  } finally {
    _loading.value = false
    if (processStage.value !== 'done') {
      processStage.value = 'done'
    }
    if (timeInterval) clearInterval(timeInterval)
  }
}

const chartBlockRef = ref()

const loadingData = ref(false)

// 用于取消上一次数据请求，防止快速切换时旧请求覆盖新数据
let predictDataAbortController: AbortController | null = null

async function getChatPredictData(recordId?: number) {
  // 取消上一次未完成的请求
  if (predictDataAbortController) {
    predictDataAbortController.abort()
  }
  predictDataAbortController = new AbortController()
  const currentAbort = predictDataAbortController
  
  loadingData.value = true
  processMessage.value = ''
  
  try {
    const response = await chatApi.get_chart_predict_data(recordId, { signal: currentAbort.signal })
    
    // 防护：检查请求是否已被取消（快速切换场景）
    if (currentAbort.signal.aborted) return
    
    // 直接通过 props.message.record 更新，避免快速切换时 _currentChat 已变导致数据丢失
    if (props.message?.record?.id === recordId) {
      props.message.record.predict_data = response ?? []
    }
    
    let has = false
    
    // 同时尝试更新 _currentChat 中的记录（兼容其他引用）
    _currentChat.value.records.forEach((record, idx) => {
      if (record.id === recordId) {
        has = true
        
        record.predict_data = response ?? []
        
        // 关键修复：如果chart不存在但有predict_record_id，从原始记录加载chart
        if (!record.chart && record.predict_record_id) {
          const baseRecord = _currentChat.value.records.find(r => r.id === record.predict_record_id)
          if (baseRecord && baseRecord.chart) {
            record.chart = baseRecord.chart
          }
        }
        
        // 新增：添加图表生成阶段到thinking_process
        if (!record.thinking_process) {
          record.thinking_process = {
            question: record.question,
            rag_enabled: false,
            stages: {}
          }
        }
        
        record.thinking_process.stages = record.thinking_process.stages || {}
        record.thinking_process.stages.chart_generation = {
          stage: 'chart_generation',
          status: 'completed',
          timestamp: new Date().toISOString(),
          chart_type: 'prediction_trend',
          extra_data: {
            chart_type: t('predict_process.prediction_trend'),
            predict_points: record.predict_data?.length || 0
          }
        }
        
        // 强制触发Vue响应式更新
        record.thinking_process = { ...record.thinking_process }
      }
    })
    
    if (!has) {
      _loading.value = false
      return
    }
    
    // 等待Vue响应式更新
    await nextTick()
    
    // 改为 >= 1，只要有预测数据就获取原始数据
    const record = _currentChat.value.records.find(r => r.id === recordId)
    if (record?.predict_data && record.predict_data.length >= 1) {
      await getChatData(recordId)
    } else {
      loadingData.value = false
    }
  } catch (e) {
    // 被取消的请求不处理
    if (currentAbort.signal.aborted) return
    loadingData.value = false
  }
}

async function getChatData(recordId?: number) {
  loadingData.value = true
  // 复用同一个 AbortController（getChatData 总是在 getChatPredictData 内部调用）
  const currentAbort = predictDataAbortController
  
  try {
    const response = await chatApi.get_chart_data(recordId, currentAbort ? { signal: currentAbort.signal } : undefined)
    
    // 防护：检查请求是否已被取消（快速切换场景）
    if (currentAbort?.signal.aborted) return
    
    // 直接通过 props.message.record 更新，避免快速切换时 _currentChat 已变导致数据丢失
    if (props.message?.record?.id === recordId) {
      props.message.record.data = response
    }
    
    // 同时尝试更新 _currentChat 中的记录（兼容其他引用）
    _currentChat.value.records.forEach((record, idx) => {
      if (record.id === recordId) {
        record.data = response
        
        // 在原始数据加载完成后，确保chart_generation阶段已添加
        if (!record.thinking_process) {
          record.thinking_process = {
            question: record.question,
            rag_enabled: false,
            stages: {}
          }
        }
        
        record.thinking_process.stages = record.thinking_process.stages || {}
        if (!record.thinking_process.stages.chart_generation) {
          record.thinking_process.stages.chart_generation = {
            stage: 'chart_generation',
            status: 'completed',
            timestamp: new Date().toISOString(),
            chart_type: 'prediction_trend',
            extra_data: {
              chart_type: t('predict_process.prediction_trend'),
              predict_points: record.predict_data?.length || 0
            }
          }
          // 强制触发响应式更新
          record.thinking_process = { ...record.thinking_process }
        }
      }
    })
    
    // 等待Vue响应式更新完成
    await nextTick()
    
    // 强制触发一次滚动，确保视图更新
    await nextTick()
    
    emits('scrollBottom')
  } finally {
    loadingData.value = false
    emits('scrollBottom')
  }
}

function stop() {
  stopFlag.value = true
  _loading.value = false
  processStage.value = 'done'
  processProgress.value = 0
  if (timeInterval) clearInterval(timeInterval)
  emits('stop')
}

onBeforeUnmount(() => {
  // 组件卸载时取消未完成的数据请求，防止更新已销毁的组件
  if (predictDataAbortController) {
    predictDataAbortController.abort()
    predictDataAbortController = null
  }
  stop()
  if (timeInterval) clearInterval(timeInterval)
})

onMounted(() => {
  // 仅在数据尚未加载时获取预测数据，避免重复请求
  if (props.message?.record?.id && props.message?.record?.finish && !props.message?.record?.predict_data) {
    getChatPredictData(props.message.record.id)
  }
  
  // 加载历史RAG检索结果并同步到thinking_process（对齐ChartAnswer.vue）
  // 确保历史记录的思考面板能正确展示RAG检索阶段
  if (props.message?.record?.rag_results) {
    try {
      const parsedRagResults = typeof props.message.record.rag_results === 'string'
        ? JSON.parse(props.message.record.rag_results)
        : props.message.record.rag_results

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
        const histRagEnabledP = parsedRagResults.rag_enabled !== false
        currentRecord.thinking_process.stages.rag_retrieval = {
          stage: 'rag_retrieval',
          status: histRagEnabledP ? 'completed' : 'skipped',
          timestamp: new Date().toISOString(),
          rag_enabled: histRagEnabledP,
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

  // 加载历史分层推荐问题（对齐ChartAnswer.vue）
  // PredictAnswer 独立流也会收到 layered_recommendations SSE 事件，
  // 但页面刷新后 record.layered_recommendations 来自 format_record 提取的 thinking_process
  if (props.message?.record?.layered_recommendations) {
    // format_record 已从 thinking_process 提取，直接使用
  } else if (props.message?.record?.thinking_process?.stages) {
    // 兜底：从 thinking_process 手动恢复
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
        props.message.record.layered_recommendations = lr
      }
    }
  }

  // 后端 Fix 32 将 prediction_confidence 持久化到 thinking_process.stages.data_prediction
  // SSE 流式接收时存到 confidenceData ref，但刷新后该 ref 为 null
  if (!confidenceData.value && props.message?.record) {
    const tp = props.message.record.thinking_process
    const predStage = tp?.stages?.data_prediction
    if (predStage?.prediction_confidence) {
      confidenceData.value = predStage.prediction_confidence as PredictionConfidence
    }
  }
})

defineExpose({ sendMessage, index: () => index.value, chatList: () => _chatList.value, stop })

</script>

<template>
  <BaseAnswer v-if="message" :message="message" :reasoning-name="['predict']" :loading="_loading" :show-rag-step="true" :scenario-type="'predict'" :process-stage="baseAnswerProcessStage" :hide-citation="false">
    <!-- 数据预测处理过程指示器 - 增强版 -->
    <div v-if="message.isTyping" class="predict-progress-container">
      <PredictProcessIndicator :stage="processStage" />
      
      <!-- 实时进度条 -->
      <div class="progress-bar-wrapper">
        <div class="progress-info">
          <span class="progress-message">{{ processMessage || $t('predict_process.processing') }}</span>
          <span class="progress-time">{{ elapsedTime }}s</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: processProgress + '%' }">
            <div class="progress-shimmer"></div>
          </div>
        </div>
        <div class="progress-percentage">{{ processProgress }}%</div>
      </div>
    </div>

    <!-- 预测内容为空时显示提示（仅在完成后且无内容时显示） -->
    <div
      v-if="
        !message.isTyping &&
        message.record?.finish &&
        (!message.record?.predict_content || message.record.predict_content.trim() === '') &&
        !shouldShowChart
      "
      class="empty-result"
    >
      <span class="empty-icon">🔮</span>
      <span class="empty-text">{{ $t('qa.no_predict_result') }}</span>
    </div>

    <!-- 置信度评分卡片 -->
    <div v-if="confidenceData" class="confidence-card" :style="{ background: confidenceLevelBg, borderColor: confidenceLevelBorder }">
      <div class="confidence-header">
        <div class="confidence-main-info">
          <!-- 置信度圆形进度 -->
          <div class="confidence-circle">
            <svg viewBox="0 0 60 60" class="circle-svg">
              <circle cx="30" cy="30" r="26" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="5" />
              <circle
                cx="30" cy="30" r="26"
                fill="none"
                :stroke="confidenceLevelColor"
                stroke-width="5"
                stroke-linecap="round"
                :stroke-dasharray="2 * Math.PI * 26"
                :stroke-dashoffset="2 * Math.PI * 26 * (1 - confidenceData.score / 100)"
                transform="rotate(-90 30 30)"
                class="circle-progress"
              />
            </svg>
            <span class="circle-text" :style="{ color: confidenceLevelColor }">{{ confidenceData.score }}</span>
          </div>
          <!-- 置信度等级标签 + 描述 -->
          <div class="confidence-label-area">
            <div class="confidence-level-row">
              <span class="confidence-level-tag" :style="{ background: confidenceLevelColor + '22', color: confidenceLevelColor, borderColor: confidenceLevelColor + '44' }">
                {{ confidenceData.level === '高' ? '🟢' : confidenceData.level === '中' ? '🟠' : '🔴' }}
                {{ t('predict_confidence.label') }}：{{ confidenceData.level === '高' ? t('predict_confidence.level_high') : confidenceData.level === '中' ? t('predict_confidence.level_medium') : t('predict_confidence.level_low') }}
              </span>
              <span class="confidence-score-text">{{ confidenceData.score }}{{ t('predict_confidence.score_suffix') }}</span>
            </div>
            <!-- 预测区间 -->
            <div v-if="confidenceData.prediction_interval.lower !== null && confidenceData.prediction_interval.upper !== null" class="confidence-interval">
              {{ t('predict_confidence.prediction_interval') }}：{{ confidenceData.prediction_interval.lower }} ~ {{ confidenceData.prediction_interval.upper }}
            </div>
          </div>
        </div>
        <!-- 展开/收起因子详情按钮 -->
        <button class="confidence-toggle-btn" @click="showFactorDetails = !showFactorDetails">
          <span>{{ showFactorDetails ? t('predict_confidence.collapse_details') : t('predict_confidence.factor_analysis') }}</span>
          <svg :class="{ 'rotated': showFactorDetails }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>
      </div>

      <!-- 低置信度警告 -->
      <div v-if="confidenceData.level === '低'" class="confidence-warning">
        <span class="warning-icon">⚠️</span>
        <span>{{ t('predict_confidence.low_warning') }}</span>
      </div>

      <!-- 可展开的因子详情 -->
      <transition name="factor-expand">
        <div v-if="showFactorDetails" class="confidence-factors">
          <div class="factor-item">
            <div class="factor-label">
              <span class="factor-icon">🔢</span>
              <span>{{ t('predict_confidence.factor_data_volume') }}</span>
            </div>
            <div class="factor-bar-wrapper">
              <div class="factor-bar">
                <div class="factor-bar-fill" :style="{ width: confidenceData.factors.data_volume + '%', background: getFactorColor(confidenceData.factors.data_volume) }"></div>
              </div>
              <span class="factor-score">{{ confidenceData.factors.data_volume }}</span>
            </div>
          </div>
          <div class="factor-item">
            <div class="factor-label">
              <span class="factor-icon">📅</span>
              <span>{{ t('predict_confidence.factor_time_span') }}</span>
            </div>
            <div class="factor-bar-wrapper">
              <div class="factor-bar">
                <div class="factor-bar-fill" :style="{ width: confidenceData.factors.time_span + '%', background: getFactorColor(confidenceData.factors.time_span) }"></div>
              </div>
              <span class="factor-score">{{ confidenceData.factors.time_span }}</span>
            </div>
          </div>
          <div class="factor-item">
            <div class="factor-label">
              <span class="factor-icon">📈</span>
              <span>{{ t('predict_confidence.factor_trend_stability') }}</span>
            </div>
            <div class="factor-bar-wrapper">
              <div class="factor-bar">
                <div class="factor-bar-fill" :style="{ width: confidenceData.factors.trend_stability + '%', background: getFactorColor(confidenceData.factors.trend_stability) }"></div>
              </div>
              <span class="factor-score">{{ confidenceData.factors.trend_stability }}</span>
            </div>
          </div>
          <div class="factor-item">
            <div class="factor-label">
              <span class="factor-icon">✅</span>
              <span>{{ t('predict_confidence.factor_data_completeness') }}</span>
            </div>
            <div class="factor-bar-wrapper">
              <div class="factor-bar">
                <div class="factor-bar-fill" :style="{ width: confidenceData.factors.data_completeness + '%', background: getFactorColor(confidenceData.factors.data_completeness) }"></div>
              </div>
              <span class="factor-score">{{ confidenceData.factors.data_completeness }}</span>
            </div>
          </div>
        </div>
      </transition>
    </div>
    
    <!--  图表在上面 - 移除chartKey，让ChartBlock的watch自然响应数据变化 -->
    <ChartBlock
      v-if="shouldShowChart"
      ref="chartBlockRef"
      style="margin-top: 12px"
      :record-id="recordId"
      :message="message"
      :loading-data="loadingData"
      is-predict
    />
    
    <!--  预测报告在图表下面（markdown格式） -->
    <MdComponent 
      v-if="message.record?.predict_content && message.record.predict_content.trim()" 
      :message="message.record?.predict_content" 
      style="margin-top: 12px" 
    />
    
    <slot></slot>
    <template #tool>
      <slot name="tool"></slot>
    </template>
    <template #footer>
      <slot name="footer"></slot>
    </template>
  </BaseAnswer>
</template>

<style scoped lang="less">
@import '@/styles/chat-components.less';

.predict-progress-container {
  margin-top: 14px;
  animation: chatFadeIn 0.3s ease;
}

.progress-bar-wrapper {
  margin-top: 16px;
  padding: 16px 20px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.06) 0%, rgba(5, 150, 105, 0.04) 100%);
  border: 1px solid rgba(16, 185, 129, 0.15);
  border-radius: 12px;
  backdrop-filter: blur(10px);

  .progress-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;

    .progress-message {
      font-size: 13px;
      font-weight: 500;
      color: @chat-dark-text;
      opacity: 0.85;
    }

    .progress-time {
      font-size: 12px;
      font-weight: 600;
      color: rgba(16, 185, 129, 0.8);
      font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
    }
  }

  .progress-bar {
    position: relative;
    height: 8px;
    background: rgba(16, 185, 129, 0.12);
    border-radius: 10px;
    overflow: hidden;
    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);

    .progress-fill {
      height: 100%;
      background: linear-gradient(90deg, 
        rgba(16, 185, 129, 0.9) 0%, 
        rgba(5, 150, 105, 0.95) 50%,
        rgba(16, 185, 129, 0.9) 100%
      );
      border-radius: 10px;
      transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
      overflow: hidden;
      box-shadow: 0 0 10px rgba(16, 185, 129, 0.4);

      .progress-shimmer {
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, 
          transparent 0%, 
          rgba(255, 255, 255, 0.3) 50%, 
          transparent 100%
        );
        animation: shimmer 2s infinite;
      }
    }
  }

  .progress-percentage {
    margin-top: 8px;
    text-align: right;
    font-size: 11px;
    font-weight: 700;
    color: rgba(16, 185, 129, 0.75);
    font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  }
}

@keyframes shimmer {
  0% {
    left: -100%;
  }
  100% {
    left: 100%;
  }
}

.empty-result {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 22px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.08) 0%, rgba(168, 85, 247, 0.05) 100%);
  border: 1px dashed rgba(139, 92, 246, 0.22);
  border-radius: 12px;
  margin-top: 14px;
  animation: chatFadeIn 0.3s ease;

  .empty-icon {
    font-size: 22px;
    opacity: 0.75;
    filter: drop-shadow(0 2px 4px rgba(139, 92, 246, 0.2));
  }

  .empty-text {
    font-size: 14px;
    color: @chat-dark-text-muted;
    font-weight: 500;
  }
}

@media (max-width: 768px) {
  .empty-result {
    padding: 14px 18px;
    gap: 10px;
    border-radius: 10px;

    .empty-icon {
      font-size: 20px;
    }
    .empty-text {
      font-size: 13px;
    }
  }
}

@media (max-width: 480px) {
  .empty-result {
    padding: 12px 14px;
    gap: 8px;
    border-radius: 8px;

    .empty-icon {
      font-size: 18px;
    }
    .empty-text {
      font-size: 12px;
    }
  }
}

// ============================================
// 置信度评分卡片样式
// ============================================
.confidence-card {
  margin-top: 14px;
  padding: 16px 20px;
  border: 1px solid;
  border-radius: 12px;
  backdrop-filter: blur(10px);
  animation: chatFadeIn 0.3s ease;

  .confidence-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;

    .confidence-main-info {
      display: flex;
      align-items: center;
      gap: 14px;
      flex: 1;
      min-width: 0;
    }
  }

  .confidence-circle {
    position: relative;
    width: 52px;
    height: 52px;
    flex-shrink: 0;

    .circle-svg {
      width: 100%;
      height: 100%;
    }

    .circle-progress {
      transition: stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .circle-text {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 14px;
      font-weight: 700;
      font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
    }
  }

  .confidence-label-area {
    flex: 1;
    min-width: 0;

    .confidence-level-row {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .confidence-level-tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 10px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 600;
      border: 1px solid;
      white-space: nowrap;
    }

    .confidence-score-text {
      font-size: 12px;
      color: @chat-dark-text-muted;
      font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
    }

    .confidence-interval {
      margin-top: 6px;
      font-size: 12px;
      color: @chat-dark-text-secondary;
      opacity: 0.85;
    }
  }

  .confidence-toggle-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 5px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 500;
    color: @chat-dark-text-secondary;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
    flex-shrink: 0;

    &:hover {
      background: rgba(255, 255, 255, 0.1);
      border-color: rgba(255, 255, 255, 0.18);
    }

    svg {
      transition: transform 0.25s ease;
      &.rotated {
        transform: rotate(180deg);
      }
    }
  }

  .confidence-warning {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 12px;
    padding: 10px 14px;
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.18);
    border-radius: 8px;
    font-size: 13px;
    color: #fca5a5;
    line-height: 1.5;

    .warning-icon {
      flex-shrink: 0;
      font-size: 15px;
    }
  }

  .confidence-factors {
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    display: flex;
    flex-direction: column;
    gap: 10px;

    .factor-item {
      display: flex;
      align-items: center;
      gap: 12px;

      .factor-label {
        display: flex;
        align-items: center;
        gap: 6px;
        width: 100px;
        flex-shrink: 0;
        font-size: 12px;
        color: @chat-dark-text-secondary;

        .factor-icon {
          font-size: 13px;
        }
      }

      .factor-bar-wrapper {
        flex: 1;
        display: flex;
        align-items: center;
        gap: 8px;

        .factor-bar {
          flex: 1;
          height: 6px;
          background: rgba(255, 255, 255, 0.06);
          border-radius: 3px;
          overflow: hidden;

          .factor-bar-fill {
            height: 100%;
            border-radius: 3px;
            transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
          }
        }

        .factor-score {
          width: 30px;
          text-align: right;
          font-size: 11px;
          font-weight: 600;
          color: @chat-dark-text-muted;
          font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
        }
      }
    }
  }
}

// 因子展开/收起动画
.factor-expand-enter-active {
  animation: factorSlideDown 0.25s ease;
}
.factor-expand-leave-active {
  animation: factorSlideDown 0.2s ease reverse;
}
@keyframes factorSlideDown {
  from {
    opacity: 0;
    max-height: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    max-height: 200px;
    transform: translateY(0);
  }
}

// 响应式适配
@media (max-width: 768px) {
  .confidence-card {
    padding: 14px 16px;

    .confidence-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 10px;
    }

    .confidence-circle {
      width: 44px;
      height: 44px;

      .circle-text {
        font-size: 12px;
      }
    }

    .confidence-toggle-btn {
      align-self: flex-end;
    }

    .confidence-factors .factor-item {
      .factor-label {
        width: 80px;
        font-size: 11px;
      }
    }
  }
}

@media (max-width: 480px) {
  .confidence-card {
    padding: 12px 14px;
    border-radius: 10px;

    .confidence-circle {
      width: 40px;
      height: 40px;

      .circle-text {
        font-size: 11px;
      }
    }

    .confidence-label-area .confidence-level-tag {
      font-size: 12px;
      padding: 2px 8px;
    }
  }
}
</style>
