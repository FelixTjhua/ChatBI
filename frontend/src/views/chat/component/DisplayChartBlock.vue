<script setup lang="ts">
import ChartComponent from '@/views/chat/component/ChartComponent.vue'
import type { ChatMessage } from '@/api/chat.ts'
import { computed, nextTick, ref } from 'vue'
import type { ChartTypes } from '@/views/chat/component/BaseChart.ts'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  id?: number | string
  chartType: ChartTypes
  message: ChatMessage
  data: Array<{ [key: string]: any }>
  loadingData?: boolean
  showLabel?: boolean
}>()

const { t } = useI18n()

const chartObject = computed<{
  type: ChartTypes
  title: string
  data?: { title: string; value: number | string } // KPI 类型的数据
  axis: {
    x: { name: string; value: string }
    y: { name: string; value: string } | Array<{ name: string; value: string }>
    series: { name: string; value: string }
    'multi-quota'?: {
      name: string
      value: Array<string>
    }
  }
  columns: Array<{ name: string; value: string }>
}>(() => {
  if (props.message?.record?.chart) {
    // 如果已经是对象，直接返回；如果是字符串，则解析
    if (typeof props.message.record.chart === 'string') {
      try {
        return JSON.parse(props.message.record.chart)
      } catch (e) {
        return {}
      }
    } else {
      return props.message.record.chart
    }
  }
  return {}
})

// 判断是否为 KPI 类型
const isKpiType = computed(() => {
  return chartObject.value?.type === 'kpi'
})

// KPI 数据 - 从 chart 对象的 data 字段获取，或者从 props.data 获取
const kpiData = computed(() => {
  // 仅当前展示类型为 kpi 时才使用 KPI 格式数据
  // 切换到 table 时需要使用原始 SQL 数据（props.data），否则列名不匹配
  if (isKpiType.value && props.chartType === 'kpi') {
    // 优先从 chartObject.data 获取 KPI 数据
    if (chartObject.value?.data) {
      return [chartObject.value.data]
    }
    // 如果 props.data 存在且有数据
    if (props.data && props.data.length > 0) {
      return props.data
    }
    // 返回默认数据
    return [{ title: chartObject.value?.title || 'KPI', value: 0 }]
  }
  return props.data
})

const xAxis = computed(() => {
  const axis = chartObject.value?.axis
  if (axis?.x) {
    return [axis.x]
  }
  // 饼图没有 x 轴，当 chartObject 原始类型为 pie 时 axis.x 为空
  // 此时如果有 series 字段，可作为 fallback（仅用于 table 视图等场景）
  if (props.chartType !== 'pie' && axis?.series) {
    return [axis.series]
  }
  return []
})
const yAxis = computed(() => {
  const axis = chartObject.value?.axis
  if (!axis?.y) {
    return []
  }

  const y = axis.y
  const multiQuotaValues = axis['multi-quota']?.value || []

  // 统一处理为数组
  const yArray = Array.isArray(y) ? [...y] : [{ ...y }]

  // 标记 multi-quota
  return yArray.map((item) => ({
    ...item,
    'multi-quota': multiQuotaValues.includes(item.value),
  }))
})
const series = computed(() => {
  const axis = chartObject.value?.axis
  if (axis?.series) {
    return [axis.series]
  }
  // column/bar/line/area 没有 series 时的 fallback
  if (props.chartType === 'pie' && axis?.x) {
    return [axis.x]
  }
  return []
})

const multiQuotaName = computed(() => {
  return chartObject.value?.axis?.['multi-quota']?.name
})

const chartRef = ref()

function onTypeChange() {
  nextTick(() => {
    chartRef.value?.destroyChart()
    // destroy 后等一帧让浏览器完成布局，再用正确的容器尺寸渲染
    requestAnimationFrame(() => {
      chartRef.value?.renderChart()
    })
  })
}
function getViewInfo() {
  return {
    chart: {
      columns: chartObject.value?.columns,
      type: props.chartType,
      xAxis: xAxis.value,
      yAxis: yAxis.value,
      series: series.value,
      title: chartObject.value.title,
    },
    data: { data: props.data },
  }
}
function getExcelData() {
  return chartRef.value?.getExcelData()
}

defineExpose({
  onTypeChange,
  getViewInfo,
  getExcelData,
})
</script>

<template>
  <div v-if="message.record?.chart" class="chart-base-container">
    <!-- KPI 类型特殊处理 - 不需要检查 data.length -->
    <ChartComponent
      v-if="message.record.id && (isKpiType || (kpiData && kpiData.length > 0))"
      :id="id ?? 'default_chat_id'"
      ref="chartRef"
      :type="chartType"
      :columns="chartObject?.columns"
      :x="xAxis"
      :y="yAxis"
      :series="series"
      :data="kpiData"
      :multi-quota-name="multiQuotaName"
      :show-label="showLabel"
    />
    <el-empty v-else :description="loadingData ? t('chat.loading_data') : t('chat.no_data')" />
  </div>
</template>

<style scoped lang="less">
// 深色主题变量
@dark-bg-card: rgba(26, 18, 37, 0.6);
@dark-border: rgba(139, 92, 246, 0.15);
@dark-text-muted: rgba(196, 181, 253, 0.6);

.chart-base-container {
  height: 100%;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  border-radius: 10px;
  background: linear-gradient(145deg, rgba(26, 18, 37, 0.65) 0%, rgba(20, 14, 32, 0.7) 100%);
  border: 1px solid @dark-border;
  box-sizing: border-box;
  overflow: hidden;
  position: relative;

  // 顶部高光
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(
      90deg,
      transparent 0%,
      rgba(139, 92, 246, 0.2) 50%,
      transparent 100%
    );
    pointer-events: none;
  }

  :deep(.ed-empty) {
    .ed-empty__description {
      color: @dark-text-muted;
    }

    .ed-empty__image svg {
      opacity: 0.5;
    }
  }
}

// 响应式适配
@media (max-width: 768px) {
  .chart-base-container {
    border-radius: 8px;
  }
}

@media (max-width: 480px) {
  .chart-base-container {
    border-radius: 6px;
  }
}
</style>
