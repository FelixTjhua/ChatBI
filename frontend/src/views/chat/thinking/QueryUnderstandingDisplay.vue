<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

interface QueryUnderstandingData {
  // 查询重写相关
  original_query?: string
  rewritten_query?: string
  rewrite_applied?: boolean
  extracted_keywords?: string[]
  // 意图识别
  intent?: string
  intent_keywords?: string[]
  // 对话上下文（如果是多轮对话）
  dialogue_turn?: number
  context_references?: Array<{
    original: string
    resolved: string
    confidence: number
  }>
  // 数据源信息
  ds_type?: string
  ds_name?: string
  // 术语预取
  pre_terminology_count?: number
  terminology_expansions?: string[]
}

const props = withDefaults(defineProps<{
  data: QueryUnderstandingData
}>(), {
  data: () => ({})
})

const { t } = useI18n()

const safeData = computed(() => ({
  original_query: props.data?.original_query || '',
  rewritten_query: props.data?.rewritten_query || '',
  rewrite_applied: props.data?.rewrite_applied || false,
  extracted_keywords: props.data?.extracted_keywords || [],
  intent: props.data?.intent || 'data_query',
  intent_keywords: props.data?.intent_keywords || [],
  dialogue_turn: props.data?.dialogue_turn || 1,
  context_references: props.data?.context_references || [],
  ds_type: props.data?.ds_type || '',
  ds_name: props.data?.ds_name || '',
  pre_terminology_count: props.data?.pre_terminology_count || 0,
  terminology_expansions: props.data?.terminology_expansions || [],
}))

function getIntentLabel(intent: string): string {
  // PDF 数据源下，term_explanation 实际代表"文档问答"
  // 后端 PDF 路径统一使用 term_explanation 作为默认意图
  const isPdf = props.data?.ds_type === 'pdf'
  if (isPdf && (intent === 'term_explanation' || intent === 'fact_query' || intent === 'ambiguous_query')) {
    return t('query_understanding.intent_document_qa')
  }
  // 非PDF场景下 term_explanation 实际路由到 general_chat，显示应与路由一致
  const isNonPdfTermExplanation = !isPdf && intent === 'term_explanation'
  const map: Record<string, string> = {
    fact_query: t('query_understanding.intent_fact_query'),
    statistical_analysis: t('query_understanding.intent_statistical_analysis'),
    comparison_analysis: t('query_understanding.intent_comparison_analysis'),
    trend_analysis: t('query_understanding.intent_trend_analysis'),
    prediction: t('query_understanding.intent_prediction'),
    term_explanation: isNonPdfTermExplanation ? t('query_understanding.intent_general_chat') : t('query_understanding.intent_term_explanation'),
    follow_up: t('query_understanding.intent_follow_up'),
    ambiguous_query: t('query_understanding.intent_ambiguous_query'),
    irrelevant_query: t('query_understanding.intent_irrelevant_query'),
    document_qa: t('query_understanding.intent_document_qa'),
    // 兼容旧意图
    data_query: t('query_understanding.intent_fact_query'),
    analysis: t('query_understanding.intent_statistical_analysis'),
    general_chat: t('query_understanding.intent_general_chat'),
  }
  return map[intent] || intent
}

function getIntentIcon(intent: string): string {
  const isPdf = props.data?.ds_type === 'pdf'
  if (isPdf && (intent === 'term_explanation' || intent === 'fact_query' || intent === 'ambiguous_query')) {
    return '📄'
  }
  // 非PDF场景下 term_explanation 路由到 general_chat，使用对话图标
  const isNonPdfTermExplanation = !isPdf && intent === 'term_explanation'
  const icons: Record<string, string> = {
    fact_query: '🔎',
    statistical_analysis: '📊',
    comparison_analysis: '⚖️',
    trend_analysis: '📈',
    prediction: '🔮',
    term_explanation: isNonPdfTermExplanation ? '🗨️' : '📖',
    follow_up: '🔄',
    ambiguous_query: '❓',
    irrelevant_query: '💬',
    document_qa: '📄',
    // 兼容旧意图
    data_query: '🔎',
    analysis: '📊',
    general_chat: '🗨️',
  }
  return icons[intent] || '❓'
}

const hasContextReferences = computed(() => safeData.value.context_references.length > 0)
</script>

<template>
  <div class="query-understanding-display">
    <!-- 查询重写对比 -->
    <div class="rewrite-section">
      <div class="query-box original">
        <span class="box-label">{{ t('query_understanding.original') }}</span>
        <span class="box-content">{{ safeData.original_query }}</span>
      </div>
      <template v-if="safeData.rewrite_applied">
        <div class="rewrite-arrow">→</div>
        <div class="query-box rewritten">
          <span class="box-label">{{ t('query_understanding.rewritten') }}</span>
          <span class="box-content">{{ safeData.rewritten_query }}</span>
        </div>
      </template>
      <div v-else class="no-rewrite-hint">
        {{ t('query_understanding.no_rewrite') }}
      </div>
    </div>

    <!--
      提取关键词：已从默认展示中移除。
      原因：关键词是 QueryRewriter 内部的中间产物，用于驱动多路检索（expanded_queries），
      不是面向用户的展示信息。与"业务要素解析"并列展示时容易造成混淆
      （答辩老师会问"这两个有什么区别"），且关键词质量受 n-gram 切分影响，
      展示效果不佳（如"用饼图展"等碎片）。
      关键词的实际作用体现在步骤2的检索结果中，无需单独展示。
    -->

    <!-- 数据源信息 + 意图识别 -->
    <div v-if="safeData.intent" class="intent-line">
      <span class="intent-icon">{{ getIntentIcon(safeData.intent) }}</span>
      <span class="intent-label">{{ t('query_understanding.intent') }}:</span>
      <span class="intent-value">{{ getIntentLabel(safeData.intent) }}</span>
      <template v-if="safeData.intent_keywords.length > 0">
        <span class="intent-evidence-arrow">←</span>
        <span class="intent-evidence-label">{{ t('query_understanding.intent_evidence') }}:</span>
        <span v-for="(kw, i) in safeData.intent_keywords" :key="i" class="intent-keyword-tag">{{ kw }}</span>
      </template>
    </div>

    <!-- 术语预取 -->
    <div v-if="safeData.pre_terminology_count > 0" class="terminology-prefetch">
      <span class="section-label">📚 {{ t('query_understanding.terminology_prefetch') }}:</span>
      <span class="prefetch-count">{{ safeData.pre_terminology_count }}{{ t('query_understanding.terminology_hits') }}</span>
      <div v-if="safeData.terminology_expansions.length > 0" class="expansion-list">
        <span v-for="(exp, i) in safeData.terminology_expansions" :key="i" class="expansion-tag">{{ exp }}</span>
      </div>
    </div>

    <!--
      指代消解：已从默认展示中移除。
      原因：context_references 是 QueryRewriter 内部的中间产物，
      用于多轮对话中代词消解（如"这个"→具体实体），
      但 LLM 输出的 resolved 字段质量不稳定（如 "Current entities / 当前讨论的实体: 3, 2026"），
      展示效果差且容易引起困惑。指代消解的实际作用已体现在重写后的查询中，无需单独展示。
    -->
  </div>
</template>

<style scoped lang="less">
@primary: #8b5cf6;
@text-primary: rgba(255, 255, 255, 0.95);
@text-secondary: rgba(255, 255, 255, 0.7);
@text-muted: rgba(255, 255, 255, 0.5);
@success: #22c55e;

.query-understanding-display {
  padding: 14px;
  background: rgba(139, 92, 246, 0.05);
  border: 1px solid rgba(139, 92, 246, 0.15);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rewrite-section {
  display: flex;
  align-items: stretch;
  gap: 10px;
}

.query-box {
  flex: 1;
  padding: 10px 12px;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;

  &.original {
    background: rgba(100, 100, 100, 0.1);
    border: 1px solid rgba(150, 150, 150, 0.2);
  }
  &.rewritten {
    background: rgba(34, 197, 94, 0.08);
    border: 1px solid rgba(34, 197, 94, 0.2);
  }

  .box-label {
    font-size: 10px;
    color: @text-muted;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .box-content {
    font-size: 13px;
    color: @text-primary;
    line-height: 1.4;
  }
}

.rewrite-arrow {
  display: flex;
  align-items: center;
  color: @success;
  font-size: 18px;
  font-weight: 700;
  flex-shrink: 0;
}

.no-rewrite-hint {
  font-size: 11px;
  color: @text-muted;
  padding: 4px 10px;
  background: rgba(139, 92, 246, 0.08);
  border-radius: 4px;
  align-self: center;
}

.keywords-section {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;

  .section-label {
    font-size: 12px;
    color: @text-muted;
    flex-shrink: 0;
  }

  .keywords-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .keyword-tag {
    font-size: 11px;
    color: @text-secondary;
    background: rgba(139, 92, 246, 0.12);
    border: 1px solid rgba(139, 92, 246, 0.2);
    border-radius: 4px;
    padding: 2px 8px;
  }
}

.intent-line {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 4px 0 0;
  flex-wrap: wrap;

  .intent-icon {
    font-size: 14px;
  }
  .intent-label {
    color: @text-muted;
  }
  .intent-value {
    color: @text-secondary;
    font-weight: 500;
  }
  .intent-evidence-arrow {
    color: @text-muted;
    font-size: 11px;
    margin-left: 4px;
  }
  .intent-evidence-label {
    color: @text-muted;
    font-size: 11px;
  }
  .intent-keyword-tag {
    font-size: 10px;
    color: #fbbf24;
    background: rgba(251, 191, 36, 0.1);
    border: 1px solid rgba(251, 191, 36, 0.25);
    border-radius: 3px;
    padding: 1px 6px;
  }
}

.terminology-prefetch {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;

  .section-label {
    color: @text-muted;
    flex-shrink: 0;
  }
  .prefetch-count {
    color: @success;
    font-weight: 500;
  }
  .expansion-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .expansion-tag {
    font-size: 11px;
    color: @success;
    background: rgba(34, 197, 94, 0.1);
    border: 1px solid rgba(34, 197, 94, 0.2);
    border-radius: 4px;
    padding: 2px 8px;
  }
}

.references-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-label {
  font-size: 11px;
  color: @text-muted;
}

.ref-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ref-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: rgba(59, 130, 246, 0.06);
  border-radius: 4px;
  font-size: 12px;

  .ref-original {
    color: #fbbf24;
    font-style: italic;
  }
  .ref-arrow {
    color: @primary;
    font-weight: 700;
  }
  .ref-resolved {
    color: @success;
    flex: 1;
  }
  .ref-confidence {
    font-size: 10px;
    color: @text-muted;
    padding: 1px 6px;
    background: rgba(139, 92, 246, 0.1);
    border-radius: 8px;
  }
}
</style>
