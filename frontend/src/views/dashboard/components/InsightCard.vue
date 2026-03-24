<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ChartComponent from '@/views/chat/component/ChartComponent.vue'
import md from '@/utils/markdown.ts'
import 'highlight.js/styles/github-dark.min.css'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    id: string | number
    /** card type: chart | data_table | analysis | prediction | document_qa */
    cardType: string
    propValue: any
  }>(),
  { propValue: () => ({}) }
)

const cardType = computed(() => props.cardType || props.propValue?.cardType || 'chart')
const question = computed(() => props.propValue?.question || '')

// chart props
const chartType = computed(() => props.propValue?.chartType || 'bar')
const chartData = computed(() => props.propValue?.data || [])
const columns = computed(() => props.propValue?.columns || [])
const xAxis = computed(() => props.propValue?.xAxis || [])
const yAxis = computed(() => props.propValue?.yAxis || [])
const series = computed(() => props.propValue?.series || [])

// data table props
const tableFields = computed(() => props.propValue?.fields || [])
const tableData = computed(() => props.propValue?.data || [])
const sql = computed(() => props.propValue?.sql || '')

// analysis / prediction text — render markdown to HTML
const content = computed(() => {
  const raw = props.propValue?.content || ''
  if (!raw) return ''
  // 移除 <think> 标签
  const cleaned = raw.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
  if (!cleaned) return ''
  return md.render(cleaned)
})

// document QA
const docSources = computed(() => props.propValue?.sources || [])

// intent tag
const intentTag = computed(() => {
  const map: Record<string, string> = {
    chart: t('dashboard.type_chart'),
    data_table: t('dashboard.type_data_table'),
    analysis: t('dashboard.type_analysis'),
    prediction: t('dashboard.type_prediction'),
    document_qa: t('dashboard.type_document_qa'),
  }
  return map[cardType.value] || cardType.value
})

const intentColor = computed(() => {
  const map: Record<string, string> = {
    chart: '#8b5cf6',
    data_table: '#3b82f6',
    analysis: '#10b981',
    prediction: '#f59e0b',
    document_qa: '#ec4899',
  }
  return map[cardType.value] || '#8b5cf6'
})
</script>

<template>
  <div class="insight-card" :class="`insight-card--${cardType}`">
    <div class="insight-card__type-bar">
      <span class="insight-card__tag" :style="{ background: intentColor + '22', color: intentColor, borderColor: intentColor + '44' }">
        {{ intentTag }}
      </span>
      <span v-if="question" class="insight-card__question">{{ question }}</span>
    </div>

    <!-- 图表卡片 -->
    <div v-if="cardType === 'chart'" class="insight-card__body">
      <ChartComponent
        :id="id"
        :type="chartType"
        :data="chartData"
        :columns="columns"
        :x="xAxis"
        :y="yAxis"
        :series="series"
      />
    </div>

    <!-- 数据表卡片 -->
    <div v-else-if="cardType === 'data_table'" class="insight-card__body insight-card__table-body">
      <div v-if="sql" class="insight-card__sql">
        <code>{{ sql }}</code>
      </div>
      <div class="insight-card__table-wrap">
        <table class="insight-card__table">
          <thead>
            <tr>
              <th v-for="f in tableFields" :key="f">{{ f }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in tableData.slice(0, 50)" :key="idx">
              <td v-for="f in tableFields" :key="f">{{ row[f] ?? '' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="tableData.length > 50" class="insight-card__more">
          {{ t('dashboard.showing_rows', { shown: 50, total: tableData.length }) }}
        </div>
      </div>
    </div>

    <!-- 分析卡片 -->
    <div v-else-if="cardType === 'analysis'" class="insight-card__body insight-card__text-body">
      <div v-if="propValue?.chartType" class="insight-card__mini-chart">
        <ChartComponent
          :id="`${id}-mini`"
          :type="chartType"
          :data="chartData"
          :columns="columns"
          :x="xAxis"
          :y="yAxis"
          :series="series"
        />
      </div>
      <div class="insight-card__content markdown-body md-render-container" v-dompurify-html="content"></div>
    </div>

    <!-- 预测卡片 -->
    <div v-else-if="cardType === 'prediction'" class="insight-card__body insight-card__text-body">
      <div v-if="propValue?.chartType" class="insight-card__mini-chart">
        <ChartComponent
          :id="`${id}-pred`"
          :type="chartType"
          :data="chartData"
          :columns="columns"
          :x="xAxis"
          :y="yAxis"
          :series="series"
        />
      </div>
      <div class="insight-card__content markdown-body md-render-container" v-dompurify-html="content"></div>
    </div>

    <!-- 文档问答卡片 -->
    <div v-else-if="cardType === 'document_qa'" class="insight-card__body insight-card__text-body">
      <div class="insight-card__content markdown-body md-render-container" v-dompurify-html="content"></div>
      <div v-if="docSources.length" class="insight-card__sources">
        <div class="insight-card__sources-title">{{ t('dashboard.sources') }}</div>
        <div v-for="(src, idx) in docSources" :key="idx" class="insight-card__source-item">
          <span class="source-badge">{{ src.source_name || src.filename || 'PDF' }}</span>
          <span v-if="src.page_number" class="source-page">P{{ src.page_number }}</span>
          <span v-if="src.section_title" class="source-section">{{ src.section_title }}</span>
        </div>
      </div>
    </div>

    <!-- 兜底 -->
    <div v-else class="insight-card__body insight-card__text-body">
      <div class="insight-card__content" v-dompurify-html="content"></div>
    </div>
  </div>
</template>

<style lang="less" scoped>
@primary: #8b5cf6;

.insight-card {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  &__type-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 0 6px;
    flex-shrink: 0;
    flex-wrap: nowrap;
    overflow: hidden;
  }

  &__tag {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 6px;
    border: 1px solid;
    font-weight: 500;
    white-space: nowrap;
    flex-shrink: 0;
  }

  &__question {
    font-size: 12px;
    color: #94a3b8;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }

  &__body {
    flex: 1;
    overflow: hidden;
    min-height: 0;
  }

  &__table-body {
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow: auto;
  }

  &__sql {
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid rgba(139, 92, 246, 0.15);
    border-radius: 6px;
    padding: 6px 10px;
    flex-shrink: 0;
    code {
      font-size: 11px;
      color: #c4b5fd;
      word-break: break-all;
      white-space: pre-wrap;
    }
  }

  &__table-wrap {
    flex: 1;
    overflow: auto;
    &::-webkit-scrollbar { width: 4px; height: 4px; }
    &::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.3); border-radius: 2px; }
  }

  &__table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    th {
      background: rgba(139, 92, 246, 0.12);
      color: #c4b5fd;
      font-weight: 600;
      padding: 6px 10px;
      text-align: left;
      white-space: nowrap;
      border-bottom: 1px solid rgba(139, 92, 246, 0.2);
      position: sticky;
      top: 0;
    }
    td {
      padding: 5px 10px;
      color: #cbd5e1;
      border-bottom: 1px solid rgba(139, 92, 246, 0.08);
      white-space: nowrap;
      max-width: 200px;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    tr:hover td { background: rgba(139, 92, 246, 0.04); }
  }

  &__more {
    font-size: 11px;
    color: #94a3b8;
    text-align: center;
    padding: 6px;
    flex-shrink: 0;
  }

  &__text-body {
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow: auto;
    &::-webkit-scrollbar { width: 4px; }
    &::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.3); border-radius: 2px; }
  }

  &__mini-chart {
    height: 45%;
    min-height: 120px;
    flex-shrink: 0;
  }

  &__content {
    font-size: 13px;
    color: #cbd5e1;
    line-height: 1.7;
    flex: 1;
    overflow: auto;
    word-wrap: break-word;
    overflow-wrap: break-word;
    word-break: break-word;
    &::-webkit-scrollbar { width: 4px; }
    &::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.3); border-radius: 2px; }
  }

  &__sources {
    flex-shrink: 0;
    padding-top: 8px;
    border-top: 1px solid rgba(139, 92, 246, 0.12);
  }

  &__sources-title {
    font-size: 11px;
    color: #94a3b8;
    margin-bottom: 4px;
    font-weight: 500;
  }

  &__source-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 2px 0;
    .source-badge {
      font-size: 11px;
      padding: 1px 6px;
      background: rgba(236, 72, 153, 0.12);
      color: #f472b6;
      border-radius: 4px;
    }
    .source-page {
      font-size: 11px;
      color: #94a3b8;
    }
    .source-section {
      font-size: 11px;
      color: #94a3b8;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}
</style>
