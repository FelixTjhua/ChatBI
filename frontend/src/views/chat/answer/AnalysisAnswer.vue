<script setup lang="ts">
import BaseAnswer from './BaseAnswer.vue'
import { chatApi, ChatInfo, type ChatMessage, ChatRecord } from '@/api/chat.ts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import MdComponent from '@/views/chat/component/MdComponent.vue'
import ChartBlock from '@/views/chat/chat-block/ChartBlock.vue'
import AnalysisProcessIndicator from '@/views/chat/AnalysisProcessIndicator.vue'

const props = withDefaults(
  defineProps<{
    chatList?: Array<ChatInfo>
    currentChatId?: number
    currentChat?: ChatInfo
    message?: ChatMessage
    loading?: boolean
  }>(),
  {
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

// 分析处理阶段 - 更细粒度的状态追踪
// 新增 'augment' 阶段，对应上下文压缩与提示词注入
const processStage = ref<'idle' | 'query' | 'rag' | 'augment' | 'loading' | 'analyzing' | 'generating' | 'chart' | 'done'>('idle')

// 映射内部阶段到 BaseAnswer 的 processStage 格式（驱动思考面板进度条）
const baseAnswerProcessStage = computed<'idle' | 'query' | 'rag' | 'analysis' | 'done'>(() => {
  const s = processStage.value
  if (s === 'idle') return 'idle'
  if (s === 'done') return 'done'
  if (s === 'query') return 'query'
  if (s === 'rag') return 'rag'
  // loading/analyzing/generating/chart 都属于"分析中"
  return 'analysis'
})
const processProgress = ref(0) // 进度百分比 0-100
const processMessage = ref('') // 当前处理消息
const startTime = ref(0) // 开始时间
const elapsedTime = ref(0) // 已用时间（秒）

// 图表相关
const chartBlockRef = ref()
const loadingData = ref(false)

// 新增：响应式的图表显示条件 - 分析场景需要从原始记录获取图表
const shouldShowChart = computed(() => {
  const record = props.message?.record
  if (!record) return false
  
  // 分析场景：需要有 chart 和 data
  const hasChart = !!record.chart
  const hasData = !!record.data
  
  return hasChart && hasData
})

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
  if (_currentChatId.value === undefined || currentRecord.analysis_record_id === undefined) {
    error = true
  }
  if (error) {
    _loading.value = false
    processStage.value = 'idle'
    if (timeInterval) clearInterval(timeInterval)
    return
  }

  // UX优化：提前加载图表数据（不等分析完成），让图表先于分析报告展示
  // 分析场景的图表数据来自原始SQL查询记录（analysis_record_id），可以立即加载
  getChatData(currentRecord.id).catch(() => {})

  try {
    const controller: AbortController = new AbortController()
    // RAG 永远开启，不需要参数（对齐 SQLBot）
    const response = await chatApi.analysis(currentRecord.analysis_record_id, controller)
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')

    let analysis_answer = ''
    let analysis_answer_thinking = ''

    let tempResult = ''
    let hasStartedAnalysis = false

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
                if (data.type === 'analysis_finish') {
                  // 残留的 analysis_finish 事件，正常处理
                  processStage.value = 'chart'
                  processProgress.value = 90
                } else if (data.type === 'analysis-result') {
                  if (data.content) {
                    analysis_answer += data.content
                    _currentChat.value.records[index.value].analysis = analysis_answer
                  }
                  if (data.reasoning_content) {
                    analysis_answer_thinking += data.reasoning_content
                    _currentChat.value.records[index.value].analysis_thinking = analysis_answer_thinking
                    _currentChat.value.records[index.value].analysis_reasoning_content = analysis_answer_thinking
                  }
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
        // 流结束时也需要 emit finish，否则父组件不知道分析已完成
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
                // 接收 RAG 检索结果（分析场景的术语/文档检索）
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
                  const ragEnabledA = data.data.rag_enabled !== false
                  // 保留已有的 rag_retrieval 嵌套数据（表检索信息来自 thinking_stage 事件）
                  const existingRagStageA = currentRecord.thinking_process.stages.rag_retrieval || {}
                  currentRecord.thinking_process.stages.rag_retrieval = {
                    ...existingRagStageA,
                    stage: 'rag_retrieval',
                    status: ragEnabledA ? 'completed' : 'skipped',
                    timestamp: new Date().toISOString(),
                    rag_enabled: ragEnabledA,
                    terminologies: data.data.terminologies || existingRagStageA.terminologies || [],
                    sql_examples: data.data.sql_examples || existingRagStageA.sql_examples || [],
                    custom_prompts: data.data.custom_prompts || existingRagStageA.custom_prompts || [],
                    terminology_quality: data.data.terminology_quality || existingRagStageA.terminology_quality || {},
                    example_quality: data.data.example_quality || existingRagStageA.example_quality || {},
                    rag_impact: data.data.rag_impact || existingRagStageA.rag_impact || {}
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
                  // RAG检索完成后进入上下文增强阶段（而非直接跳到分析）
                  processStage.value = 'augment'
                  processProgress.value = 20
                  processMessage.value = ''
                } else if (data.stage === 'context_compression' || data.stage === 'prompt_construction') {
                  // 上下文压缩和提示词构建都属于增强阶段
                  processStage.value = 'augment'
                  processProgress.value = 35
                } else if (data.stage === 'data_analysis') {
                  processStage.value = 'generating'
                  processProgress.value = 50
                }
                break
              case 'error':
                currentRecord.error = data.content || data.msg || 'Unknown error'
                // error事件必须设置_loading=false，否则后端不关闭连接时客户端卡在loading状态
                _loading.value = false
                processStage.value = 'done'
                processProgress.value = 0
                if (timeInterval) clearInterval(timeInterval)
                emits('error')
                return
              case 'analysis-result':
                // 第一次收到分析结果，进入生成阶段
                if (!hasStartedAnalysis) {
                  processStage.value = 'generating'
                  processProgress.value = 60
                  processMessage.value = ''
                  hasStartedAnalysis = true
                }
                // 实时累积分析内容和思考过程
                if (data.content) {
                  analysis_answer += data.content
                  _currentChat.value.records[index.value].analysis = analysis_answer
                  // 根据内容长度动态更新进度
                  const contentProgress = Math.min(30, Math.floor(analysis_answer.length / 50))
                  processProgress.value = 60 + contentProgress
                }
                if (data.reasoning_content) {
                  analysis_answer_thinking += data.reasoning_content
                  _currentChat.value.records[index.value].analysis_thinking = analysis_answer_thinking
                  // 同时更新 analysis_reasoning_content 字段（用于历史记录）
                  _currentChat.value.records[index.value].analysis_reasoning_content = analysis_answer_thinking
                }
                break
              case 'layered_recommendations':
                // 接收分层推荐问题（三层推荐系统的mid/post层）
                if (data.data && currentRecord) {
                  currentRecord.layered_recommendations = {
                    mid: data.data.mid || [],
                    post: data.data.post || [],
                  }
                }
                break
              case 'analysis_finish':
                // 添加遗漏的 _loading.value = false
                // 对比 PredictAnswer.vue 的 predict_finish，此处遗漏了设置 loading 为 false
                _loading.value = false
                processStage.value = 'done'
                processProgress.value = 100
                processMessage.value = ''
                if (timeInterval) clearInterval(timeInterval)
                
                emits('finish', currentRecord.id)
                // analysis_finish 后必须 return 跳出 while 循环，
                // 或返回 done=true 触发重复的 finish 逻辑
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
function stop() {
  stopFlag.value = true
  _loading.value = false
  processStage.value = 'done'
  processProgress.value = 0
  if (timeInterval) clearInterval(timeInterval)
  emits('stop')
}

// 用于取消上一次 getChatData 请求，防止快速切换时旧请求覆盖新数据
let getChatDataAbortController: AbortController | null = null

// 新增：获取图表数据（从原始记录 analysis_record_id 获取）
async function getChatData(recordId?: number) {
  // 取消上一次未完成的请求
  if (getChatDataAbortController) {
    getChatDataAbortController.abort()
  }
  getChatDataAbortController = new AbortController()
  const currentAbort = getChatDataAbortController
  
  loadingData.value = true
  
  try {
    // 分析场景：从 analysis_record_id 指向的原始记录获取数据
    const currentRecord = _currentChat.value.records.find(r => r.id === recordId)
    const baseRecordId = currentRecord?.analysis_record_id || recordId
    
    const response = await chatApi.get_chart_data(baseRecordId, { signal: currentAbort.signal })
    
    // 防护：检查请求是否已被取消（快速切换场景）
    if (currentAbort.signal.aborted) return
    
    // 直接通过 props.message.record 更新数据，避免快速切换时 _currentChat 已变导致数据丢失
    if (props.message?.record?.id === recordId) {
      props.message.record.data = response
    }
    
    // 同时尝试更新 _currentChat 中的记录（兼容其他引用）
    _currentChat.value.records.forEach((record) => {
      if (record.id === recordId) {
        // 更新数据
        record.data = response
        
        // 如果 chart 不存在，从原始记录加载
        if (!record.chart && record.analysis_record_id) {
          const baseRecord = _currentChat.value.records.find(r => r.id === record.analysis_record_id)
          if (baseRecord && baseRecord.chart) {
            record.chart = baseRecord.chart
          }
        }
        
        // 添加图表生成阶段到 thinking_process
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
          chart_type: 'analysis_chart',
          extra_data: {
            chart_type: 'analysis_chart'
          }
        }
        record.thinking_process = { ...record.thinking_process }
      }
    })
    
    await nextTick()
    emits('scrollBottom')
  } finally {
    if (!currentAbort.signal.aborted) {
      loadingData.value = false
    }
    emits('scrollBottom')
  }
}

onBeforeUnmount(() => {
  // 组件卸载时取消未完成的数据请求，防止更新已销毁的组件
  if (getChatDataAbortController) {
    getChatDataAbortController.abort()
    getChatDataAbortController = null
  }
  stop()
  if (timeInterval) clearInterval(timeInterval)
})

onMounted(() => {
  // 加载历史记录时获取图表数据（仅在数据尚未加载时）
  if (props.message?.record?.id && props.message?.record?.finish && !props.message?.record?.data) {
    getChatData(props.message.record.id)
  }
  
  // 加载历史分层推荐问题（对齐ChartAnswer.vue）
  // AnalysisAnswer 独立流也会收到 layered_recommendations SSE 事件，
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
        const histRagEnabledA = parsedRagResults.rag_enabled !== false
        currentRecord.thinking_process.stages.rag_retrieval = {
          stage: 'rag_retrieval',
          status: histRagEnabledA ? 'completed' : 'skipped',
          timestamp: new Date().toISOString(),
          rag_enabled: histRagEnabledA,
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

defineExpose({ sendMessage, index: () => index.value, chatList: () => _chatList.value, stop })
</script>

<template>
  <BaseAnswer
    v-if="message"
    :message="message"
    :reasoning-name="['analysis_thinking']"
    :loading="_loading"
    :show-rag-step="true"
    :scenario-type="'analysis'"
    :process-stage="baseAnswerProcessStage"
    :hide-citation="false"
  >
    <!-- 数据分析处理过程指示器 - 增强版 -->
    <div v-if="message.isTyping" class="analysis-progress-container">
      <AnalysisProcessIndicator :stage="processStage" />
      
      <!-- 实时进度条 -->
      <div class="progress-bar-wrapper">
        <div class="progress-info">
          <span class="progress-message">{{ processMessage || $t('analysis_process.processing') }}</span>
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

    <!-- 分析结果为空时显示提示（仅在完成后且无内容时显示） -->
    <div
      v-if="
        !message.isTyping &&
        message.record?.finish &&
        (!message.record?.analysis || message.record.analysis.trim() === '') &&
        !shouldShowChart
      "
      class="empty-result"
    >
      <span class="empty-icon">📈</span>
      <span class="empty-text">{{ $t('qa.no_analysis_result') }}</span>
    </div>
    
    <!--  新增：图表展示（在分析报告上方） -->
    <ChartBlock
      v-if="shouldShowChart"
      ref="chartBlockRef"
      style="margin-top: 12px"
      :message="message"
      :loading-data="loadingData"
    />
    
    <!-- 分析报告（markdown格式） -->
    <MdComponent v-if="message.record?.analysis" :message="message.record?.analysis" style="margin-top: 12px" />
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

.analysis-progress-container {
  margin-top: 14px;
  animation: chatFadeIn 0.3s ease;
}

.progress-bar-wrapper {
  margin-top: 16px;
  padding: 16px 20px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.06) 0%, rgba(168, 85, 247, 0.04) 100%);
  border: 1px solid rgba(139, 92, 246, 0.15);
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
      color: rgba(139, 92, 246, 0.8);
      font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
    }
  }

  .progress-bar {
    position: relative;
    height: 8px;
    background: rgba(139, 92, 246, 0.12);
    border-radius: 10px;
    overflow: hidden;
    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);

    .progress-fill {
      height: 100%;
      background: linear-gradient(90deg, 
        rgba(139, 92, 246, 0.9) 0%, 
        rgba(168, 85, 247, 0.95) 50%,
        rgba(139, 92, 246, 0.9) 100%
      );
      border-radius: 10px;
      transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
      overflow: hidden;
      box-shadow: 0 0 10px rgba(139, 92, 246, 0.4);

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
    color: rgba(139, 92, 246, 0.75);
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
</style>
