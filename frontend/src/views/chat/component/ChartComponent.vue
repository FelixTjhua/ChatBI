<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { getChartInstance } from '@/views/chat/component/index.ts'
import type { BaseChart, ChartAxis, ChartData } from '@/views/chat/component/BaseChart.ts'
import { fixFloatPrecision } from '@/views/chat/component/charts/utils.ts'
import { useEmitt } from '@/utils/useEmitt.ts'

const params = withDefaults(
  defineProps<{
    id: string | number
    type: string
    data?: Array<ChartData>
    columns?: Array<ChartAxis>
    x?: Array<ChartAxis>
    y?: Array<ChartAxis>
    series?: Array<ChartAxis>
    multiQuotaName?: string | undefined
    showLabel?: boolean
  }>(),
  {
    data: () => [],
    columns: () => [],
    x: () => [],
    y: () => [],
    series: () => [],
    multiQuotaName: undefined,
    showLabel: false,
  }
)

const chartId = computed(() => {
  return 'chart-component-' + params.id
})

const axis = computed(() => {
  const _list: Array<ChartAxis> = []
  params.columns.forEach((column) => {
    _list.push({ name: column.name, value: column.value })
  })
  params.x.forEach((column) => {
    _list.push({ name: column.name, value: column.value, type: 'x' })
  })
  params.y.forEach((column) => {
    _list.push({
      name: column.name,
      value: column.value,
      type: 'y',
      'multi-quota': column['multi-quota'],
    })
  })
  params.series.forEach((column) => {
    _list.push({ name: column.name, value: column.value, type: 'series' })
  })
  if (params.multiQuotaName) {
    _list.push({
      name: params.multiQuotaName,
      value: params.multiQuotaName,
      type: 'other-info',
      hidden: true,
    })
  }
  return _list
})

let chartInstance: BaseChart | undefined
let renderRetryCount = 0
let renderRetryTimer: number | undefined
const MAX_RENDER_RETRIES = 10

function renderChart() {
  // 渲染前检查DOM元素是否存在
  const container = document.getElementById(chartId.value)
  if (!container) {
    nextTick(() => {
      const retryContainer = document.getElementById(chartId.value)
      if (retryContainer) {
        renderChart()
      }
    })
    return
  }

  // 检查容器是否有有效尺寸
  if ((container.clientWidth === 0 || container.clientHeight === 0) && renderRetryCount < MAX_RENDER_RETRIES) {
    renderRetryCount++
    renderRetryTimer = window.setTimeout(() => renderChart(), 60)
    return
  }
  renderRetryCount = 0
  renderRetryTimer = undefined
  
  chartInstance = getChartInstance(params.type, chartId.value)
  if (chartInstance) {
    chartInstance.showLabel = params.showLabel
    chartInstance.init(axis.value, fixFloatPrecision(params.data))
    chartInstance.render()
  }
}

function destroyChart() {
  // 清除待执行的重试定时器，防止 destroy 后旧的 renderChart 仍被触发
  if (renderRetryTimer) {
    window.clearTimeout(renderRetryTimer)
    renderRetryTimer = undefined
  }
  renderRetryCount = 0
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = undefined
  }
}

watch(
  () => params.showLabel,
  () => {
    destroyChart()
    renderChart()
  }
)

function getExcelData() {
  return {
    axis: axis.value,
    data: params.data,
  }
}

useEmitt({
  name: 'view-render-all',
  callback: () => {
    // 重新渲染图表以适应新的容器尺寸
    nextTick(() => {
      destroyChart()
      renderChart()
    })
  },
})

useEmitt({
  name: `view-render-${params.id}`,
  callback: renderChart,
})

defineExpose({
  renderChart,
  destroyChart,
  getExcelData,
})

onMounted(() => {
  // 等一帧让浏览器完成容器布局，再用正确的尺寸渲染图表
  // 切换聊天记录时组件刚挂载，容器可能还没有最终尺寸
  nextTick(() => {
    requestAnimationFrame(() => {
      renderChart()
    })
  })
})

onUnmounted(() => {
  destroyChart()
})
</script>

<template>
  <div :id="chartId" class="chart-container"></div>
</template>

<style scoped lang="less">
.chart-container {
  height: 100%;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}
</style>
