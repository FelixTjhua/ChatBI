<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

interface CustomPromptMatch {
  name: string
  reason: 'all' | 'matched' | 'fallback'
  score?: number
}

interface CustomPromptInfo {
  type: string
  used: boolean
  empty: boolean
  content?: string
  count?: number
  total?: number
  matched?: CustomPromptMatch[]
}

interface PromptConstructionData {
  prompt_type?: string
  system_prompt_preview?: string
  user_prompt_preview?: string
  system_prompt_length?: number
  user_prompt_length?: number
  model_name?: string
  rag_components?: Record<string, boolean>
  component_counts?: Record<string, any>
  message_count?: number
  total_prompt_length?: number
  custom_prompts?: CustomPromptInfo[]
}

const props = withDefaults(defineProps<{
  data: PromptConstructionData
}>(), {
  data: () => ({})
})

const { t } = useI18n()

const safeData = computed(() => ({
  prompt_type: props.data?.prompt_type || 'unknown',
  system_prompt_preview: props.data?.system_prompt_preview || '',
  user_prompt_preview: props.data?.user_prompt_preview || '',
  system_prompt_length: props.data?.system_prompt_length || 0,
  user_prompt_length: props.data?.user_prompt_length || 0,
  model_name: props.data?.model_name || '',
  rag_components: props.data?.rag_components || {},
  component_counts: props.data?.component_counts || {},
  message_count: props.data?.message_count || 0,
  total_prompt_length: props.data?.total_prompt_length || 0,
  custom_prompts: props.data?.custom_prompts || [],
}))

const promptLengthFormatted = computed(() => {
  const len = safeData.value.total_prompt_length
  return len > 1000 ? `${(len / 1000).toFixed(1)}K` : `${len}`
})

function formatChars(n: number): string {
  const unit = t('thinking.chars')
  return n > 1000 ? `${(n / 1000).toFixed(1)}K ${unit}` : `${n} ${unit}`
}

/** 系统提示词 vs 用户提示词占比 */
const topLevelStructure = computed(() => {
  const total = safeData.value.total_prompt_length || 1
  const userLen = safeData.value.user_prompt_length || 0
  const sysLen = Math.max(total - userLen, 0)
  return {
    system: { chars: sysLen, percent: Math.round((sysLen / total) * 100) },
    user: { chars: userLen, percent: Math.round((userLen / total) * 100) },
  }
})

// ========== XML 内容提取工具 ==========

function extractXmlContent(tagName: string): string {
  const full = safeData.value.system_prompt_preview || ''
  if (!full) return ''
  const open = `<${tagName}>`, close = `</${tagName}>`
  const start = full.indexOf(open)
  if (start < 0) return ''
  const cStart = start + open.length
  const end = full.indexOf(close, cStart)
  return end < 0 ? full.slice(cStart).trim() : full.slice(cStart, end).trim()
}

function extractLastXmlContent(tagName: string): string {
  const full = safeData.value.system_prompt_preview || ''
  if (!full) return ''
  const open = `<${tagName}>`, close = `</${tagName}>`
  let lastStart = -1, pos = 0
  while (true) {
    const idx = full.indexOf(open, pos)
    if (idx < 0) break
    lastStart = idx
    pos = idx + open.length
  }
  if (lastStart < 0) return ''
  const cStart = lastStart + open.length
  const end = full.indexOf(close, cStart)
  return end < 0 ? full.slice(cStart).trim() : full.slice(cStart, end).trim()
}

// ========== 子组件检测（直接从 system_prompt_preview 检测，不依赖后端 metadata） ==========

/**
 * 系统提示词内部子组件分解
 *  核心不再依赖后端 rag_components/component_counts 判断是否命中
 * 而是直接从 system_prompt_preview（即实际发送给 LLM 的系统指令）中检测 XML 标签
 * 这样即使后端 metadata 因时序问题为 0，只要系统指令里有内容就能正确显示
 */
const systemSubComponents = computed(() => {
  const sysPreview = safeData.value.system_prompt_preview || ''
  const sysLen = topLevelStructure.value.system.chars || 1
  const cc = safeData.value.component_counts || {}
  const rc = safeData.value.rag_components || {}

  // --- 表结构 ---
  const schemaContent = extractLastXmlContent('m-schema') || extractXmlContent('schema')
  const schemaLen = cc.schema_length || (schemaContent ? schemaContent.length + 20 : 0)
  const schemaActive = schemaLen > 0 || rc.schema

  // --- 业务术语：优先使用后端精确值（raw_terminology_count），兜底从 XML 检测 ---
  let termCount = cc.terminology_count || 0
  let termLen = cc.terminology_char_length || 0
  if (termCount === 0 && sysPreview) {
    const formalMarker = '以下是正式的信息'
    const formalIdx = sysPreview.indexOf(formalMarker)
    if (formalIdx >= 0) {
      const formalSection = sysPreview.slice(formalIdx)
      const termMatches = formalSection.match(/<terminology>/g)
      if (termMatches && termMatches.length > 0) {
        termCount = termMatches.length
        const termBlock = extractLastXmlContent('terminologies')
        termLen = termBlock ? termBlock.length + 30 : termCount * 80
      }
    }
  }
  const termActive = termCount > 0 || (rc.terminologies === true)

  // --- SQL 示例：优先使用后端精确值 ---
  let sqlExCount = cc.sql_example_count || 0
  let sqlExLen = cc.sql_example_char_length || 0
  if (sqlExCount === 0 && sysPreview) {
    const sqlMatches = sysPreview.match(/<sql-example>/g)
    if (sqlMatches && sqlMatches.length > 0) {
      // 只计算"以下是正式的信息"之后的 sql-example，排除 <example> 中的示例
      const formalMarker2 = '以下是正式的信息'
      const formalIdx2 = sysPreview.indexOf(formalMarker2)
      if (formalIdx2 >= 0) {
        const formalSection2 = sysPreview.slice(formalIdx2)
        const formalSqlMatches = formalSection2.match(/<sql-example>/g)
        if (formalSqlMatches && formalSqlMatches.length > 0) {
          sqlExCount = formalSqlMatches.length
          const sqlBlock = extractXmlContent('sql-examples')
          sqlExLen = sqlBlock ? sqlBlock.length + 30 : sqlExCount * 200
        }
      }
    }
  }
  const sqlExActive = sqlExCount > 0 || (rc.sql_examples === true)

  // --- 文档片段（仅 PDF 数据源才可能有真实的文档片段注入） ---
  const docChunkCount = cc.doc_chunk_count || 0
  const docChunkLen = cc.doc_chunk_length || 0

  // --- 数据样本 ---
  const dataSampleCount = cc.data_sample_count || (sysPreview.includes('<data-sample>') ? 1 : 0)
  const dataSampleLen = cc.data_sample_length || (dataSampleCount > 0 ? (extractXmlContent('data-sample').length || 0) + 30 : 0)

  // --- 自定义提示词 ---
  const cpList = safeData.value.custom_prompts || []
  const cpDeduped: typeof cpList = []
  const cpSeenTypes = new Set<string>()
  for (const cp of cpList) {
    if (!cpSeenTypes.has(cp.type)) { cpSeenTypes.add(cp.type); cpDeduped.push(cp) }
  }
  const hasAnyRules = cpDeduped.some(cp => !cp.empty)
  const hasMatchedRules = cpDeduped.some(cp => cp.used)
  const customLen = hasMatchedRules ? (cc.custom_prompt_length || 300) : 0

  // --- 基础指令 = 总长 - 已知子组件 ---
  const knownLen = schemaLen + termLen + sqlExLen + docChunkLen + dataSampleLen + customLen
  const baseInstructionLen = Math.max(sysLen - knownLen, 100)

  const parts: Array<{
    key: string; label: string; chars: number; percent: number
    color: string; active: boolean; detail: string
  }> = []

  // 系统指令（Instruction + Rules + SQL-Generation-Process + example + db-engine + 响应要求）
  parts.push({
    key: 'base_instruction', label: t('prompt_construction.part_instruction'),
    chars: baseInstructionLen, percent: Math.round((baseInstructionLen / sysLen) * 100),
    color: '#a78bfa', active: true, detail: t('prompt_construction.part_instruction_detail'),
  })

  // 表结构
  if (schemaActive) {
    parts.push({
      key: 'schema', label: t('prompt_construction.comp_schema'),
      chars: schemaLen, percent: Math.round((schemaLen / sysLen) * 100),
      color: '#60a5fa', active: true, detail: schemaLen > 0 ? formatChars(schemaLen) : t('prompt_construction.method_inject'),
    })
  }

  // 业务术语（PDF文档问答不需要商业术语库，不显示此行）
  // 架构设计：PDF = 非结构化文档 → 纯RAG文档问答，COMPONENT_MATRIX 中 terminology=False
  // Fix：未命中时也不显示，与步骤2知识检索保持一致（CSV/Excel/Database同步）
  const isPdfDocQA = sysPreview.includes('<document-knowledge>') && !sysPreview.includes('<m-schema>')
  if (!isPdfDocQA && termActive) {
    parts.push({
      key: 'terminologies', label: t('prompt_construction.comp_terminologies'),
      chars: termLen, percent: Math.round((termLen / sysLen) * 100),
      color: '#22c55e', active: true,
      detail: termCount > 0 ? `${termCount}` + t('prompt_construction.items_injected') : t('prompt_construction.method_vector'),
    })
  }

  // SQL 示例（仅 SQL 生成场景显示，分析/预测/直接回答/PDF 文档问答不显示）
  const isSqlPath = safeData.value.prompt_type === 'sql_generation' || (sysPreview.includes('<m-schema>') && sysPreview.includes('<Info>'))
  if (isSqlPath && sqlExActive) {
    parts.push({
      key: 'sql_examples', label: t('prompt_construction.comp_sql_examples'),
      chars: sqlExLen, percent: Math.round((sqlExLen / sysLen) * 100),
      color: '#06b6d4', active: true,
      detail: sqlExCount > 0 ? `${sqlExCount}` + t('prompt_construction.items_injected') : t('prompt_construction.method_vector'),
    })
  }

  // 文档片段
  if (docChunkCount > 0 || rc.document_chunks) {
    parts.push({
      key: 'document_chunks', label: t('prompt_construction.comp_document_chunks'),
      chars: docChunkLen, percent: Math.round((docChunkLen / sysLen) * 100),
      color: '#f97316', active: true, detail: `${docChunkCount}` + t('prompt_construction.items_injected'),
    })
  }

  // 数据样本（从数据源查询的真实样本数据）
  if (dataSampleCount > 0 || rc.data_sample) {
    parts.push({
      key: 'data_sample', label: t('prompt_construction.comp_data_sample'),
      chars: dataSampleLen, percent: Math.round((dataSampleLen / sysLen) * 100),
      color: '#10b981', active: true, detail: `${dataSampleCount}` + t('prompt_construction.tables_sampled'),
    })
  }

  // 自定义提示词
  if (hasMatchedRules) {
    // 动态生成注入方式描述：根据实际匹配的 reason 类型
    const allMatched = cpDeduped.flatMap(cp => (cp.matched || []).filter((m: any) => m.reason !== 'not_matched' && m.reason !== 'budget_exceeded'))
    const hasIntent = allMatched.some((m: any) => m.reason === 'intent_inject')
    const methodDetail = hasIntent ? t('thinking.prompt_match_intent') : t('prompt_construction.method_keyword')
    parts.push({
      key: 'custom_prompt', label: t('prompt_construction.comp_custom_prompt'),
      chars: customLen, percent: Math.round((customLen / sysLen) * 100),
      color: '#fbbf24', active: true, detail: methodDetail,
    })
  }
  // Fix：自定义提示词未命中时不再显示（移除 hasAnyRules 分支）

  // 对话上下文（独立 SystemMessage，但逻辑上属于系统提示词的子组件）
  const dialogueActive = rc.dialogue_context === true
  if (dialogueActive) {
    const dialogueText = cc.dialogue_context_text || ''
    const dialogueLen = dialogueText ? dialogueText.length : 80
    parts.push({
      key: 'dialogue_context', label: t('prompt_construction.comp_dialogue'),
      chars: dialogueLen, percent: Math.round((dialogueLen / sysLen) * 100),
      color: '#f472b6', active: true, detail: t('prompt_construction.method_context'),
    })
  }

  // 百分比归一化：确保所有子组件百分比之和 = 100%
  const totalChars = parts.reduce((sum, p) => sum + p.chars, 0) || 1
  for (const p of parts) {
    p.percent = p.active ? Math.round((p.chars / totalChars) * 100) : 0
  }
  // 修正舍入误差：将差值加到最大的组件上
  const activeTotal = parts.reduce((sum, p) => sum + p.percent, 0)
  if (activeTotal !== 100 && parts.length > 0) {
    const largest = parts.reduce((a, b) => a.chars > b.chars ? a : b)
    largest.percent += (100 - activeTotal)
  }

  return parts
})

// ========== 展开状态 ==========
const expandedSystem = ref(false)
const expandedUser = ref(false)
const expandedUserPrompt = ref(false)
const expandedSubLegend = ref<Record<string, boolean>>({})

function toggleSubLegend(key: string) {
  expandedSubLegend.value[key] = !expandedSubLegend.value[key]
}

// ========== 各子组件展开内容 ==========

const injectedTerminologies = computed(() => safeData.value.component_counts?.injected_terminologies || [])
const injectedSqlExamples = computed(() => safeData.value.component_counts?.injected_sql_examples || [])

const schemaContent = computed(() => extractLastXmlContent('m-schema') || extractXmlContent('schema') || '')
const terminologiesContent = computed(() => extractLastXmlContent('terminologies'))
const sqlExamplesContent = computed(() => {
  const content = extractXmlContent('sql-examples')
  if (content) return content
  const full = safeData.value.system_prompt_preview || ''
  const firstIdx = full.indexOf('<sql-example>')
  if (firstIdx < 0) return ''
  const lastIdx = full.lastIndexOf('</sql-example>')
  return lastIdx < 0 ? full.slice(firstIdx).trim() : full.slice(firstIdx, lastIdx + '</sql-example>'.length).trim()
})
const docChunksContent = computed(() => extractXmlContent('document-knowledge'))
const dataSampleContent = computed(() => extractXmlContent('data-sample'))

/** 基础指令内容：Instruction + Rules + SQL-Generation-Process + example + db-engine + 响应要求 */
const baseInstructionContent = computed(() => {
  const full = safeData.value.system_prompt_preview || ''
  if (!full) return ''
  const parts: string[] = []
  const instruction = extractXmlContent('Instruction')
  if (instruction) parts.push(`<Instruction>\n${instruction}\n</Instruction>`)
  const rules = extractXmlContent('Rules')
  if (rules) parts.push(`<Rules>\n${rules}\n</Rules>`)
  const process = extractXmlContent('SQL-Generation-Process')
  if (process) parts.push(`<SQL-Generation-Process>\n${process}\n</SQL-Generation-Process>`)
  // example 块
  const exampleContent = extractXmlContent('example')
  if (exampleContent) parts.push(`<example>\n${exampleContent.slice(0, 500)}...\n</example>`)
  // db-engine
  const dbEngine = extractXmlContent('db-engine')
  if (dbEngine) parts.push(`<db-engine>${dbEngine.trim()}</db-engine>`)
  // 响应要求
  const respIdx = full.indexOf('### 响应要求')
  if (respIdx >= 0) parts.push(full.slice(respIdx).trim())
  if (parts.length > 0) return parts.join('\n\n')
  // 兜底
  const infoIdx = full.indexOf('<Info>')
  if (infoIdx > 0) return full.slice(0, infoIdx).trim()
  return full.length > 800 ? full.slice(0, 800) + '...' : full
})

const needExpandBaseInstruction = computed(() => baseInstructionContent.value.length > 500)
const expandedBaseInstruction = ref(false)
const baseInstructionDisplay = computed(() => {
  const content = baseInstructionContent.value
  if (!content) return ''
  return (expandedBaseInstruction.value || content.length <= 500) ? content : content.slice(0, 500) + '...'
})

// 对话上下文（独立 SystemMessage）
const dialogueContextContent = computed(() => safeData.value.component_counts?.dialogue_context_text || '')

// 用户提示词
const needExpandUserPrompt = computed(() => (safeData.value.user_prompt_preview?.length || 0) > 500)
const userPromptDisplay = computed(() => {
  const full = safeData.value.user_prompt_preview || ''
  if (!full) return ''
  return (expandedUserPrompt.value || full.length <= 500) ? full : full.slice(0, 500) + '...'
})

// 自定义提示词匹配详情
function getMatchReasonText(reason: string): string {
  const map: Record<string, string> = {
    all: t('thinking.prompt_match_all'),
    matched: t('thinking.prompt_match_hit'),
    fallback: t('thinking.prompt_match_fallback'),
    global: t('thinking.prompt_match_global'),
    not_matched: t('thinking.prompt_match_miss'),
    budget_exceeded: t('thinking.prompt_match_budget_exceeded'),
    always_inject: t('thinking.prompt_match_global'),
    keyword_match: t('thinking.prompt_match_hit'),
    intent_inject: t('thinking.prompt_match_intent'),
  }
  return map[reason] || reason
}
const relevantCustomPrompts = computed(() => (safeData.value.custom_prompts || []).filter(cp => cp.used))

</script>

<template>
  <div class="prompt-construction-display">
    <!-- 顶部：模型 + 总长度 -->
    <div class="top-bar">
      <span v-if="safeData.model_name" class="model-tag">{{ safeData.model_name }}</span>
      <div class="top-stats">
        <span class="stat">{{ promptLengthFormatted }} {{ t('thinking.chars') }}</span>
      </div>
    </div>

    <!-- 提示词结构组成 -->
    <div class="structure-section">
      <div class="structure-title">{{ t('prompt_construction.injected_components') }}</div>

      <!-- 占比条：System Prompt vs User Prompt -->
      <div class="structure-bar">
        <div class="bar-segment" :style="{ width: Math.max(topLevelStructure.system.percent, 3) + '%', backgroundColor: '#8b5cf6' }"></div>
        <div v-if="topLevelStructure.user.chars > 0" class="bar-segment" :style="{ width: Math.max(topLevelStructure.user.percent, 3) + '%', backgroundColor: '#38bdf8' }"></div>
      </div>

      <!-- 系统提示词行 -->
      <div class="legend-item clickable" @click="expandedSystem = !expandedSystem">
        <span class="legend-dot" style="background-color: #8b5cf6"></span>
        <span class="legend-label">{{ t('prompt_construction.system_prompt_label') }}</span>
        <span class="legend-detail">{{ formatChars(topLevelStructure.system.chars) }}</span>
        <span class="legend-percent">{{ topLevelStructure.system.percent }}%</span>
        <span class="legend-expand">{{ expandedSystem ? '▾' : '▸' }}</span>
      </div>

      <!-- 系统提示词展开：子组件分解 -->
      <div v-if="expandedSystem" class="legend-expand-content">
        <!-- 子组件占比条 -->
        <div class="sub-bar">
          <div v-for="sub in systemSubComponents.filter(s => s.active)" :key="sub.key" class="bar-segment"
            :style="{ width: Math.max(sub.percent, 3) + '%', backgroundColor: sub.color }"></div>
        </div>
        <!-- 子组件图例 -->
        <div class="sub-legend">
          <template v-for="sub in systemSubComponents" :key="sub.key">
            <div class="legend-item clickable sub" :class="{ inactive: !sub.active }" @click="toggleSubLegend(sub.key)">
              <span class="legend-dot" :style="{ backgroundColor: sub.color }"></span>
              <span class="legend-label">{{ sub.label }}</span>
              <span class="legend-detail">{{ sub.detail }}</span>
              <span class="legend-percent">{{ sub.active ? sub.percent + '%' : '—' }}</span>
              <span class="legend-expand">{{ expandedSubLegend[sub.key] ? '▾' : '▸' }}</span>
            </div>

            <!-- 系统指令展开 -->
            <div v-if="expandedSubLegend['base_instruction'] && sub.key === 'base_instruction'" class="legend-expand-content nested">
              <div v-if="baseInstructionContent">
                <div class="preview-header">
                  <span class="preview-label">{{ t('prompt_construction.part_instruction') }}</span>
                  <span v-if="needExpandBaseInstruction" class="expand-btn" @click.stop="expandedBaseInstruction = !expandedBaseInstruction">
                    {{ expandedBaseInstruction ? t('prompt_construction.collapse') : t('prompt_construction.expand') }}
                  </span>
                </div>
                <div class="preview-body system" :class="{ expanded: expandedBaseInstruction }">{{ baseInstructionDisplay }}</div>
              </div>
            </div>
            <!-- 表结构展开 -->
            <div v-if="expandedSubLegend['schema'] && sub.key === 'schema'" class="legend-expand-content nested">
              <div v-if="schemaContent" class="preview-body system" style="max-height: 200px;">{{ schemaContent }}</div>
              <div v-else class="legend-expand-hint">{{ t('prompt_construction.schema_expand_hint') }}</div>
            </div>
            <!-- 术语展开 -->
            <div v-if="expandedSubLegend['terminologies'] && sub.key === 'terminologies'" class="legend-expand-content nested">
              <div v-if="injectedTerminologies.length > 0" class="legend-detail-list">
                <template v-for="(item, i) in injectedTerminologies" :key="'t-'+i">
                  <!-- 新格式：{word, synonyms} 分组结构 -->
                  <div v-if="typeof item === 'object' && item.word" class="legend-detail-item term">
                    {{ item.word }}
                    <span v-if="item.synonyms && item.synonyms.length" class="term-synonyms">（{{ item.synonyms.join('、') }}）</span>
                  </div>
                  <!-- 兼容旧格式：纯字符串 -->
                  <div v-else class="legend-detail-item term">{{ item }}</div>
                </template>
              </div>
              <div v-if="terminologiesContent" class="preview-body system" style="max-height: 200px; margin-top: 6px;">{{ terminologiesContent }}</div>
              <div v-else-if="!injectedTerminologies.length" class="legend-expand-hint">{{ t('prompt_construction.term_hint_old_record') }}</div>
            </div>
            <!-- SQL示例展开 -->
            <div v-if="expandedSubLegend['sql_examples'] && sub.key === 'sql_examples'" class="legend-expand-content nested">
              <div v-if="injectedSqlExamples.length > 0" class="legend-detail-list">
                <div v-for="(name, i) in injectedSqlExamples" :key="'s-'+i" class="legend-detail-item sql">{{ name }}</div>
              </div>
              <div v-if="sqlExamplesContent" class="preview-body system" style="max-height: 200px; margin-top: 6px;">{{ sqlExamplesContent }}</div>
              <div v-else-if="!injectedSqlExamples.length" class="legend-expand-hint">{{ t('prompt_construction.sql_example_hint_old_record') }}</div>
            </div>
            <!-- 文档片段展开 -->
            <div v-if="expandedSubLegend['document_chunks'] && sub.key === 'document_chunks'" class="legend-expand-content nested">
              <div v-if="docChunksContent" class="preview-body system" style="max-height: 200px;">{{ docChunksContent }}</div>
              <div v-else class="legend-expand-hint">{{ t('prompt_construction.doc_chunks_expand_hint') }}</div>
            </div>
            <!-- 数据样本展开 -->
            <div v-if="expandedSubLegend['data_sample'] && sub.key === 'data_sample'" class="legend-expand-content nested">
              <div v-if="dataSampleContent" class="preview-body system" style="max-height: 200px;">{{ dataSampleContent }}</div>
              <div v-else class="legend-expand-hint">{{ t('prompt_construction.data_sample_expand_hint') }}</div>
            </div>
            <!-- 自定义提示词展开 -->
            <div v-if="expandedSubLegend['custom_prompt'] && sub.key === 'custom_prompt'" class="legend-expand-content nested">
              <template v-if="relevantCustomPrompts.length > 0">
                <div v-for="(cp, ci) in relevantCustomPrompts" :key="'cp-'+ci" class="match-details">
                  <div class="match-group-title">{{ t('prompt_construction.type_match_count', { type: cp.type, count: cp.count, total: cp.total }) }}</div>
                  <div v-for="(m, mi) in (cp.matched || []).filter(x => x.reason !== 'not_matched')" :key="'m-'+mi" class="match-row">
                    <span class="match-name">{{ m.name }}</span>
                    <span class="match-reason" :class="m.reason">{{ getMatchReasonText(m.reason) }}</span>
                    <span v-if="m.score !== undefined && m.score > 0 && m.reason !== 'always_inject' && m.reason !== 'intent_inject'" class="match-score">{{ (m.score * 100).toFixed(0) }}%</span>
                  </div>
                </div>
              </template>
              <div v-else class="legend-expand-hint">{{ t('prompt_construction.custom_prompt_no_trigger_hint') }}</div>
            </div>
            <!-- 对话上下文展开 -->
            <div v-if="expandedSubLegend['dialogue_context'] && sub.key === 'dialogue_context'" class="legend-expand-content nested">
              <div v-if="dialogueContextContent" class="preview-body system" style="max-height: 200px;">{{ dialogueContextContent }}</div>
              <div v-else class="legend-expand-hint">{{ t('prompt_construction.method_context') }}</div>
            </div>
          </template>
        </div>
      </div>

      <!-- 用户提示词行 -->
      <div v-if="topLevelStructure.user.chars > 0" class="legend-item clickable" @click="expandedUser = !expandedUser">
        <span class="legend-dot" style="background-color: #38bdf8"></span>
        <span class="legend-label">{{ t('prompt_construction.user_prompt_label') }}</span>
        <span class="legend-detail">{{ t('prompt_construction.user_prompt_hint') }}</span>
        <span class="legend-percent">{{ topLevelStructure.user.percent }}%</span>
        <span class="legend-expand">{{ expandedUser ? '▾' : '▸' }}</span>
      </div>
      <div v-if="expandedUser && safeData.user_prompt_preview" class="legend-expand-content">
        <div class="preview-header">
          <span class="preview-label">{{ t('prompt_construction.user_prompt_label') }}</span>
          <span v-if="needExpandUserPrompt" class="expand-btn" @click.stop="expandedUserPrompt = !expandedUserPrompt">
            {{ expandedUserPrompt ? t('prompt_construction.collapse') : t('prompt_construction.expand') }}
          </span>
        </div>
        <div class="preview-body user" :class="{ expanded: expandedUserPrompt }">{{ userPromptDisplay }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="less">
@primary: #8b5cf6;
@text-primary: rgba(255, 255, 255, 0.95);
@text-secondary: rgba(255, 255, 255, 0.7);
@text-muted: rgba(255, 255, 255, 0.45);
@success: #22c55e;
@blue: #60a5fa;
@amber: #fbbf24;

.prompt-construction-display { display: flex; flex-direction: column; gap: 14px; }

.top-bar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.model-tag { padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; background: rgba(139, 92, 246, 0.12); color: @primary; border: 1px solid rgba(139, 92, 246, 0.2); }
.top-stats { margin-left: auto; display: flex; gap: 10px; align-items: center; }
.stat { font-size: 11px; color: @text-muted; &.compressed { color: @success; font-weight: 600; } }

.structure-section { padding: 12px; background: rgba(139, 92, 246, 0.03); border: 1px solid rgba(139, 92, 246, 0.1); border-radius: 8px; }
.structure-title { font-size: 12px; font-weight: 600; color: @text-primary; margin-bottom: 10px; }

.structure-bar, .sub-bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden; background: rgba(255, 255, 255, 0.05); margin-bottom: 10px; gap: 1px; }
.sub-bar { height: 6px; margin-bottom: 8px; }
.bar-segment { height: 100%; min-width: 4px; border-radius: 2px; transition: width 0.4s ease; opacity: 0.85; &:hover { opacity: 1; } }

.legend-item { display: flex; align-items: center; gap: 8px; font-size: 12px; padding: 4px 0; &.inactive { opacity: 0.5; .legend-dot { opacity: 0.4; } } &.sub { font-size: 11px; padding: 3px 0; } }
.legend-dot { width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }
.legend-label { color: @text-primary; font-weight: 500; min-width: 70px; }
.legend-detail { color: @text-muted; font-size: 11px; flex: 1; }
.legend-percent { color: @text-secondary; font-size: 11px; font-weight: 600; font-variant-numeric: tabular-nums; min-width: 32px; text-align: right; }
.legend-expand { font-size: 11px; color: @text-muted; flex-shrink: 0; margin-left: 4px; transition: color 0.15s; }

.legend-item.clickable { cursor: pointer; border-radius: 4px; padding: 4px 6px; margin: 0 -6px; transition: background 0.15s; &:hover { background: rgba(139, 92, 246, 0.06); .legend-expand { color: @primary; } } }

.legend-expand-content { padding: 8px 12px 8px 16px; margin: 2px 0 4px 0; background: rgba(139, 92, 246, 0.03); border-left: 2px solid rgba(139, 92, 246, 0.15); border-radius: 0 6px 6px 0; animation: slideDown 0.2s ease; &.nested { margin-left: 8px; border-left-color: rgba(139, 92, 246, 0.1); } }

.sub-legend { display: flex; flex-direction: column; gap: 3px; }
.legend-expand-hint { font-size: 11px; color: @text-muted; line-height: 1.5; }

.legend-detail-list { display: flex; flex-wrap: wrap; gap: 6px; padding: 6px 0 2px 0; }
.legend-detail-item { font-size: 11px; padding: 3px 10px; border-radius: 4px; font-weight: 500; &.term { background: rgba(34, 197, 94, 0.1); color: @success; .term-synonyms { font-weight: 400; opacity: 0.7; font-size: 10px; } } &.sql { background: rgba(6, 182, 212, 0.1); color: #06b6d4; } }

@keyframes slideDown { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }

.match-details { padding-top: 8px; margin-top: 8px; border-top: 1px solid rgba(139, 92, 246, 0.08); }
.match-group-title { font-size: 11px; font-weight: 600; color: @primary; padding: 3px 0; }
.match-row { display: flex; align-items: center; gap: 8px; padding: 5px 10px; background: rgba(139, 92, 246, 0.04); border-radius: 4px; margin-bottom: 3px; font-size: 11px;
  .match-name { flex: 1; color: @text-primary; font-weight: 500; }
  .match-reason { padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: 500;
    &.all { background: rgba(59, 130, 246, 0.12); color: @blue; }
    &.matched, &.keyword_match { background: rgba(34, 197, 94, 0.12); color: @success; }
    &.fallback { background: rgba(251, 191, 36, 0.12); color: @amber; }
    &.global, &.always_inject { background: rgba(139, 92, 246, 0.12); color: @primary; }
    &.intent_inject { background: rgba(59, 130, 246, 0.12); color: @blue; }
    &.not_matched { background: rgba(255, 255, 255, 0.06); color: @text-muted; }
    &.budget_exceeded { background: rgba(249, 115, 22, 0.12); color: #f97316; }
  }
  .match-score { font-size: 10px; color: @primary; font-weight: 600; }
}

.preview-header { display: flex; align-items: center; gap: 8px; }
.preview-label { font-size: 10px; font-weight: 700; color: @text-muted; text-transform: uppercase; letter-spacing: 0.8px; }
.expand-btn { margin-left: auto; font-size: 11px; color: @primary; cursor: pointer; padding: 2px 8px; border-radius: 4px; background: rgba(139, 92, 246, 0.08); transition: all 0.15s; &:hover { background: rgba(139, 92, 246, 0.15); } }

.preview-body { padding: 10px 12px; border-radius: 6px; font-size: 11px; line-height: 1.6; font-family: 'SF Mono', 'Fira Code', monospace; white-space: pre-wrap; word-break: break-all; max-height: 160px; overflow-y: auto; transition: max-height 0.3s ease;
  &.expanded { max-height: 600px; }
  &.system { background: rgba(139, 92, 246, 0.06); border: 1px solid rgba(139, 92, 246, 0.12); color: @text-secondary; }
  &.user { background: rgba(59, 130, 246, 0.06); border: 1px solid rgba(59, 130, 246, 0.12); color: @text-secondary; }
}
</style>
