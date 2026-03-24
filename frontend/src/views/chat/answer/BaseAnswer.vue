<script setup lang="ts">
import { type ChatMessage } from '@/api/chat.ts'
import { computed, ref, watch } from 'vue'
import MdComponent from '@/views/chat/component/MdComponent.vue'
import icon_up_outlined from '@/assets/svg/icon_up_outlined.svg'
import icon_down_outlined from '@/assets/svg/icon_down_outlined.svg'
import { useI18n } from 'vue-i18n'
import QueryUnderstandingDisplay from '@/views/chat/thinking/QueryUnderstandingDisplay.vue'
import PromptConstructionDisplay from '@/views/chat/thinking/PromptConstructionDisplay.vue'

/**
 * 归一化思考阶段数据：兼容新格式（extra_data 嵌套）和旧格式（extra_data 展平到顶层）
 *
 * 新格式（后端重构后）：{ stage, status, duration, extra_data: { field1, field2, ... } }
 * 旧格式（数据库历史数据）：{ stage, status, duration, field1, field2, ... }
 *
 * 归一化后统一为：{ stage, status, duration, extra_data: { field1, field2, ... }, field1, field2, ... }
 * 这样 stage.extra_data.field 和 stage.field 都能访问到数据。
 */
function normalizeStage(raw: any): any {
  if (!raw) return null
  // 新格式：extra_data 是对象且有内容 → 将 extra_data 字段也展开到顶层（方便模板直接访问）
  if (raw.extra_data && typeof raw.extra_data === 'object' && Object.keys(raw.extra_data).length > 0) {
    return { ...raw, ...raw.extra_data }
  }
  // 旧格式：没有 extra_data 或 extra_data 为空 → 从顶层字段重建 extra_data
  const meta = new Set(['stage', 'name', 'status', 'duration', 'rag_retrieval', 'llm_generation', 'execution', 'extra_data'])
  const extra: Record<string, any> = {}
  for (const [k, v] of Object.entries(raw)) {
    if (!meta.has(k)) extra[k] = v
  }
  return { ...raw, extra_data: Object.keys(extra).length > 0 ? extra : (raw.extra_data || {}) }
}

const props = withDefaults(
  defineProps<{
    message: ChatMessage
    loading?: boolean
    reasoningName:
      | 'sql_answer'
      | 'chart_answer'
      | 'analysis_thinking'
      | 'predict'
      | Array<'sql_answer' | 'chart_answer' | 'analysis_thinking' | 'predict'>
    ragResults?: {
      terminologies: any[]
      sql_examples: any[]
      analysis_examples?: any[]
      predict_examples?: any[]
      custom_prompts?: any[]
    } | null
    showRagStep?: boolean
    scenarioType?: 'sql' | 'analysis' | 'predict' | 'general_chat' | 'sql_analysis' | 'sql_prediction'
    processStage?: 'idle' | 'query' | 'rag' | 'sql' | 'execute' | 'chart' | 'direct' | 'analysis' | 'predict' | 'done'
    hideCitation?: boolean
    deferredAnalysisLoading?: boolean
    deferredPredictLoading?: boolean
  }>(),
  {
    loading: false,
    ragResults: null,
    showRagStep: true,
    scenarioType: 'sql',
    processStage: 'idle',
    hideCitation: false,
    deferredAnalysisLoading: false,
    deferredPredictLoading: false,
  }
)

const { t } = useI18n()
const show = ref<boolean>(false)

const expandedSteps = ref<Record<string, boolean>>({})
function toggleStep(key: string) { expandedSteps.value[key] = !expandedSteps.value[key] }
function isExpanded(key: string) { return expandedSteps.value[key] ?? false }

// RAG 检索结果
const effectiveRagResults = computed(() => {
  if (props.ragResults) return props.ragResults
  if (props.message?.record?.rag_results) {
    try {
      if (typeof props.message.record.rag_results === 'string') return JSON.parse(props.message.record.rag_results)
      return props.message.record.rag_results
    } catch (e) { return null }
  }
  return null
})

// 思考过程数据
const thinkingProcess = computed(() => {
  if (props.message?.record?.thinking_process) {
    try {
      if (typeof props.message.record.thinking_process === 'string') return JSON.parse(props.message.record.thinking_process)
      return props.message.record.thinking_process
    } catch (e) { return null }
  }
  return null
})

// 提取各阶段
const ragStage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) return normalizeStage(stages.find(s => s.name === 'rag_retrieval' || s.stage === 'rag_retrieval'))
  return stages.rag_retrieval ? normalizeStage({ name: 'rag_retrieval', ...stages.rag_retrieval }) : null
})

const sqlStage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) {
    const found = stages.find(s => s.name === 'sql_generation' || s.stage === 'sql_generation')
    return found && found.status === 'completed' ? normalizeStage(found) : null
  }
  const s = stages.sql_generation
  return s && s.status === 'completed' ? normalizeStage({ name: 'sql_generation', ...s }) : null
})

const executionStage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) {
    const found = stages.find(s => s.name === 'sql_execution' || s.stage === 'sql_execution')
    return found && found.status === 'completed' ? normalizeStage(found) : null
  }
  const s = stages.sql_execution
  return s && s.status === 'completed' ? normalizeStage({ name: 'sql_execution', ...s }) : null
})

const chartStage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) {
    const found = stages.find(s => s.name === 'chart_generation' || s.stage === 'chart_generation')
    return found && found.status === 'completed' ? normalizeStage(found) : null
  }
  const s = stages.chart_generation
  return s && s.status === 'completed' ? normalizeStage({ name: 'chart_generation', ...s }) : null
})

const analysisStage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) {
    const found = stages.find(s => s.name === 'data_analysis' || s.stage === 'data_analysis')
    return found && found.status === 'completed' ? normalizeStage(found) : null
  }
  const s = stages.data_analysis
  return s && s.status === 'completed' ? normalizeStage({ name: 'data_analysis', ...s }) : null
})

const predictStage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) {
    const found = stages.find(s => s.name === 'data_prediction' || s.stage === 'data_prediction')
    return found && found.status === 'completed' ? normalizeStage(found) : null
  }
  const s = stages.data_prediction
  if (s && s.status === 'completed') return normalizeStage({ name: 'data_prediction', ...s })
  if (props.scenarioType === 'sql_prediction') {
    const fallback = stages.data_analysis
    if (fallback && fallback.status === 'completed') return normalizeStage({ name: 'data_prediction', ...fallback })
  }
  return null
})

const currentLLMStage = computed(() => {
  if (props.scenarioType === 'analysis') return analysisStage.value
  if (props.scenarioType === 'predict') return predictStage.value
  if (props.scenarioType === 'sql_analysis' || props.scenarioType === 'sql_prediction') return sqlStage.value
  if (props.scenarioType === 'general_chat') {
    if (!thinkingProcess.value?.stages) return null
    const stages = thinkingProcess.value.stages
    if (Array.isArray(stages)) return normalizeStage(stages.find((s: any) => s.name === 'direct_answer' || s.stage === 'direct_answer') || null)
    return stages.direct_answer ? normalizeStage({ name: 'direct_answer', ...stages.direct_answer }) : null
  }
  return sqlStage.value
})

const isLLMStageLoading = computed(() => {
  if (!thinkingProcess.value?.stages) return false
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) return false
  if (props.scenarioType === 'analysis') return stages.data_analysis?.status === 'loading'
  if (props.scenarioType === 'predict') return stages.data_prediction?.status === 'loading'
  return stages.sql_generation?.status === 'loading'
})

const streamingReasoning = computed(() => {
  if (!thinkingProcess.value?.stages) return ''
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) return ''
  let streaming = ''
  if (props.scenarioType === 'analysis') streaming = stages.data_analysis?.streaming_reasoning || ''
  else if (props.scenarioType === 'predict') streaming = stages.data_prediction?.streaming_reasoning || ''
  else streaming = stages.sql_generation?.streaming_reasoning || ''
  if (streaming) return streaming
  if (props.message?.record?.sql_generating_content && !currentLLMStage.value) {
    const content = props.message.record.sql_generating_content.trim()
    if (content.startsWith('{') || content.startsWith('[')) return ''
    return content
  }
  return ''
})

const hasRagResults = computed(() => {
  return effectiveRagResults.value &&
    (effectiveRagResults.value.terminologies?.length > 0 ||
     effectiveRagResults.value.sql_examples?.length > 0 ||
     effectiveRagResults.value.document_chunks?.length > 0)
})

const isRagEnabled = computed(() => {
  if (effectiveRagResults.value?.rag_enabled === false) return false
  return true
})

const shouldShowRagStep = computed(() => {
  if (!props.showRagStep) return false
  return true
})

const isRagSkipped = computed(() => !isRagEnabled.value)

const ragTerminologies = computed(() => effectiveRagResults.value?.terminologies || [])
const ragSqlExamples = computed(() => effectiveRagResults.value?.sql_examples || [])
const ragCustomPrompts = computed(() => effectiveRagResults.value?.custom_prompts || [])
const ragAllCustomPrompts = computed(() => {
  const ragCps = ragCustomPrompts.value || []
  const pcCps = promptConstructionStage.value?.custom_prompts || []
  const seen = new Set<string>()
  const merged: any[] = []
  for (const cp of [...ragCps, ...pcCps]) {
    if (!seen.has(cp.type)) { seen.add(cp.type); merged.push(cp) }
  }
  return merged
})

const promptConstructionData = computed(() => promptConstructionStage.value?.extra_data || {})
const ragDocumentChunks = computed(() => effectiveRagResults.value?.document_chunks || [])
// ragTotalCount 应包含文档片段数量
// 包含文档片段数量
const ragTotalCount = computed(() => ragTerminologies.value.length + ragSqlExamples.value.length + ragTableCandidates.value.length + ragDocumentChunks.value.length)

// 表检索信息（从 rag_retrieval 阶段的 rag_retrieval 数据中提取）
const ragTableCandidates = computed(() => {
  const rag = ragStage.value?.rag_retrieval
  if (!rag) return []
  return rag.table_candidates || []
})
const ragSelectedTables = computed(() => {
  const rag = ragStage.value?.rag_retrieval
  if (!rag) return []
  return rag.tables_selected || []
})
const ragTableSimilarities = computed(() => {
  const rag = ragStage.value?.rag_retrieval
  if (!rag) return []
  return rag.table_similarities || []
})

const reasoningContent = computed<Array<string>>(() => {
  const names: Array<'sql_answer' | 'chart_answer' | 'analysis_thinking' | 'predict'> = []
  if (typeof props.reasoningName === 'string') names.push(props.reasoningName)
  else props.reasoningName.forEach((item) => names.push(item))
  const result: Array<string> = []
  names.forEach((item) => {
    if (props.message?.record) {
      let content = ''
      if (item === 'sql_answer') content = props.message.record.sql_reasoning_content || props.message.record.sql_answer || ''
      else if (item === 'chart_answer') content = props.message.record.chart_reasoning_content || props.message.record.chart_answer || ''
      else if (item === 'analysis_thinking') content = props.message.record.analysis_reasoning_content || props.message.record.analysis_thinking || ''
      else if (item === 'predict') content = props.message.record.predict_reasoning_content || props.message.record.predict_thinking || ''
      if (content && content.trim() !== '') result.push(content)
    }
  })
  return result
})

const hasReasoning = computed<boolean>(() => reasoningContent.value.some(c => c && c.trim() !== ''))
const isCurrentlyTyping = computed<boolean>(() => !!(props.message.isTyping && props.loading))
const shouldShowReasoningToggle = computed<boolean>(() => isCurrentlyTyping.value || hasReasoning.value || hasRagResults.value || !!thinkingProcess.value)

watch([isCurrentlyTyping, hasReasoning, hasRagResults, isLLMStageLoading, streamingReasoning, () => props.processStage], () => {})

const tokenUsage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  let totalTokens = { input: 0, output: 0, total: 0 }
  const stageList = Array.isArray(stages) ? stages : Object.values(stages)
  for (const stage of stageList) {
    if (stage?.llm_generation?.token_usage) {
      const usage = stage.llm_generation.token_usage
      totalTokens.input += usage.input_tokens || 0
      totalTokens.output += usage.output_tokens || 0
      totalTokens.total += usage.total_tokens || 0
    }
  }
  return totalTokens.total > 0 ? totalTokens : null
})

function formatTokens(count: number): string {
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`
  return count.toString()
}

const queryUnderstandingStage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) {
    const found = stages.find((s: any) => s.name === 'query_understanding' || s.stage === 'query_understanding') ||
           stages.find((s: any) => s.name === 'query_rewrite' || s.stage === 'query_rewrite') || null
    return normalizeStage(found)
  }
  if (stages.query_understanding) return normalizeStage({ name: 'query_understanding', ...stages.query_understanding })
  if (stages.query_rewrite) return normalizeStage({ name: 'query_understanding', ...stages.query_rewrite })
  return null
})

const promptConstructionStage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) return normalizeStage(stages.find((s: any) => s.name === 'prompt_construction' || s.stage === 'prompt_construction') || null)
  return stages.prompt_construction ? normalizeStage({ name: 'prompt_construction', ...stages.prompt_construction }) : null
})

const queryDecompositionStage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) return normalizeStage(stages.find((s: any) => s.name === 'query_decomposition' || s.stage === 'query_decomposition') || null)
  return stages.query_decomposition ? normalizeStage({ name: 'query_decomposition', ...stages.query_decomposition }) : null
})

const contextCompressionStage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) return normalizeStage(stages.find((s: any) => s.name === 'context_compression' || s.stage === 'context_compression') || null)
  return stages.context_compression ? normalizeStage({ name: 'context_compression', ...stages.context_compression }) : null
})

const smartOutputStage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) return normalizeStage(stages.find((s: any) => s.name === 'smart_output' || s.stage === 'smart_output') || null)
  return stages.smart_output ? normalizeStage({ name: 'smart_output', ...stages.smart_output }) : null
})

const antvG2ConfigStage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) return normalizeStage(stages.find((s: any) => s.name === 'antv_g2_config' || s.stage === 'antv_g2_config') || null)
  return stages.antv_g2_config ? normalizeStage({ name: 'antv_g2_config', ...stages.antv_g2_config }) : null
})

// 是否为纯文本输出（smart_answer / natural_language / direct），不需要图表可视化步骤
const isTextOnlyOutput = computed(() => {
  const ft = smartOutputStage.value?.format_type
  return ft === 'smart_answer' || ft === 'natural_language' || ft === 'direct'
})

const provenanceStage = computed(() => {
  let stage: any = null
  if (thinkingProcess.value?.stages) {
    const stages = thinkingProcess.value.stages
    if (Array.isArray(stages)) {
      stage = normalizeStage(stages.find((s: any) => s.name === 'provenance' || s.stage === 'provenance') || null)
    } else if (stages.provenance) {
      stage = normalizeStage({ name: 'provenance', ...stages.provenance })
    }
  }
  if (!stage) {
    const rag = effectiveRagResults.value as any
    if (rag?.document_chunks?.length > 0) {
      const chunks = rag.document_chunks
      const summary = rag.pdf_source_summary || {}
      stage = {
        name: 'provenance', status: 'completed',
        extra_data: {
          record_count: chunks.length, source_types: ['pdf'],
          avg_similarity: summary.avg_similarity || null, has_tables: summary.has_tables || false,
          records: chunks.map((c: any) => ({
            source_name: c.source_name || c.source_file || 'PDF', source_type: 'pdf',
            page_number: c.page_number, section_title: c.section_title,
            chunk_type: c.chunk_type, similarity: c.similarity, text: c.text,
          })),
        },
      }
      // normalizeStage 会将 extra_data 展开到顶层
      stage = normalizeStage(stage)
    }
  }
  const _records = stage?.extra_data?.records
  if (_records?.length) {
    if (!stage.extra_data.pages) {
      const pages = new Set<number>()
      _records.forEach((r: any) => { if (r.page_number) pages.add(r.page_number) })
      stage.extra_data.pages = Array.from(pages).sort((a: number, b: number) => a - b)
    }
    if (!stage.extra_data.sections) {
      const sections = new Set<string>()
      _records.forEach((r: any) => { if (r.section_title) sections.add(r.section_title) })
      stage.extra_data.sections = Array.from(sections)
    }
    if (!stage.extra_data.avg_similarity && stage.extra_data.avg_similarity !== 0) {
      const sims = _records.filter((r: any) => r.similarity).map((r: any) => r.similarity)
      if (sims.length > 0) stage.extra_data.avg_similarity = sims.reduce((a: number, b: number) => a + b, 0) / sims.length
    }
  }
  return stage
})

const retrievalValidationStage = computed(() => {
  if (!thinkingProcess.value?.stages) return null
  const stages = thinkingProcess.value.stages
  if (Array.isArray(stages)) return normalizeStage(stages.find((s: any) => s.name === 'retrieval_validation' || s.stage === 'retrieval_validation') || null)
  return stages.retrieval_validation ? normalizeStage({ name: 'retrieval_validation', ...stages.retrieval_validation }) : null
})

const dialogueContext = computed(() => {
  const qu = queryUnderstandingStage.value
  if (!qu) return null
  if (qu.dialogue_turn > 1 || (qu.context_references && qu.context_references.length > 0)) {
    return { turn: qu.dialogue_turn || 1, references: qu.context_references || [] }
  }
  return null
})

const predictReasoningContent = computed(() => props.message?.record?.predict_reasoning_content || props.message?.record?.predict_thinking || '')
const analysisReasoningContent = computed(() => props.message?.record?.analysis_reasoning_content || props.message?.record?.analysis_thinking || '')

// 引用来源文件名列表
const provenanceSourceFiles = computed(() => {
  if (!provenanceStage.value?.extra_data?.records) return []
  const files = new Set<string>()
  for (const rec of provenanceStage.value.extra_data.records) {
    if (rec.source_name) files.add(rec.source_name)
  }
  return Array.from(files)
})

// 引用来源主数据源类型
const provenancePrimaryType = computed(() => {
  if (!provenanceStage.value?.extra_data?.records?.length) return ''
  const rec = provenanceStage.value.extra_data.records[0]
  return rec.source_type || ''
})

// 引用来源主记录（非PDF场景通常只有1条）
const provenancePrimaryRecord = computed(() => {
  if (!provenanceStage.value?.extra_data?.records?.length) return null
  return provenanceStage.value.extra_data.records[0]
})

// PDF 实际片段数（排除 pdf_summary 记录）
const pdfActualChunkCount = computed(() => {
  const records = provenanceStage.value?.extra_data?.records
  if (!records?.length) return 0
  const summary = records.find((r: any) => r.source_type === 'pdf_summary')
  if (summary?.total_chunks) return summary.total_chunks
  return records.filter((r: any) => r.source_type !== 'pdf_summary').length
})

const progressPercent = computed(() => {
  const stage = props.processStage
  if (stage === 'idle') return 0
  // processStage='done' 但延迟分析/预测仍在加载时，
  // 进度条不应显示 100%，而是显示 88%（表示"图表已完成，分析/预测进行中"）
  if (stage === 'done') {
    if (props.deferredAnalysisLoading || props.deferredPredictLoading) return 88
    return 100
  }
  if (props.scenarioType === 'general_chat') {
    if (stage === 'query') return 25
    if (stage === 'rag') return 50
    if (stage === 'direct') return 75
    return 12
  }
  if (props.scenarioType === 'sql_analysis' || props.scenarioType === 'sql_prediction') {
    if (stage === 'query') return 10
    if (stage === 'rag') return 22
    if (stage === 'sql') return 40
    if (stage === 'execute') return 55
    if (stage === 'chart') return 70
    if (stage === 'analysis' || stage === 'predict') return 88
    return 5
  }
  if (props.scenarioType === 'analysis' || props.scenarioType === 'predict') {
    if (stage === 'query') return 15
    if (stage === 'rag') return 35
    if (stage === 'analysis' || stage === 'predict') return 75
    return 8
  }
  if (stage === 'query') return 10
  if (stage === 'rag') return 25
  if (stage === 'sql') return 45
  if (stage === 'execute') return 65
  if (stage === 'chart') return 85
  return 5
})

const progressLabel = computed(() => {
  const stage = props.processStage
  if (stage === 'idle') return ''
  // 延迟加载中时显示对应的阶段标签，而非"全部完成"
  if (stage === 'done') {
    if (props.deferredAnalysisLoading) return t('thinking.ai_analysis')
    if (props.deferredPredictLoading) return t('thinking.ai_predict')
    return t('thinking.all_completed')
  }
  if (stage === 'query') return t('rag_process.query_understanding')
  if (stage === 'rag') return t('thinking.retrieving')
  if (stage === 'sql') return t('thinking.generating_sql')
  if (stage === 'execute') return t('thinking.executing')
  if (stage === 'chart') return t('thinking.generating') + ' ' + t('thinking.generate_chart')
  if (stage === 'direct') return t('thinking.generating')
  if (stage === 'analysis') return t('thinking.ai_analysis')
  if (stage === 'predict') return t('thinking.ai_predict')
  return ''
})

const isProcessing = computed(() => props.processStage !== 'idle' && props.processStage !== 'done')
// 只有当 processStage='done' 且没有延迟加载时才算真正完成
const isProcessDone = computed(() => props.processStage === 'done' && !props.deferredAnalysisLoading && !props.deferredPredictLoading)

// 记住进度条曾经到达过100%，防止processStage重置为idle时进度条消失
const hasReachedDone = ref(false)
// 只有当延迟加载也完成时才标记为真正到达100%
watch([() => props.processStage, () => props.deferredAnalysisLoading, () => props.deferredPredictLoading], ([stage, dal, dpl]) => {
  if (stage === 'done' && !dal && !dpl) hasReachedDone.value = true
})
const displayProgress = computed(() => {
  if (hasReachedDone.value) return 100
  return progressPercent.value
})

function clickShow() { show.value = !show.value }

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}
/** 清理表名：去掉 Excel/CSV 内部的 10 位 hash 后缀（如 产品销售汇总_72ace56da3 → 产品销售汇总） */
function cleanTableName(name: string): string {
  if (!name) return name
  const parts = name.split('_')
  if (parts.length >= 2) {
    const last = parts[parts.length - 1]
    if (/^[a-f0-9]{10}$/.test(last)) return parts.slice(0, -1).join('_')
  }
  return name
}
/** 清理表注释：去掉 Excel/CSV 文件名前缀（如 "ChatBI演示数据_商业销售.xlsx - 每日销售汇总" → "每日销售汇总"） */
function cleanTableComment(comment: string): string {
  if (!comment) return comment
  const dashIdx = comment.indexOf(' - ')
  if (dashIdx >= 0 && /\.\w+$/.test(comment.substring(0, dashIdx))) return comment.substring(dashIdx + 3)
  return comment
}
function getConfidenceLabel(confidence: string): string {
  const labels: Record<string, string> = {
    'high': t('rag.confidence_high'), 'medium': t('rag.confidence_medium'),
    'low': t('rag.confidence_low'), 'very_low': t('rag.confidence_very_low'), 'none': t('rag.confidence_none')
  }
  return labels[confidence] || labels['none'] || t('rag.confidence_unknown')
}

function formatChartType(type: string): string {
  const map: Record<string, string> = {
    'column': '柱状图', 'bar': '条形图', 'line': '折线图', 'pie': '饼图',
    'area': '面积图', 'scatter': '散点图', 'radar': '雷达图', 'heatmap': '热力图',
    'funnel': '漏斗图', 'waterfall': '瀑布图', 'treemap': '矩形树图', 'table': '表格',
    'kpi': 'KPI卡片', 'dual-axes': '双轴图', 'rose': '玫瑰图', 'gauge': '仪表盘',
  }
  return map[type] || type
}

function formatOutputType(type: string): string {
  const map: Record<string, string> = {
    'keep': '保持原图表', 'smart_answer': '智能回答', 'table': '表格展示',
    'kpi': 'KPI卡片', 'direct': '直接回答', 'chart': '图表展示',
  }
  // format_type 可能是具体图表类型（如 line/bar/pie），兜底到 formatChartType
  return map[type] || formatChartType(type)
}

function formatChunkType(chunkType: string): string {
  const map: Record<string, string> = {
    'section': '📝 段落',
    'section_split': '📝 段落拆分',
    'table': '📊 表格',
    'table_overlap': '📊 表格重叠',
    'sliding_window': '📝 滑动窗口',
    'text': '📝 文本',
  }
  return map[chunkType] || '📄 PDF'
}

// 知识库展示，严格区分RAG三阶段角色

const isPdfScenario = computed(() => {
  const hasDocChunks = ragDocumentChunks.value.length > 0
  const isDocQaIntent = effectiveRagResults.value?.design_intent === 'document_qa'
  const hasStructuredHits = ragSqlExamples.value.length > 0
  // 当PDF查询命中0个文档片段时，通过 ds_type 兜底判断
  const isDsTypePdf = queryUnderstandingStage.value?.ds_type === 'pdf'
  if (hasStructuredHits && !hasDocChunks && !isDsTypePdf) return false
  return hasDocChunks || isDocQaIntent || isDsTypePdf
})

// 检索型知识库命中汇总（步骤2展示：只有通过向量检索命中的知识库）
// Fix：未命中的知识库不再显示，CSV/Excel/Database 三种数据源保持一致
const knowledgeBaseSummary = computed(() => {
  const items: Array<{ icon: string; name: string; count: number; active: boolean; role: string }> = []

  // 1. 商业术语库（仅结构化数据源：Database/Excel/CSV，且命中时才显示）
  if (!isPdfScenario.value && ragTerminologies.value.length > 0) {
    items.push({
      icon: '📘', name: t('thinking.kb_terminology'),
      count: ragTerminologies.value.length, active: true,
      role: 'retrieval'
    })
  }

  if (isPdfScenario.value) {
    // PDF场景：文档知识库是核心检索源（命中时才显示）
    if (ragDocumentChunks.value.length > 0) {
      items.push({
        icon: '📚', name: t('thinking.kb_document'),
        count: ragDocumentChunks.value.length, active: true,
        role: 'retrieval'
      })
    }
  } else {
    // 结构化数据场景：SQL示例库参与检索（命中时才显示）
    if (ragSqlExamples.value.length > 0) {
      items.push({
        icon: '🗃️', name: t('thinking.kb_sql_examples'),
        count: ragSqlExamples.value.length, active: true,
        role: 'retrieval'
      })
    }
  }

  return items
})

// 规则型提示词注入汇总（步骤3展示：按阶段直接注入的规则，不是检索命中的）
const customPromptSummary = computed(() => {
  // 架构设计PDF不使用任何自定义提示词
  // 三种提示词类型（SQL生成、数据分析、数据预测）都是针对结构化数据操作的
  // PDF只走RAG文档问答路径，不走SQL/分析/预测路径
  if (isPdfScenario.value) return []

  const cpAll = ragAllCustomPrompts.value
  const items: Array<{ icon: string; type: string; injected: boolean; empty: boolean }> = []

  // 根据当前场景类型决定展示哪些提示词
  const scenario = props.scenarioType
  const isSqlPath = scenario === 'sql' || scenario === 'sql_analysis' || scenario === 'sql_prediction'
  const isAnalysisPath = scenario === 'sql_analysis' || scenario === 'analysis'
  const isPredictPath = scenario === 'sql_prediction' || scenario === 'predict'

  // standalone analysis/predict 不走SQL路径，不应展示SQL提示词芯片
  if (isSqlPath) {
    const sqlPrompt = cpAll.find((c: any) =>
      c.type === 'sql_generation' || c.type === 'SQL生成' || c.type === 'SQL Generation'
    )
    items.push({
      icon: '', type: t('thinking.prompt_type_sql'),
      injected: !!(sqlPrompt?.used),
      empty: !!(sqlPrompt?.empty)
    })
  }

  if (isAnalysisPath) {
    const analysisPrompt = cpAll.find((c: any) =>
      c.type === 'analysis' || c.type === '数据分析' || c.type === 'Data Analysis'
    )
    items.push({
      icon: '📊', type: t('thinking.prompt_type_analysis'),
      injected: !!(analysisPrompt?.used),
      empty: !!(analysisPrompt?.empty)
    })
  }

  if (isPredictPath) {
    const predictPrompt = cpAll.find((c: any) =>
      c.type === 'prediction' || c.type === '数据预测' || c.type === 'Data Prediction'
    )
    items.push({
      icon: '🔮', type: t('thinking.prompt_type_prediction'),
      injected: !!(predictPrompt?.used),
      empty: !!(predictPrompt?.empty)
    })
  }

  return items
})
</script>

<template>
  <div class="base-answer-block">
    <!-- 思考过程按钮 -->
    <button v-if="shouldShowReasoningToggle" class="tp-toggle" :class="{ active: show, thinking: isCurrentlyTyping, done: isProcessDone || hasReachedDone }" @click="clickShow" :style="{ '--progress': displayProgress + '%' }">
      <span class="tp-toggle-icon">🧠</span>
      <span class="tp-toggle-label">{{ t('thinking.title') }}</span>
      <span v-if="tokenUsage" class="tp-toggle-tokens">{{ formatTokens(tokenUsage.total) }} 令牌</span>
      <span class="tp-toggle-arrow"><el-icon><icon_down_outlined v-if="!show" /><icon_up_outlined v-else /></el-icon></span>
    </button>

    <!-- ==================== 思考过程面板 ==================== -->
    <div v-if="shouldShowReasoningToggle && show" class="tp-panel">

      <!-- 进度条 -->
      <div class="tp-progress" v-if="isProcessing || isProcessDone">
        <div class="tp-progress-track">
          <div class="tp-progress-fill" :class="{ done: isProcessDone }" :style="{ width: progressPercent + '%' }"></div>
        </div>
        <div class="tp-progress-info">
          <span>{{ progressLabel }}</span>
          <span class="tp-progress-pct">{{ progressPercent }}%</span>
        </div>
      </div>

      <!-- ===== 推理链 ===== -->
      <div class="tp-chain">

        <!-- ══════ 步骤1: 查询理解 ══════ -->
        <div v-if="queryUnderstandingStage || isCurrentlyTyping" class="tp-step" :class="{ done: queryUnderstandingStage?.status === 'completed' || queryUnderstandingStage }">
          <div class="tp-step-bar"><div class="tp-step-dot"></div><div class="tp-step-line"></div></div>
          <div class="tp-step-body">
            <div class="tp-step-head">
              <span class="tp-step-num">1</span>
              <span class="tp-step-emoji">🎯</span>
              <span class="tp-step-name">{{ t('thinking.step_query_understanding') }}</span>
              <span class="tp-rag-phase">{{ t('thinking.rag_phase_query') }}</span>
              <span class="tp-step-badge" v-if="queryUnderstandingStage?.duration">{{ formatDuration(queryUnderstandingStage.duration) }}</span>
              <span class="tp-step-badge tp-badge-green" v-if="queryUnderstandingStage?.rewrite_applied">{{ t('thinking.badge_query_rewritten') }}</span>
              <span class="tp-step-badge tp-badge-blue" v-if="dialogueContext">{{ t('thinking.badge_dialogue_turn', { n: dialogueContext.turn }) }}</span>
              <span class="tp-step-badge tp-badge-blue" v-if="queryDecompositionStage?.sub_tasks?.length">{{ t('thinking.badge_sub_tasks', { n: queryDecompositionStage.sub_tasks.length }) }}</span>
              <span class="tp-scenario-tag">
                {{ scenarioType === 'general_chat' ? t('thinking.scenario_knowledge_qa') :
                   scenarioType === 'sql_analysis' ? t('thinking.scenario_sql_analysis') :
                   scenarioType === 'sql_prediction' ? t('thinking.scenario_sql_prediction') :
                   scenarioType === 'analysis' ? t('thinking.scenario_data_analysis') :
                   scenarioType === 'predict' ? t('thinking.scenario_data_prediction') :
                   t('thinking.scenario_sql_query') }}
              </span>
              <span class="tp-step-status">✓</span>
            </div>
            <div class="tp-step-summary">
              <QueryUnderstandingDisplay :data="queryUnderstandingStage" />
            </div>
          </div>
        </div>

        <!-- ══════ 步骤2: 知识检索 ══════ -->
        <div v-if="shouldShowRagStep && queryUnderstandingStage" class="tp-step" :class="{ done: !isRagSkipped && (ragStage || hasRagResults), skipped: isRagSkipped, loading: isCurrentlyTyping && props.processStage === 'rag' && !hasRagResults && !isRagSkipped }">
          <div class="tp-step-bar"><div class="tp-step-dot"></div><div class="tp-step-line"></div></div>
          <div class="tp-step-body">
            <div class="tp-step-head clickable" @click="hasRagResults ? toggleStep('step2') : null">
              <span class="tp-step-num">2</span>
              <span class="tp-step-emoji">🔍</span>
              <span class="tp-step-name">{{ t('thinking.step_knowledge_retrieval') }}</span>
              <span class="tp-rag-phase">{{ t('thinking.rag_phase_retrieve') }}</span>
              <span class="tp-step-badge tp-badge-dim" v-if="isRagSkipped">{{ t('thinking.badge_skipped') }}</span>
              <span class="tp-step-badge" v-else-if="ragStage?.duration">{{ formatDuration(ragStage.duration) }}</span>
              <span class="tp-step-badge tp-badge-green" v-if="!isRagSkipped && hasRagResults">{{ t('thinking.badge_hit_count', { n: ragTotalCount }) }}</span>
              <span class="tp-step-status tp-status-skipped" v-if="isRagSkipped">⊘</span>
              <span class="tp-step-status" v-else-if="ragStage || hasRagResults">✓</span>
              <span class="tp-step-status tp-status-loading" v-else-if="isCurrentlyTyping && !hasRagResults"></span>
              <span v-if="hasRagResults && !isRagSkipped" class="tp-step-expand">{{ isExpanded('step2') ? '▾' : '▸' }}</span>
            </div>
            <div class="tp-step-summary" v-if="!isRagSkipped">
              <!-- 检索流水线可视化（直接展示，不隐藏在悬浮提示中） -->
              <div class="tp-flow-viz" v-if="hasRagResults || ragStage">
                <!--  PDF 查询时只执行"语义搜索"步骤，
                     解析/分块/向量化是上传时完成的，不应在查询流程中展示 -->
                <div class="tp-flow-steps" v-if="isPdfScenario">
                  <span class="tp-flow-node">❓ {{ t('thinking.pdf_flow_question') }}</span>
                  <span class="tp-flow-arrow">→</span>
                  <span class="tp-flow-node">🧮 {{ t('thinking.pdf_flow_embed') }}</span>
                  <span class="tp-flow-arrow">→</span>
                  <span class="tp-flow-node tp-flow-active">🎯 {{ t('thinking.pdf_flow_search') }}</span>
                </div>
                <div class="tp-flow-steps" v-else>
                  <span class="tp-flow-node">📊 {{ t('thinking.structured_flow_datasource') }}</span>
                  <span class="tp-flow-arrow">→</span>
                  <span class="tp-flow-node">📘 {{ t('thinking.structured_flow_terminology') }}</span>
                  <span class="tp-flow-arrow">→</span>
                  <span class="tp-flow-node">🗃️ {{ t('thinking.structured_flow_examples') }}</span>
                  <span class="tp-flow-arrow">→</span>
                  <span class="tp-flow-node tp-flow-active">🔄 {{ t('thinking.structured_flow_rerank') }}</span>
                </div>
              </div>
              <!-- 表检索芯片（结构化数据源：只显示数量，详情在展开区查看） -->
              <div class="tp-kb-hits" v-if="hasRagResults || (ragSelectedTables.length > 0 && !isPdfScenario)">
                <span v-if="ragSelectedTables.length > 0 && !isPdfScenario" class="tp-kb-chip active" style="background: rgba(59,130,246,0.08); border-color: rgba(59,130,246,0.2);">
                  🗂️ {{ t('thinking.kb_table_retrieval') }}
                  <span class="tp-kb-count">{{ ragSelectedTables.length }}</span>
                </span>
                <span v-for="kb in knowledgeBaseSummary" :key="kb.name" class="tp-kb-chip" :class="{ active: kb.active }">
                  {{ kb.icon }} {{ kb.name }}
                  <span v-if="kb.active && kb.count > 0" class="tp-kb-count">{{ kb.count }}</span>
                </span>
                <!-- PDF场景：意图标签紧跟芯片后面，不单独占一行 -->
                <span v-if="isPdfScenario && effectiveRagResults?.design_intent" class="tp-kb-chip active" style="background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.2);">
                  🎯 {{ effectiveRagResults.design_intent === 'document_qa' ? t('thinking.design_intent_document_qa') : effectiveRagResults.design_intent === 'data_query' ? t('thinking.design_intent_data_query') : effectiveRagResults.design_intent === 'data_analysis' ? t('thinking.design_intent_data_analysis') : effectiveRagResults.design_intent === 'data_prediction' ? t('thinking.design_intent_data_prediction') : effectiveRagResults.design_intent }}
                </span>
              </div>
              <!-- RAG质量评分 -->
              <div class="tp-rag-quality" v-if="effectiveRagResults?.rag_impact">
                <span class="tp-rq-score">{{ t('thinking.rag_quality_label') }} {{ (effectiveRagResults.rag_impact.quality_score * 100 || 0).toFixed(0) }}/100</span>
                <span class="tp-rq-improve" v-if="effectiveRagResults.rag_impact.expected_improvement_display">{{ t('thinking.rag_quality_improve') }} {{ effectiveRagResults.rag_impact.expected_improvement_display }}</span>
                <span class="tp-rq-badge" :class="effectiveRagResults.rag_impact.confidence || 'none'">{{ getConfidenceLabel(effectiveRagResults.rag_impact.confidence) }}</span>
              </div>
            </div>
            <!-- 展开详情 -->
            <div v-if="isExpanded('step2') && hasRagResults" class="tp-step-detail">
              <!-- 表检索详情（Embedding 向量匹配） -->
              <div v-if="ragTableCandidates.length > 0 && !isPdfScenario" class="tp-detail-block">
                <div class="tp-detail-block-title">🗂️ {{ t('thinking.detail_table_retrieval', { n: ragSelectedTables.length, total: ragTableCandidates.length }) }}
                  <el-popover trigger="hover" placement="bottom" :width="680" :show-after="200" popper-class="tp-help-popover">
                    <template #reference>
                      <span class="tp-help-icon">❓</span>
                    </template>
                    <div class="tp-retrieval-method">
                      <span class="tp-rm-icon">🧮</span>
                      <span class="tp-rm-text">{{ t('thinking.retrieval_method_table_embedding') }}</span>
                    </div>
                  </el-popover>
                </div>
                <div class="tp-rg-list">
                  <div v-for="(tbl, idx) in ragTableCandidates.filter(t => ragSelectedTables.includes(t.name)).slice(0, 10)" :key="'tc-' + idx" class="tp-rg-item">
                    <span class="tp-rg-name">{{ cleanTableName(tbl.name) }}<span v-if="tbl.comment" style="opacity: 0.6; margin-left: 4px;">{{ cleanTableComment(tbl.comment) }}</span></span>
                    <span class="tp-match-tag vector">{{ t('thinking.match_semantic') }}</span>
                    <span class="tp-rg-score" :class="{ high: (tbl.similarity || 0) >= 0.7 }">{{ ((tbl.similarity || 0) * 100).toFixed(0) }}%</span>
                  </div>
                </div>
              </div>
              <div v-if="ragTerminologies.length > 0" class="tp-detail-block">
                <div class="tp-detail-block-title">📘 {{ t('thinking.detail_terminology_library', { n: ragTerminologies.length }) }}
                  <el-popover trigger="hover" placement="bottom" :width="680" :show-after="200" popper-class="tp-help-popover">
                    <template #reference>
                      <span class="tp-help-icon">❓</span>
                    </template>
                    <div class="tp-retrieval-method">
                      <span class="tp-rm-icon">🔍</span>
                      <span class="tp-rm-text">{{ t('thinking.retrieval_method_terminology') }}</span>
                    </div>
                  </el-popover>
                </div>
                <div class="tp-rg-list">
                  <div v-for="(term, idx) in ragTerminologies" :key="idx" class="tp-rg-item">
                    <span class="tp-rg-name">{{ term.word }}</span>
                    <span class="tp-match-tag" :class="term.match_type === 'keyword' ? 'keyword' : 'vector'">{{ term.match_type === 'keyword' ? t('thinking.match_keyword') : t('thinking.match_semantic') }}</span>
                    <span v-if="term.match_type !== 'keyword'" class="tp-rg-score" :class="{ high: (term.similarity || 0) >= 0.7 }">{{ ((term.similarity || 0) * 100).toFixed(0) }}%</span>
                  </div>
                </div>
              </div>
              <div v-if="ragSqlExamples.length > 0" class="tp-detail-block">
                <div class="tp-detail-block-title">🗃️ {{ t('thinking.detail_sql_examples_library', { n: ragSqlExamples.length }) }}
                  <el-popover trigger="hover" placement="bottom" :width="680" :show-after="200" popper-class="tp-help-popover">
                    <template #reference>
                      <span class="tp-help-icon">❓</span>
                    </template>
                    <div class="tp-retrieval-method">
                      <span class="tp-rm-icon">🧮</span>
                      <span class="tp-rm-text">{{ t('thinking.retrieval_method_sql_examples') }}</span>
                    </div>
                  </el-popover>
                </div>
                <div class="tp-rg-list">
                  <div v-for="(ex, idx) in ragSqlExamples" :key="idx" class="tp-rg-item">
                    <span class="tp-rg-name">{{ ex.question }}</span>
                    <span class="tp-match-tag" :class="ex.match_type === 'keyword' ? 'keyword' : ex.match_type === 'substring' ? 'substring' : ex.match_type === 'token_fuzzy' ? 'token-fuzzy' : 'vector'">{{ ex.match_type === 'keyword' ? t('thinking.match_keyword') : ex.match_type === 'substring' ? t('thinking.match_substring') : ex.match_type === 'token_fuzzy' ? t('thinking.match_token_fuzzy') : t('thinking.match_semantic') }}</span>
                    <span v-if="ex.match_type !== 'keyword' && ex.match_type !== 'substring'" class="tp-rg-score" :class="{ high: (ex.similarity || 0) >= 0.7 }">{{ ((ex.similarity || 0) * 100).toFixed(0) }}%</span>
                  </div>
                </div>
              </div>
              <div v-if="ragDocumentChunks.length > 0" class="tp-detail-block">
                <div class="tp-detail-block-title">📚 {{ t('thinking.detail_document_knowledge', { n: ragDocumentChunks.length }) }}
                  <el-popover trigger="hover" placement="bottom" :width="680" :show-after="200" popper-class="tp-help-popover">
                    <template #reference>
                      <span class="tp-help-icon">❓</span>
                    </template>
                    <div class="tp-retrieval-method">
                      <span class="tp-rm-icon">🧮</span>
                      <span class="tp-rm-text">{{ t('thinking.retrieval_method_embedding') }}</span>
                    </div>
                  </el-popover>
                </div>
                <div v-if="effectiveRagResults?.pdf_source_summary" class="tp-kv-list" style="margin-bottom: 8px;">
                  <div class="tp-kv"><span class="tp-kv-k">{{ t('thinking.detail_cited_pages') }}</span><span class="tp-kv-v">{{ effectiveRagResults.pdf_source_summary.pages?.join(', ') || t('thinking.detail_none') }}</span></div>
                  <div class="tp-kv" v-if="effectiveRagResults.pdf_source_summary.sections?.length"><span class="tp-kv-k">{{ t('thinking.detail_sections') }}</span><span class="tp-kv-v">{{ effectiveRagResults.pdf_source_summary.sections.join('、') }}</span></div>
                  <div class="tp-kv"><span class="tp-kv-k">{{ t('thinking.detail_avg_relevance') }}</span><span class="tp-kv-v">{{ ((effectiveRagResults.pdf_source_summary.avg_similarity || 0) * 100).toFixed(0) }}%</span></div>
                </div>
                <div class="tp-rg-list">
                  <div v-for="(chunk, idx) in ragDocumentChunks" :key="idx" class="tp-rg-item tp-rg-doc">
                    <div class="tp-doc-source">
                      <span class="tp-doc-type">{{ chunk.source_type === 'pdf' ? 'PDF' : chunk.source_type === 'excel' ? 'Excel' : chunk.source_type === 'csv' ? 'CSV' : '文件' }}</span>
                      {{ chunk.source_name || chunk.source_file }}
                      <span v-if="chunk.page_number" class="tp-tag tp-tag-dim" style="margin-left: 4px;">{{ t('thinking.page_number', { n: chunk.page_number }) }}</span>
                      <span class="tp-match-tag vector">{{ t('thinking.match_semantic') }}</span>
                    </div>
                    <div class="tp-doc-text clickable" @click="toggleStep('doc_chunk_' + idx)">
                      <template v-if="isExpanded('doc_chunk_' + idx)">{{ chunk.text }}</template>
                      <template v-else>{{ chunk.text.substring(0, 120) }}{{ chunk.text.length > 120 ? '...' : '' }}</template>
                      <span v-if="chunk.text.length > 120" class="tp-doc-expand-hint">{{ isExpanded('doc_chunk_' + idx) ? '▾ ' + t('thinking.collapse') : '▸ ' + t('thinking.expand') }}</span>
                    </div>
                    <span class="tp-rg-score" :class="{ high: (chunk.similarity || 0) >= 0.7 }">{{ ((chunk.similarity || 0) * 100).toFixed(0) }}%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ══════ 步骤3: 上下文增强 ══════ -->
        <!--  Step 3 显示条件 + 状态区分 -->
        <!-- contextCompressionStage 到达时显示为 loading 状态，promptConstructionStage 完成后才标记 done -->
        <div v-if="(promptConstructionStage || contextCompressionStage) && (ragStage || hasRagResults || isRagSkipped)" class="tp-step" :class="{ done: promptConstructionStage?.status === 'completed', loading: !promptConstructionStage?.status && contextCompressionStage }">
          <div class="tp-step-bar"><div class="tp-step-dot"></div><div class="tp-step-line"></div></div>
          <div class="tp-step-body">
            <div class="tp-step-head clickable" @click="toggleStep('step3')">
              <span class="tp-step-num">3</span>
              <span class="tp-step-emoji"></span>
              <span class="tp-step-name">{{ t('thinking.step_context_augmentation') }}</span>
              <span class="tp-rag-phase">{{ t('thinking.rag_phase_augment') }}</span>
              <span class="tp-step-badge" v-if="promptConstructionStage?.duration">{{ formatDuration(promptConstructionStage.duration) }}</span>
              <span class="tp-step-badge tp-badge-blue" v-if="promptConstructionStage?.prompt_type">
                {{ promptConstructionStage.prompt_type === 'sql_generation' ? t('thinking.scene_sql') :
                   promptConstructionStage.prompt_type === 'analysis' ? t('thinking.scene_analysis') :
                   promptConstructionStage.prompt_type === 'prediction' ? t('thinking.scene_prediction') :
                   promptConstructionStage.prompt_type === 'direct_answer' ? t('thinking.scene_direct') : t('thinking.scene_general') }}
              </span>
              <span class="tp-step-status" v-if="promptConstructionStage?.status === 'completed'">✓</span>
              <span class="tp-step-expand">{{ isExpanded('step3') ? '▾' : '▸' }}</span>
            </div>
            <div class="tp-step-summary">
              <!-- 上下文注入组件（RAG的A阶段：将检索结果+规则注入Prompt） -->
              <div class="tp-tags-row">
                <span class="tp-tag tp-tag-green" v-if="!isPdfScenario && promptConstructionStage?.rag_components?.schema">📋 {{ t('thinking.kb_schema') }}</span>
                <span class="tp-tag tp-tag-green" v-if="!isPdfScenario && promptConstructionStage?.rag_components?.terminologies">📘 {{ t('thinking.kb_terminology') }} {{ ragTerminologies.length || promptConstructionStage?.component_counts?.terminology_count || '' }}{{ t('thinking.items') }}</span>
                <span class="tp-tag tp-tag-green" v-if="!isPdfScenario && promptConstructionStage?.rag_components?.sql_examples">🗃️ {{ t('thinking.sql_examples') }} {{ promptConstructionStage?.component_counts?.sql_example_count || '' }}{{ t('thinking.items') }}</span>
                <span class="tp-tag tp-tag-green" v-if="promptConstructionStage?.rag_components?.document_chunks">📚 {{ t('thinking.kb_document') }} {{ promptConstructionStage?.component_counts?.doc_chunk_count || '' }}{{ t('thinking.items') }}</span>
                <span class="tp-tag tp-tag-green" v-if="promptConstructionStage?.rag_components?.dialogue_context">💬 {{ t('thinking.dialogue_state_title') }}</span>
              </div>
              <div class="tp-prompt-size" v-if="promptConstructionStage?.total_prompt_length">
                <span class="tp-ps-label">{{ t('thinking.prompt_label') }}</span>
                <span class="tp-ps-value">{{ promptConstructionStage.total_prompt_length > 1000 ? (promptConstructionStage.total_prompt_length / 1000).toFixed(1) + 'K' : promptConstructionStage.total_prompt_length }} {{ t('thinking.chars') }}</span>
                <span class="tp-ps-model" v-if="promptConstructionStage?.model_name">{{ promptConstructionStage.model_name }}</span>
              </div>
              <!-- 自定义提示词注入状态（规则型 Augmentation：按场景注入的业务规则） -->
              <div class="tp-tags-row" v-if="customPromptSummary.length > 0" style="margin-top: 6px;">
                <span v-for="cp in customPromptSummary" :key="cp.type" class="tp-tag" :class="cp.injected ? 'tp-tag-green' : cp.empty ? 'tp-tag-dim' : 'tp-tag-amber'">
                  {{ cp.icon }} {{ cp.type }}
                  <span v-if="cp.injected" style="margin-left: 2px;">✓</span>
                  <span v-else-if="cp.empty" style="margin-left: 2px; opacity: 0.6;">{{ t('thinking.badge_not_configured') }}</span>
                </span>
              </div>
            </div>
            <div v-if="isExpanded('step3')" class="tp-step-detail">
              <!-- 上下文压缩（R-layer最后一步：压缩检索结果，为Augment阶段的Prompt构建做准备） -->
              <div class="tp-detail-block" v-if="contextCompressionStage || retrievalValidationStage">
                <div class="tp-detail-block-title">🗜️ {{ t('thinking.detail_context_compression') }}</div>
                <div class="tp-kv-list">
                  <div class="tp-kv" v-if="retrievalValidationStage?.second_retrieval_triggered">
                    <span class="tp-kv-k">{{ t('thinking.detail_second_retrieval') }}</span>
                    <span class="tp-kv-v"><span class="tp-tag tp-tag-amber">{{ t('thinking.detail_triggered') }}</span></span>
                  </div>
                  <div class="tp-kv" v-if="contextCompressionStage?.compression_applied">
                    <span class="tp-kv-k">{{ t('thinking.detail_compression') }}</span>
                    <span class="tp-kv-v">{{ contextCompressionStage?.original_length || 0 }} → {{ contextCompressionStage?.compressed_length || 0 }} {{ t('thinking.chars') }} <span class="tp-tag tp-tag-green">{{ t('thinking.detail_saved') }} {{ ((1 - (contextCompressionStage?.compression_ratio || 1)) * 100).toFixed(0) }}%</span></span>
                  </div>
                  <div class="tp-kv" v-else-if="contextCompressionStage?.compression_skipped">
                    <span class="tp-kv-k">{{ t('thinking.detail_compression') }}</span>
                    <span class="tp-kv-v">
                      <span class="tp-tag tp-tag-green">{{ t('thinking.compression_within_budget') }}</span>
                      <span v-if="contextCompressionStage?.estimated_tokens" style="margin-left: 6px; font-size: 11px; color: rgba(255,255,255,0.45);">≈{{ contextCompressionStage.estimated_tokens }}<span v-if="contextCompressionStage?.token_budget">/{{ contextCompressionStage.token_budget }}</span> {{ t('thinking.unit_tokens') }}</span>
                    </span>
                  </div>
                  <div class="tp-kv" v-else-if="contextCompressionStage">
                    <span class="tp-kv-k">{{ t('thinking.detail_compression') }}</span>
                    <span class="tp-kv-v">
                      {{ contextCompressionStage?.original_length || 0 }} {{ t('thinking.chars') }}
                      <span class="tp-tag tp-tag-dim" style="margin-left: 4px;">≈{{ contextCompressionStage?.estimated_tokens || '?' }}<span v-if="contextCompressionStage?.token_budget">/{{ contextCompressionStage.token_budget }}</span> {{ t('thinking.unit_tokens') }}</span>
                    </span>
                  </div>
                </div>
              </div>
              <PromptConstructionDisplay :data="promptConstructionData" />
            </div>
          </div>
        </div>

        <!-- ══════ 步骤4: 大模型推理 ══════ -->
        <div v-if="(promptConstructionStage?.status === 'completed') || currentLLMStage || executionStage" class="tp-step" :class="{ done: currentLLMStage || executionStage || chartStage || analysisStage || predictStage, loading: isCurrentlyTyping && !currentLLMStage && props.processStage !== 'idle' && props.processStage !== 'rag' }">
          <div class="tp-step-bar">
            <div class="tp-step-dot"></div>
            <div class="tp-step-line" v-if="scenarioType !== 'general_chat' && scenarioType !== 'analysis' && scenarioType !== 'predict'"></div>
          </div>
          <div class="tp-step-body">
            <div class="tp-step-head clickable" @click="(reasoningContent[0] || analysisReasoningContent || streamingReasoning) ? toggleStep('step4') : null">
              <span class="tp-step-num">4</span>
              <span class="tp-step-emoji">🤖</span>
              <span class="tp-step-name">{{ t('thinking.step_llm_reasoning') }}</span>
              <span class="tp-rag-phase">{{ t('thinking.rag_phase_generate') }}</span>
              <span class="tp-step-badge" v-if="currentLLMStage?.duration">{{ formatDuration(currentLLMStage.duration) }}</span>
              <span class="tp-step-badge tp-badge-amber" v-if="currentLLMStage?.llm_generation?.token_usage?.total_tokens">{{ formatTokens(currentLLMStage.llm_generation.token_usage.total_tokens) }} {{ t('thinking.unit_tokens') }}</span>
              <span class="tp-step-status" v-if="currentLLMStage || executionStage || chartStage">✓</span>
              <span class="tp-step-status tp-status-loading" v-else-if="isCurrentlyTyping && props.processStage !== 'idle' && props.processStage !== 'rag'"></span>
              <span v-if="reasoningContent[0] || analysisReasoningContent || streamingReasoning" class="tp-step-expand">{{ isExpanded('step4') ? '▾' : '▸' }}</span>
            </div>
            <div v-if="isExpanded('step4') && (reasoningContent[0] || analysisReasoningContent || streamingReasoning)" class="tp-step-detail">
              <div class="tp-reasoning">
                <div class="tp-reasoning-label">{{ scenarioType === 'general_chat' ? t('thinking.reasoning_answer_gen') : scenarioType === 'analysis' ? t('thinking.reasoning_analysis_gen') : scenarioType === 'predict' ? t('thinking.reasoning_prediction_gen') : t('thinking.reasoning_sql_gen') }}</div>
                <div class="tp-reasoning-content">
                  <MdComponent v-if="reasoningContent[0]" :message="reasoningContent[0]" />
                  <MdComponent v-else-if="analysisReasoningContent" :message="analysisReasoningContent" />
                  <pre v-else class="tp-code-preview">{{ streamingReasoning }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ══════ 步骤5: 结果输出（SQL场景，纯文本输出时隐藏） ══════ -->
        <div v-if="!isTextOnlyOutput && (scenarioType === 'sql' || scenarioType === 'sql_analysis' || scenarioType === 'sql_prediction') && (currentLLMStage || executionStage || chartStage) && (sqlStage || executionStage || chartStage)" class="tp-step" :class="{ done: chartStage || analysisStage || predictStage, loading: isCurrentlyTyping && (executionStage && !chartStage) || (sqlStage && !executionStage) }">
          <div class="tp-step-bar">
            <div class="tp-step-dot"></div>
            <div class="tp-step-line" v-if="scenarioType === 'sql_analysis' || scenarioType === 'sql_prediction'"></div>
          </div>
          <div class="tp-step-body">
            <div class="tp-step-head clickable" @click="(message?.record?.sql || reasoningContent[1]) ? toggleStep('step5') : null">
              <span class="tp-step-num">5</span>
              <span class="tp-step-emoji">📊</span>
              <span class="tp-step-name">{{ t('thinking.step_data_visualization') }}</span>
              <span class="tp-rag-phase">{{ t('thinking.rag_phase_generate') }}</span>
              <span class="tp-step-badge" v-if="executionStage?.duration || chartStage?.duration">{{ formatDuration((chartStage?.duration || 0) + (executionStage?.duration || 0)) }}</span>
              <span class="tp-step-badge tp-badge-green" v-if="executionStage?.execution?.row_count !== undefined">{{ executionStage.execution.row_count }} {{ t('thinking.rows') }}</span>
              <span class="tp-step-badge tp-badge-blue" v-if="chartStage?.chart_type">{{ formatChartType(chartStage.chart_type) }}</span>
              <span class="tp-step-status" v-if="chartStage || analysisStage || predictStage">✓</span>
              <span class="tp-step-status tp-status-loading" v-else-if="isCurrentlyTyping && (sqlStage || executionStage)"></span>
              <span v-if="message?.record?.sql || reasoningContent[1]" class="tp-step-expand">{{ isExpanded('step5') ? '▾' : '▸' }}</span>
            </div>
            <div v-if="smartOutputStage?.format_type" class="tp-step-summary">
              <div class="tp-tags-row">
                <!-- 仅当 format_type 与头部 badge 的 chart_type 不同时才显示，避免重复展示图表类型 -->
                <span class="tp-tag tp-tag-blue" v-if="smartOutputStage.format_type !== chartStage?.chart_type">{{ formatOutputType(smartOutputStage.format_type) }}</span>
                <span class="tp-tag tp-tag-green">{{ t('thinking.rows_x_fields', { rows: smartOutputStage?.row_count, fields: smartOutputStage?.field_count }) }}</span>
              </div>
              <!-- AntV G2 可视化配置（展示图表维度映射） -->
              <div class="tp-g2-config" v-if="antvG2ConfigStage">
                <span class="tp-g2-label">{{ t('thinking.g2_config_label') }}</span>
                <span class="tp-tag tp-tag-blue" v-if="antvG2ConfigStage.chart_type">{{ formatChartType(antvG2ConfigStage.chart_type) }}</span>
                <template v-if="antvG2ConfigStage.dimensions">
                  <span class="tp-g2-dim" v-if="antvG2ConfigStage.dimensions.x">X: {{ antvG2ConfigStage.dimensions.x?.value || antvG2ConfigStage.dimensions.x }}</span>
                  <span class="tp-g2-dim" v-if="antvG2ConfigStage.dimensions.y">Y: {{ antvG2ConfigStage.dimensions.y?.value || antvG2ConfigStage.dimensions.y }}</span>
                  <span class="tp-g2-dim" v-if="antvG2ConfigStage.dimensions.series">{{ t('thinking.g2_series') }}: {{ antvG2ConfigStage.dimensions.series?.value || antvG2ConfigStage.dimensions.series }}</span>
                </template>
              </div>
            </div>
            <div v-else-if="message?.record?.sql && !isExpanded('step5')" class="tp-step-summary">
              <pre class="tp-sql-preview">{{ message.record.sql.length > 120 ? message.record.sql.substring(0, 120) + '...' : message.record.sql }}</pre>
            </div>
            <div v-if="isExpanded('step5')" class="tp-step-detail">
              <div v-if="message?.record?.sql" class="tp-detail-block">
                <div class="tp-detail-block-title">{{ t('thinking.detail_sql_query') }}</div>
                <pre class="tp-sql-display">{{ message.record.sql }}</pre>
              </div>
              <div v-if="reasoningContent[1]" class="tp-detail-block">
                <div class="tp-reasoning">
                  <div class="tp-reasoning-label">{{ t('thinking.detail_chart_config') }}</div>
                  <div class="tp-reasoning-content"><MdComponent :message="reasoningContent[1]" /></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ══════ 引用来源（不再作为思考链步骤，移至回答区域下方） ══════ -->

        <!-- ══════ 步骤6: 深度分析（sql_analysis/sql_prediction） ══════ -->
        <div v-if="(scenarioType === 'sql_analysis' || scenarioType === 'sql_prediction') && chartStage" class="tp-step" :class="{ done: analysisStage || predictStage, loading: (isCurrentlyTyping && chartStage && !analysisStage && !predictStage) || (deferredAnalysisLoading && !analysisStage) || (deferredPredictLoading && !predictStage) }">
          <div class="tp-step-bar"><div class="tp-step-dot tp-dot-star"></div></div>
          <div class="tp-step-body">
            <div class="tp-step-head">
              <span class="tp-step-num tp-num-star">6</span>
              <span class="tp-step-emoji">{{ scenarioType === 'sql_prediction' ? '🔮' : '' }}</span>
              <span class="tp-step-name">{{ scenarioType === 'sql_prediction' ? t('thinking.step_smart_prediction') : t('thinking.step_deep_analysis') }}</span>
              <span class="tp-rag-phase">{{ t('thinking.rag_phase_generate') }}</span>
              <span class="tp-step-badge" v-if="(analysisStage || predictStage)?.duration">{{ formatDuration((analysisStage || predictStage)?.duration || 0) }}</span>
              <span class="tp-step-badge tp-badge-amber" v-if="(analysisStage || predictStage)?.llm_generation?.token_usage?.total_tokens">{{ formatTokens((analysisStage || predictStage).llm_generation.token_usage.total_tokens) }} {{ t('thinking.unit_tokens') }}</span>
              <span class="tp-step-status" v-if="analysisStage || predictStage">✓</span>
              <span class="tp-step-status tp-status-loading" v-else-if="(isCurrentlyTyping && chartStage) || deferredAnalysisLoading || deferredPredictLoading"></span>
            </div>
          </div>
        </div>

      </div><!-- end tp-chain -->
    </div><!-- end tp-panel -->

    <!-- 主内容区域 -->
    <div class="answer-container">
      <slot></slot>
      <slot name="source-info">
        <!-- 引用来源卡片（紧贴回答下方） -->
    <div v-if="!hideCitation && !loading && provenanceStage?.extra_data?.records?.length" class="citation-bar">
      <div class="citation-header clickable" @click="toggleStep('citation')">
        <span class="citation-icon">{{ provenancePrimaryType === 'database' || provenancePrimaryType === 'knowledge_base' ? '🗄️' : provenancePrimaryType === 'excel' ? '📊' : provenancePrimaryType === 'csv' ? '📋' : provenancePrimaryType === 'pdf' ? '📄' : '📎' }}</span>
        <span class="citation-summary">
          <!-- PDF 来源 -->
          <template v-if="provenancePrimaryType === 'pdf' || provenancePrimaryType === 'pdf_summary'">
            {{ t('thinking.citation_from_pdf', { files: provenanceSourceFiles.join('、') }) }}
            <template v-if="provenanceStage.extra_data.pages?.length"> · {{ t('thinking.citation_page', { pages: provenanceStage.extra_data.pages.join('、') }) }}</template>
          </template>
          <!-- 数据库来源（含历史 knowledge_base 类型兼容） -->
          <template v-else-if="provenancePrimaryType === 'database' || provenancePrimaryType === 'knowledge_base'">
            {{ t('thinking.citation_from_db', { files: provenanceSourceFiles.join('、') }) }}
            <template v-if="provenancePrimaryRecord?.table_names?.length"> · {{ provenancePrimaryRecord.table_names.join('、') }}</template>
          </template>
          <!-- Excel 来源 -->
          <template v-else-if="provenancePrimaryType === 'excel'">
            {{ t('thinking.citation_from_excel', { files: provenanceSourceFiles.join('、') }) }}
            <template v-if="provenancePrimaryRecord?.table_names?.length"> · {{ provenancePrimaryRecord.table_names.join('、') }}</template>
            <template v-else-if="provenancePrimaryRecord?.sheet_name"> · {{ provenancePrimaryRecord.sheet_name }}</template>
          </template>
          <!-- CSV 来源 -->
          <template v-else-if="provenancePrimaryType === 'csv'">
            {{ t('thinking.citation_from_csv', { files: provenanceSourceFiles.join('、') }) }}
            <template v-if="provenancePrimaryRecord?.table_names?.length"> · {{ provenancePrimaryRecord.table_names.join('、') }}</template>
          </template>
          <!-- 其他 -->
          <template v-else>
            {{ t('thinking.citation_from_kb', { files: provenanceSourceFiles.join('、') || t('thinking.citation_default_kb') }) }}
          </template>
        </span>
        <!-- 右侧摘要指标 -->
        <span class="citation-meta">
          <template v-if="provenancePrimaryType === 'pdf' || provenancePrimaryType === 'pdf_summary'">
            <template v-if="pdfActualChunkCount > 0">
              {{ t('thinking.citation_chunks', { n: pdfActualChunkCount }) }}
              <template v-if="provenanceStage.extra_data.avg_similarity"> · {{ t('thinking.citation_relevance', { pct: ((provenanceStage.extra_data.avg_similarity || 0) * 100).toFixed(0) }) }}</template>
            </template>
          </template>
          <template v-else-if="provenancePrimaryRecord?.row_count !== undefined">
            {{ t('thinking.citation_rows', { n: provenancePrimaryRecord.row_count }) }}
            <template v-if="provenancePrimaryRecord?.execution_time"> · {{ provenancePrimaryRecord.execution_time < 1 ? (provenancePrimaryRecord.execution_time * 1000).toFixed(0) + 'ms' : provenancePrimaryRecord.execution_time.toFixed(2) + 's' }}</template>
            <template v-if="provenancePrimaryRecord?.cache_status === 'hit'"> · {{ t('thinking.citation_cache_hit') }}</template>
          </template>
          <template v-else-if="provenancePrimaryRecord?.data_rows !== undefined">
            {{ t('thinking.rows_x_fields', { rows: provenancePrimaryRecord.data_rows, fields: provenancePrimaryRecord.data_fields || 0 }) }}
          </template>
          <template v-else-if="provenancePrimaryRecord?.terminology_count || provenancePrimaryRecord?.terminologies_used">
            {{ t('thinking.kb_terminology') }} {{ provenancePrimaryRecord.terminology_count || provenancePrimaryRecord.terminologies_used }}{{ t('thinking.items') }}
          </template>
        </span>
        <span class="citation-expand">{{ isExpanded('citation') ? '▾' : '▸' }}</span>
      </div>
      <!-- 展开详情 -->
      <div v-if="isExpanded('citation')" class="citation-detail">
        <!-- PDF 展开：逐条引用片段 -->
        <template v-if="provenancePrimaryType === 'pdf' || provenancePrimaryType === 'pdf_summary'">
          <div v-for="(rec, idx) in provenanceStage.extra_data.records.filter((r: any) => r.source_type !== 'pdf_summary')" :key="idx" class="citation-card">
            <div class="cc-header">
              <span class="cc-source">{{ rec.source_name || t('thinking.citation_unknown_source') }}</span>
              <span class="cc-type">{{ formatChunkType(rec.chunk_type) }}</span>
              <span class="cc-page" v-if="rec.page_number">{{ t('thinking.page_number', { n: rec.page_number }) }}</span>
              <span class="cc-section" v-if="rec.section_title">{{ rec.section_title }}</span>
              <span class="cc-sim" v-if="rec.similarity" :class="{ high: rec.similarity >= 0.7 }">{{ (rec.similarity * 100).toFixed(0) }}%</span>
            </div>
            <div class="cc-text" v-if="rec.text">{{ rec.text.length > 150 ? rec.text.substring(0, 150) + '...' : rec.text }}</div>
          </div>
        </template>
        <!-- 结构化数据展开：SQL + 数据概况 -->
        <template v-else>
          <div v-for="(rec, idx) in provenanceStage.extra_data.records" :key="idx" class="citation-card">
            <div class="cc-header">
              <span class="cc-source">{{ rec.source_name || t('thinking.citation_unknown_source') }}</span>
              <span class="cc-type">{{ rec.source_type === 'database' || rec.source_type === 'knowledge_base' ? '🗄️ ' + t('thinking.citation_type_database') : rec.source_type === 'excel' ? '📊 ' + t('thinking.citation_type_excel') : rec.source_type === 'csv' ? '📋 ' + t('thinking.citation_type_csv') : '📎 ' + t('thinking.citation_type_kb') }}</span>
              <span class="cc-tag" v-if="rec.sheet_name && !(rec.table_names?.length)">{{ t('thinking.citation_sheet') }} {{ rec.sheet_name }}</span>
              <span class="cc-tag" v-if="rec.row_count !== undefined">{{ t('thinking.n_rows', { n: rec.row_count }) }}</span>
              <span class="cc-tag" v-if="rec.data_rows !== undefined && rec.data_fields && rec.row_count === undefined">{{ t('thinking.rows_x_fields', { rows: rec.data_rows, fields: rec.data_fields }) }}</span>
              <span class="cc-tag cc-tag-green" v-if="rec.cache_status === 'hit'">{{ t('thinking.citation_cache_hit') }}</span>
              <span class="cc-tag" v-if="rec.execution_time">{{ rec.execution_time < 1 ? (rec.execution_time * 1000).toFixed(0) + 'ms' : rec.execution_time.toFixed(2) + 's' }}</span>
              <span class="cc-tag" v-if="rec.terminologies_used">{{ t('thinking.kb_terminology') }} {{ rec.terminologies_used }}{{ t('thinking.items') }}</span>
              <span class="cc-tag" v-else-if="rec.terminology_count">{{ t('thinking.kb_terminology') }} {{ rec.terminology_count }}{{ t('thinking.items') }}</span>
              <span class="cc-tag cc-tag-green" v-if="rec.custom_prompt_used">{{ t('thinking.kb_custom_prompt') }}</span>
            </div>
            <!-- SQL 语句 -->
            <pre class="cc-sql" v-if="rec.sql">{{ rec.sql }}</pre>
            <!-- 查询表 -->
            <div class="cc-tables" v-if="rec.table_names?.length">
              <span class="cc-table-tag" v-for="t in rec.table_names" :key="t">{{ t }}</span>
            </div>
            <!-- 描述 -->
            <div class="cc-text" v-if="rec.description && !rec.sql">{{ rec.description }}</div>
          </div>
        </template>
      </div>
    </div>
      </slot>
      <slot name="tool"></slot>
      <slot name="footer"></slot>
    </div>
  </div>
</template>

<style scoped lang="less">
@primary: #8b5cf6;
@success: #22c55e;
@blue: #60a5fa;
@amber: #fbbf24;
@text-1: rgba(255, 255, 255, 0.95);
@text-2: rgba(255, 255, 255, 0.7);
@text-3: rgba(255, 255, 255, 0.45);
@bg: rgba(26, 18, 37, 0.6);
@border: rgba(139, 92, 246, 0.2);

.base-answer-block { width: 100%; display: flex; flex-direction: column; gap: 16px; }

.tp-toggle {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 10px 18px; background: rgba(139,92,246,0.1); border: 1px solid rgba(139,92,246,0.3);
  border-radius: 8px; cursor: pointer; transition: all 0.2s; align-self: flex-start;
  position: relative; overflow: hidden;
  &::before {
    content: ''; position: absolute; left: 0; bottom: 0; height: 3px;
    width: var(--progress, 0%); border-radius: 0 2px 2px 0;
    background: linear-gradient(90deg, #8b5cf6, #38bdf8);
    transition: width 0.5s ease;
  }
  &.done::before {
    background: linear-gradient(90deg, #22c55e, #4ade80);
  }
  &:hover { background: rgba(139,92,246,0.15); border-color: rgba(139,92,246,0.4); }
  &.active { background: rgba(139,92,246,0.15); border-color: @primary; }
  .tp-toggle-icon { font-size: 16px; }
  .tp-toggle-label { font-size: 14px; font-weight: 600; color: @text-1; }
  .tp-toggle-tokens { font-size: 11px; padding: 2px 8px; background: rgba(34,197,94,0.15); color: @success; border-radius: 4px; }
  .tp-toggle-arrow { display: flex; color: @text-3; font-size: 12px; }
}

.tp-panel {
  padding: 20px; background: @bg; border: 1px solid @border; border-radius: 12px;
  animation: slideDown 0.3s ease; overflow: hidden;
}

.tp-header {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid @border; flex-wrap: wrap;
  .tp-header-left { display: flex; align-items: center; gap: 8px; }
  .tp-header-icon { font-size: 18px; }
  .tp-header-title { font-size: 15px; font-weight: 700; color: @text-1; }
}
.tp-scenario-tag {
  padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: 600;
  background: rgba(59,130,246,0.15); color: @blue; border: 1px solid rgba(59,130,246,0.25);
}

.tp-progress {
  margin-bottom: 18px;
  .tp-progress-track { width: 100%; height: 5px; background: rgba(139,92,246,0.12); border-radius: 3px; overflow: hidden; }
  .tp-progress-fill {
    height: 100%; background: linear-gradient(90deg, #22c55e, #4ade80); border-radius: 3px;
    transition: width 0.6s cubic-bezier(0.4,0,0.2,1); position: relative;
    &::after { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent); animation: shimmer 1.5s ease-in-out infinite; }
    &.done { background: linear-gradient(90deg, #22c55e, #16a34a); &::after { animation: none; } }
  }
  .tp-progress-info { display: flex; justify-content: space-between; margin-top: 5px; font-size: 12px; color: @text-2; }
  .tp-progress-pct { font-weight: 600; color: @success; }
}

.tp-chain { display: flex; flex-direction: column; gap: 4px; }

.tp-step {
  display: flex; gap: 12px; opacity: 0.35; transition: opacity 0.3s;
  &.done { opacity: 1; .tp-step-dot { background: @success; box-shadow: 0 0 0 3px rgba(34,197,94,0.2); } }
  &.skipped { opacity: 0.55; .tp-step-dot { background: rgba(148,163,184,0.5); box-shadow: 0 0 0 3px rgba(148,163,184,0.15); } }
  &.loading { opacity: 0.8; .tp-step-dot { background: @primary; animation: pulse 1.5s infinite; } }
}
.tp-step-bar {
  display: flex; flex-direction: column; align-items: center; flex-shrink: 0; padding-top: 14px;
  .tp-step-dot { width: 10px; height: 10px; border-radius: 50%; background: rgba(139,92,246,0.4); border: 2px solid rgba(139,92,246,0.25); transition: all 0.3s; flex-shrink: 0; }
  .tp-step-line { width: 2px; flex: 1; min-height: 16px; background: linear-gradient(180deg, rgba(139,92,246,0.25), rgba(139,92,246,0.08)); margin-top: 6px; }
  .tp-dot-star { background: @amber !important; box-shadow: 0 0 0 3px rgba(251,191,36,0.25) !important; width: 12px; height: 12px; }
}
.tp-step:last-child .tp-step-line { display: none; }
.tp-step-body {
  flex: 1; min-width: 0; padding: 10px 14px 12px;
  background: rgba(139,92,246,0.04); border: 1px solid rgba(139,92,246,0.1);
  border-radius: 10px; transition: border-color 0.2s;
}
.tp-step.done .tp-step-body { border-color: rgba(34,197,94,0.15); }
.tp-step.loading .tp-step-body { border-color: rgba(139,92,246,0.25); }

.tp-step-head {
  display: flex; align-items: center; gap: 7px; padding: 4px 0;
  user-select: none; flex-wrap: wrap;
  &:hover .tp-step-expand { color: @primary; }
}
.tp-step-head:has(.tp-step-expand) { cursor: pointer; }
.tp-step-head.clickable { cursor: pointer; }
.tp-step-num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%; background: rgba(139,92,246,0.15);
  font-size: 11px; font-weight: 700; color: @primary; flex-shrink: 0;
  &.tp-num-star { background: rgba(251,191,36,0.2); color: @amber; }
}
.tp-step-emoji { font-size: 16px; flex-shrink: 0; }
.tp-step-name { font-size: 14px; font-weight: 600; color: @text-1; }
.tp-rag-phase {
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 9px; font-weight: 700; padding: 1px 6px; border-radius: 4px;
  background: rgba(139,92,246,0.15); color: @primary; border: 1px solid rgba(139,92,246,0.25);
  letter-spacing: 0.5px; line-height: 1.4; flex-shrink: 0;
}
.tp-help-icon { font-size: 12px; cursor: help; opacity: 0.45; transition: opacity 0.2s; margin-left: 2px; &:hover { opacity: 1; } }
.tp-step-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500;
  background: rgba(139,92,246,0.1); color: @text-3;
  &.tp-badge-green { background: rgba(34,197,94,0.15); color: @success; }
  &.tp-badge-blue { background: rgba(59,130,246,0.15); color: @blue; }
  &.tp-badge-amber { background: rgba(251,191,36,0.15); color: @amber; }
  &.tp-badge-dim { background: rgba(148,163,184,0.1); color: @text-3; }
}
.tp-step-status { margin-left: auto; font-size: 12px; color: @success; font-weight: 600; flex-shrink: 0;
  &.tp-status-loading {
    width: 18px; height: 18px; display: inline-block;
    border: 2.5px solid rgba(56, 189, 248, 0.25);
    border-top-color: #38bdf8;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  &.tp-status-skipped { color: @text-3; font-weight: 400; }
}
.tp-step-expand { font-size: 11px; color: @text-3; flex-shrink: 0; transition: color 0.15s; }

.tp-step-summary { margin-top: 8px; }
.tp-step-detail {
  margin-top: 10px; padding: 10px; background: rgba(0,0,0,0.1);
  border: 1px solid rgba(139,92,246,0.08); border-radius: 6px;
  animation: slideDown 0.2s ease;
}

/* 标签 */
.tp-tags-row { display: flex; flex-wrap: wrap; gap: 6px; }
.tp-tag {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 3px 10px; border-radius: 4px; font-size: 11px; font-weight: 500;
  &.tp-tag-blue { background: rgba(59,130,246,0.12); color: @blue; }
  &.tp-tag-purple { background: rgba(139,92,246,0.12); color: #c4b5fd; }
  &.tp-tag-green { background: rgba(34,197,94,0.12); color: @success; }
  &.tp-tag-amber { background: rgba(251,191,36,0.12); color: @amber; }
  &.tp-tag-dim { background: rgba(148,163,184,0.08); color: @text-3; }
}

/* 知识库命中芯片 */
.tp-kb-hits {
  display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px;
}

.tp-kb-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 500;
  background: rgba(139,92,246,0.06); border: 1px solid rgba(139,92,246,0.12); color: @text-3;
  transition: all 0.2s;
  &.active { background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.2); color: @text-2; }
  .tp-kb-count {
    display: inline-flex; align-items: center; justify-content: center;
    min-width: 16px; height: 16px; border-radius: 8px; font-size: 10px; font-weight: 700;
    background: rgba(34,197,94,0.2); color: @success; padding: 0 4px;
  }
  .tp-kb-miss { font-size: 10px; color: @text-3; font-style: italic; }
}

/* 流程可视化 */
.tp-flow-viz {
  margin-top: 8px; padding: 8px 10px;
  background: rgba(139,92,246,0.04); border: 1px solid rgba(139,92,246,0.1); border-radius: 6px;
  .tp-flow-title { font-size: 11px; font-weight: 600; color: @text-2; margin-bottom: 6px; }
}
.tp-flow-steps {
  display: flex; align-items: center; flex-wrap: wrap; gap: 2px;
  .tp-flow-node {
    font-size: 10px; padding: 2px 8px; border-radius: 4px;
    background: rgba(139,92,246,0.08); color: @text-2; font-weight: 500;
    em { font-style: normal; color: @text-3; font-size: 9px; }
    &.tp-flow-active { background: rgba(34,197,94,0.15); color: @success; font-weight: 700; }
  }
  .tp-flow-arrow { font-size: 10px; color: @text-3; }
}
.tp-flow-metrics {
  display: flex; gap: 10px; margin-top: 6px; font-size: 10px; color: @text-3;
  .metric-good { color: @success; font-weight: 600; }
  .metric-warn { color: @amber; font-weight: 600; }
}

/* KV列表 */
.tp-kv-list { display: flex; flex-direction: column; gap: 6px; }
.tp-kv { display: flex; align-items: center; gap: 8px; font-size: 12px; flex-wrap: wrap;
  .tp-kv-k { color: @text-2; min-width: 60px; flex-shrink: 0; font-weight: 600; }
  .tp-kv-v { display: flex; flex-wrap: wrap; gap: 4px; color: @text-1; align-items: center; }
}

/* RAG质量 */
.tp-rag-quality {
  display: flex; align-items: center; gap: 10px; padding: 6px 10px; margin-top: 6px;
  background: rgba(139,92,246,0.05); border: 1px solid rgba(139,92,246,0.12); border-radius: 6px; font-size: 11px;
  .tp-rq-score { color: @text-2; font-weight: 500; }
  .tp-rq-improve { color: @success; font-weight: 600; }
  .tp-rq-badge {
    margin-left: auto; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600;
    &.high { background: rgba(34,197,94,0.2); color: @success; }
    &.medium { background: rgba(59,130,246,0.2); color: @blue; }
    &.low { background: rgba(251,191,36,0.2); color: @amber; }
    &.very_low, &.none { background: rgba(239,68,68,0.2); color: #ef4444; }
  }
}

/* 检索结果 */
.tp-rg-list { display: flex; flex-direction: column; gap: 4px; }
.tp-rg-item {
  display: flex; align-items: center; gap: 8px; padding: 5px 10px;
  background: rgba(139,92,246,0.06); border-radius: 5px; font-size: 12px;
  .tp-rg-name { flex: 1; color: @text-2; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  &.tp-rg-doc { flex-direction: column; align-items: stretch; }
}
.tp-match-tag {
  font-size: 10px; padding: 1px 6px; border-radius: 3px; font-weight: 600; flex-shrink: 0;
  &.keyword { background: rgba(251,191,36,0.12); color: @amber; }
  &.substring { background: rgba(34,197,94,0.12); color: #22c55e; }
  &.token-fuzzy { background: rgba(168,85,247,0.12); color: #a855f7; }
  &.vector { background: rgba(59,130,246,0.12); color: @blue; }
}
.tp-rg-score {
  font-size: 11px; font-weight: 600; color: @success; padding: 1px 5px;
  background: rgba(34,197,94,0.12); border-radius: 3px; flex-shrink: 0;
  &.high { background: rgba(34,197,94,0.2); font-weight: 700; }
}
.tp-doc-source { font-size: 11px; color: @primary; font-weight: 500; display: flex; align-items: center; gap: 4px; }
.tp-doc-type { font-size: 10px; padding: 0 4px; border-radius: 3px; background: rgba(139,92,246,0.12); font-weight: 700; }
.tp-doc-text { font-size: 11px; color: @text-3; line-height: 1.4; margin-top: 2px; &.clickable { cursor: pointer; &:hover { color: @text-2; } } }
.tp-doc-expand-hint { display: inline-block; margin-left: 6px; font-size: 10px; color: @primary; opacity: 0.7; white-space: nowrap; }

/* 详情区块 */
.tp-detail-block {
  margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid rgba(139,92,246,0.08);
  &:last-child { margin-bottom: 0; padding-bottom: 0; border-bottom: none; }
}
.tp-detail-block-title { font-size: 12px; font-weight: 700; color: @primary; margin-bottom: 8px; }

/* 检索方法说明 */
.tp-retrieval-method {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 10px; margin-bottom: 8px;
  background: rgba(59,130,246,0.06); border: 1px solid rgba(59,130,246,0.12);
  border-radius: 5px; font-size: 11px;
  .tp-rm-icon { font-size: 12px; flex-shrink: 0; }
  .tp-rm-text { color: @text-2; line-height: 1.5; }
}

/* 自定义提示词注入状态 */
.tp-prompt-inject {
  display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 8px;
  .tp-inject-label { font-size: 11px; color: @text-3; font-weight: 600; margin-right: 2px; }
}
.tp-inject-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 500;
  background: rgba(148,163,184,0.08); border: 1px solid rgba(148,163,184,0.15); color: @text-3;
  transition: all 0.2s;
  &.injected { background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.2); color: @text-2; }
  .tp-inject-status {
    font-size: 10px; font-weight: 600; margin-left: 2px;
  }
  &.injected .tp-inject-status { color: @success; }
  &.empty .tp-inject-status { color: @text-3; font-style: italic; }
}

/* AntV G2 可视化配置 */
.tp-g2-config {
  display: flex; align-items: center; gap: 8px; margin-top: 6px;
  padding: 4px 10px; background: rgba(59,130,246,0.05); border: 1px solid rgba(59,130,246,0.12); border-radius: 4px; font-size: 11px; flex-wrap: wrap;
  .tp-g2-label { color: @text-3; font-weight: 600; }
  .tp-g2-dim { color: @text-2; padding: 1px 6px; background: rgba(139,92,246,0.08); border-radius: 3px; font-family: 'SF Mono', monospace; font-size: 10px; }
}

/* 提示词摘要 */
.tp-prompt-size {
  display: flex; align-items: center; gap: 8px; margin-top: 6px;
  padding: 4px 10px; background: rgba(139,92,246,0.05); border-radius: 4px; font-size: 11px;
  .tp-ps-label { color: @text-3; }
  .tp-ps-value { color: @text-2; font-weight: 600; font-family: 'SF Mono', monospace; }
  .tp-ps-model { margin-left: auto; padding: 1px 8px; background: rgba(139,92,246,0.12); color: @primary; border-radius: 10px; font-size: 10px; font-weight: 600; }
}

/* 推理框 */
.tp-reasoning {
  .tp-reasoning-label {
    font-size: 11px; font-weight: 600; color: @primary; text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;
  }
  .tp-reasoning-content {
    font-size: 13px; line-height: 1.7; color: @text-2;
    :deep(.markdown-body) { color: @text-2 !important; background: transparent !important;
      code { background: rgba(139,92,246,0.2) !important; color: @primary !important; padding: 2px 6px; border-radius: 4px; }
      pre { background: rgba(26,18,37,0.8) !important; border: 1px solid rgba(139,92,246,0.3); border-radius: 6px; padding: 12px;
        code { background: transparent !important; padding: 0; }
      }
    }
  }
}
.tp-code-preview {
  font-size: 12px; line-height: 1.6; color: @text-2; background: rgba(0,0,0,0.15);
  border: 1px solid rgba(139,92,246,0.15); border-radius: 6px; padding: 10px 12px; margin: 0;
  max-height: 300px; overflow-y: auto; white-space: pre-wrap; word-break: break-word;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
}
.tp-sql-display {
  font-size: 12px; line-height: 1.6; color: #c4b5fd; background: rgba(0,0,0,0.2);
  border: 1px solid rgba(139,92,246,0.2); border-radius: 6px; padding: 10px 12px; margin: 0;
  max-height: 200px; overflow-y: auto; white-space: pre-wrap; word-break: break-word;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
}
.tp-sql-preview {
  font-size: 11px; line-height: 1.5; color: @text-3; background: rgba(0,0,0,0.12);
  border: 1px solid rgba(139,92,246,0.1); border-radius: 4px; padding: 6px 10px; margin: 4px 0 0 0;
  max-height: 40px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
}
.tp-dots {
  display: inline-flex; gap: 3px; margin-left: 2px;
  span { width: 4px; height: 4px; border-radius: 50%; background: @primary; animation: dotBounce 1.4s ease-in-out infinite;
    &:nth-child(2) { animation-delay: 0.2s; }
    &:nth-child(3) { animation-delay: 0.4s; }
  }
}
.tp-kv-text-snippet {
  font-size: 11px; color: rgba(255,255,255,0.55); line-height: 1.5;
  max-height: 60px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
}

.answer-container { width: 100%; display: flex; flex-direction: column; gap: 14px; }

@keyframes slideDown { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
@keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
@keyframes dotBounce { 0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); } 40% { opacity: 1; transform: scale(1.2); } }

@media (max-width: 768px) {
  .tp-panel { padding: 14px; }
  .tp-step { gap: 10px; }
}

/* 引用来源卡片 */
.citation-bar {
  background: rgba(139,92,246,0.04); border: 1px solid rgba(139,92,246,0.12);
  border-radius: 10px; overflow: hidden;
}
.citation-header {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  cursor: pointer; user-select: none; transition: background 0.15s;
  &:hover { background: rgba(139,92,246,0.06); }
}
.citation-icon { font-size: 14px; flex-shrink: 0; }
.citation-summary { font-size: 12px; color: @text-2; font-weight: 500; flex: 1; min-width: 0; }
.citation-meta { font-size: 11px; color: @text-3; flex-shrink: 0; }
.citation-expand { font-size: 11px; color: @text-3; flex-shrink: 0; }
.citation-detail {
  padding: 0 14px 12px; display: flex; flex-direction: column; gap: 6px;
  animation: slideDown 0.2s ease;
}
.citation-card {
  padding: 8px 10px; background: rgba(0,0,0,0.1); border-radius: 6px;
  border-left: 3px solid rgba(139,92,246,0.3);
}
.cc-header {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 4px;
}
.cc-source { font-size: 12px; font-weight: 600; color: @text-1; }
.cc-type { font-size: 10px; padding: 1px 6px; background: rgba(59,130,246,0.12); color: @blue; border-radius: 3px; }
.cc-page { font-size: 10px; padding: 1px 6px; background: rgba(139,92,246,0.1); color: #c4b5fd; border-radius: 3px; }
.cc-section { font-size: 10px; color: @text-3; }
.cc-tag {
  font-size: 10px; padding: 1px 6px; background: rgba(139,92,246,0.08); color: @text-3; border-radius: 3px;
  &.cc-tag-green { background: rgba(34,197,94,0.12); color: @success; }
}
.cc-sim {
  margin-left: auto; font-size: 10px; font-weight: 600; padding: 1px 6px;
  background: rgba(34,197,94,0.12); color: @success; border-radius: 3px;
  &.high { background: rgba(34,197,94,0.2); font-weight: 700; }
}
.cc-sql {
  font-size: 11px; line-height: 1.5; color: #c4b5fd; background: rgba(0,0,0,0.15);
  border: 1px solid rgba(139,92,246,0.15); border-radius: 4px; padding: 6px 8px; margin: 4px 0 0;
  max-height: 80px; overflow-y: auto; white-space: pre-wrap; word-break: break-word;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
}
.cc-tables {
  display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px;
}
.cc-table-tag {
  font-size: 10px; padding: 1px 6px; background: rgba(59,130,246,0.1); color: @blue;
  border-radius: 3px; font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
}
.cc-text {
  font-size: 11px; color: @text-3; line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
</style>
