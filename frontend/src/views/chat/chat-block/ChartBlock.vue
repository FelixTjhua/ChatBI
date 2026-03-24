<script setup lang="ts">
import type { ChatMessage } from '@/api/chat.ts'
import DisplayChartBlock from '@/views/chat/component/DisplayChartBlock.vue'
import ChartPopover from '@/views/chat/chat-block/ChartPopover.vue'
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus-secondary'
import { useClipboard } from '@vueuse/core'
import { concat } from 'lodash-es'
import type { ChartTypes } from '@/views/chat/component/BaseChart.ts'
import ICON_BAR from '@/assets/svg/chart/icon_bar_outlined.svg'
import ICON_COLUMN from '@/assets/svg/chart/icon_dashboard_outlined.svg'
import ICON_LINE from '@/assets/svg/chart/icon_chart-line.svg'
import ICON_PIE from '@/assets/svg/chart/icon_pie_outlined.svg'
import ICON_AREA from '@/assets/svg/chart/icon_area_outlined.svg'
import ICON_KPI from '@/assets/svg/chart/icon_kpi_outlined.svg'
import ICON_BOX from '@/assets/svg/chart/icon_box_outlined.svg'
import ICON_HEATMAP from '@/assets/svg/chart/icon_heatmap_outlined.svg'
import ICON_DUAL_AXIS from '@/assets/svg/chart/icon_dual_axis_outlined.svg'
import ICON_TABLE from '@/assets/svg/chart/icon_form_outlined.svg'
import icon_sql_outlined from '@/assets/svg/icon_sql_outlined.svg'
import icon_export_outlined from '@/assets/svg/icon_export_outlined.svg'
import icon_file_image_colorful from '@/assets/svg/icon_file-image_colorful.svg'
import icon_file_excel_colorful from '@/assets/svg/icon_file-excel_colorful.svg'
import icon_window_max_outlined from '@/assets/svg/icon_window-max_outlined.svg'
import icon_window_mini_outlined from '@/assets/svg/icon_window-mini_outlined.svg'
import icon_copy_outlined from '@/assets/svg/icon_copy_outlined.svg'
import { useI18n } from 'vue-i18n'
import SQLComponent from '@/views/chat/component/SQLComponent.vue'

import html2canvas from 'html2canvas'
import { chatApi } from '@/api/chat'


const props = withDefaults(
  defineProps<{
    recordId?: number
    message: ChatMessage
    isPredict?: boolean
    chatType?: ChartTypes
    enlarge?: boolean
    loadingData?: boolean
  }>(),
  {
    recordId: undefined,
    isPredict: false,
    chatType: undefined,
    enlarge: false,
    loadingData: false,
  }
)

const { copy } = useClipboard({ legacy: true })
const loading = ref<boolean>(false)
const { t } = useI18n()
const emits = defineEmits(['exitFullScreen'])

const dataObject = computed<{
  fields: Array<string>
  data: Array<{ [key: string]: any }>
  limit: number | undefined
}>(() => {
  if (props.message?.record?.data) {
    if (typeof props.message?.record?.data === 'string') {
      try {
        return JSON.parse(props.message.record.data)
      } catch (e) {
        console.warn('Failed to parse chart data JSON:', e)
        return { fields: [], data: [], limit: undefined }
      }
    } else {
      return props.message.record.data
    }
  }
  return { fields: [], data: [], limit: undefined }
})
const isCompletePage = true

const chartId = computed(() => props.message?.record?.id + (props.enlarge ? '-fullscreen' : ''))

/**
 *  图表数据聚合辅助函数：对同一分类的多行数据进行求和合并
 * SQL 可能返回同一类别多条记录，所有图表类型（pie/column/bar/line/area）
 * 都需要在数据层聚合，确保图表和表格视图展示聚合后的数据。
 * table 类型不做聚合（展示原始明细数据）。
 */
function aggregateChartData(rawData: Array<{ [key: string]: any }>): Array<{ [key: string]: any }> {
  const chart = chartObject.value
  if (!chart || !rawData || rawData.length === 0) {
    return rawData
  }

  const chartType = chart.type
  // table 展示原始明细，不聚合
  if (!chartType || !['pie', 'column', 'bar', 'line', 'area'].includes(chartType)) {
    return rawData
  }

  // 确定分组字段：饼图用 series 或 x，其他图表用 x
  const groupField = chartType === 'pie'
    ? (chart.axis?.series?.value || chart.axis?.x?.value)
    : chart.axis?.x?.value
  const yField = chart.axis?.y?.value
  const seriesField = chart.axis?.series?.value

  if (!groupField || !yField) {
    return rawData
  }

  // 是否需要复合分组键（x + series）
  const useSeries = seriesField && seriesField !== groupField

  // 辅助函数：将值转为数字（支持 "5.67%" 格式的字符串）
  const toNum = (v: any): number => {
    if (typeof v === 'number') return v
    if (typeof v === 'string') {
      const stripped = v.trim().replace(/%$/, '')
      const n = Number(stripped)
      return isNaN(n) ? 0 : n
    }
    return 0
  }

  // 检测原始数据是否带 % 后缀（用于聚合后恢复格式）
  const firstVal = rawData.find(r => r[yField] != null)?.[yField]
  const hasPercentSuffix = typeof firstVal === 'string' && firstVal.trim().endsWith('%')

  const aggregatedMap = new Map<string, { [key: string]: any }>()
  for (const row of rawData) {
    const keyParts = [String(row[groupField] ?? '')]
    if (useSeries) {
      keyParts.push(String(row[seriesField] ?? ''))
    }
    const key = keyParts.join('||')

    if (aggregatedMap.has(key)) {
      const existing = aggregatedMap.get(key)!
      const existingVal = toNum(existing[yField])
      const newVal = toNum(row[yField])
      const sum = Math.round((existingVal + newVal) * 100) / 100
      existing[yField] = hasPercentSuffix ? `${sum}%` : sum
    } else {
      aggregatedMap.set(key, { ...row })
    }
  }
  return Array.from(aggregatedMap.values())
}

const data = computed(() => {
  if (props.isPredict) {
    let _list = []
    
    if (
      props.message?.record?.predict_data &&
      typeof props.message?.record?.predict_data === 'string'
    ) {
      if (
        props.message?.record?.predict_data.length > 0 &&
        props.message?.record?.predict_data.trim().startsWith('[') &&
        props.message?.record?.predict_data.trim().endsWith(']')
      ) {
        try {
          _list = JSON.parse(props.message?.record?.predict_data)
        } catch (e) {
          // parse error, keep empty
        }
      }
    } else {
      if (props.message?.record?.predict_data?.length > 0) {
        _list = props.message?.record?.predict_data
      }
    }
    
    if (dataObject.value.data && dataObject.value.data?.length > 0) {
      if (_list.length > 0) {
        // 验证预测数据与原始数据的列结构兼容性
        // 如果列名不一致，仅返回原始数据，避免图表渲染异常
        const originalKeys = Object.keys(dataObject.value.data[0] || {}).sort()
        const predictKeys = Object.keys(_list[0] || {}).sort()
        const isCompatible = originalKeys.length > 0 && predictKeys.length > 0 &&
          originalKeys.length === predictKeys.length &&
          originalKeys.every((key, i) => key === predictKeys[i])
        if (isCompatible) {
          return aggregateChartData(concat(dataObject.value.data, _list))
        } else {
          console.warn('Predict data columns mismatch, skipping concat:', { originalKeys, predictKeys })
          return aggregateChartData(dataObject.value.data)
        }
      } else {
        return aggregateChartData(dataObject.value.data)
      }
    }
    
    if (_list.length > 0) {
      return aggregateChartData(_list)
    }
    
    return []
  } else {
    return aggregateChartData(dataObject.value.data || [])
  }
})

const chartRef = ref()

const chartObject = computed<{
  type: ChartTypes
  title: string
  data?: { title: string; value: number | string } // KPI 类型的数据
  axis: {
    x: { name: string; value: string }
    y: { name: string; value: string }
    series: { name: string; value: string }
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

// 单行结果自然语言总结（极值查询如"最高/最低/第一"只返回1行，表格展示不够直观）
const singleRowSummary = computed(() => {
  if (
    chartObject.value?.type !== 'table' ||
    !data.value ||
    data.value.length !== 1 ||
    !chartObject.value?.columns?.length
  ) {
    return ''
  }
  const row = data.value[0]
  const parts = chartObject.value.columns
    .map((col: { name: string; value: string }) => {
      const val = row[col.value]
      return val != null ? `${col.name}：${val}` : null
    })
    .filter(Boolean)
  return parts.join('，')
})

const currentChartType = ref<ChartTypes | undefined>(
  props.chatType ?? chartObject.value.type ?? 'table'
)

const chartType = computed<ChartTypes>({
  get() {
    if (currentChartType.value) {
      return currentChartType.value
    }
    return props.chatType ?? chartObject.value.type ?? 'table'
  },
  set(v) {
    currentChartType.value = v
  },
})

const chartTypeList = computed(() => {
  const _list = []
  if (chartObject.value) {
    switch (chartObject.value.type) {
      // table / kpi / box / heatmap / dual_axis / pie：数据结构特殊，不支持切换
      case 'table':
      case 'kpi':
      case 'box':
      case 'heatmap':
      case 'dual_axis':
        break
      // 柱状图/条形图/折线图/面积图：数据结构兼容（x轴 + y轴），可互切
      case 'column':
      case 'bar':
      case 'line':
      case 'area':
        _list.push({
          value: 'column',
          name: t('chat.chart_type.column'),
          icon: ICON_COLUMN,
        })
        _list.push({
          value: 'bar',
          name: t('chat.chart_type.bar'),
          icon: ICON_BAR,
        })
        _list.push({
          value: 'line',
          name: t('chat.chart_type.line'),
          icon: ICON_LINE,
        })
        _list.push({
          value: 'area',
          name: t('chat.chart_type.area'),
          icon: ICON_AREA,
        })
        break
      // 饼图：数据结构特殊（series+y，无x轴），不可切到其他图表
      case 'pie':
        break
    }
  }

  return _list
})

// 不可切换的图表类型的图标和名称（用于静态按钮显示）
const chartIconMap: Record<string, any> = {
  pie: ICON_PIE,
  column: ICON_COLUMN,
  bar: ICON_BAR,
  line: ICON_LINE,
  area: ICON_AREA,
  kpi: ICON_KPI,
  box: ICON_BOX,
  heatmap: ICON_HEATMAP,
  dual_axis: ICON_DUAL_AXIS,
}
const chartNameMap: Record<string, string> = {
  pie: 'chat.chart_type.pie',
  column: 'chat.chart_type.column',
  bar: 'chat.chart_type.bar',
  line: 'chat.chart_type.line',
  area: 'chat.chart_type.area',
  kpi: 'chat.chart_type.kpi',
  box: 'chat.chart_type.box',
  heatmap: 'chat.chart_type.heatmap',
  dual_axis: 'chat.chart_type.dual_axis',
}
const originalChartIcon = computed(() => chartIconMap[chartObject.value?.type] ?? null)
const originalChartName = computed(() => {
  const key = chartNameMap[chartObject.value?.type]
  if (!key) return ''
  return t(key)
})

function changeTable() {
  onTypeChange('table')
}

function onTypeChange(val: any) {
  chartType.value = val
  chartRef.value?.onTypeChange()
}

function reloadChart() {
  chartRef.value?.onTypeChange()
}

const dialogVisible = ref(false)

function openFullScreen() {
  dialogVisible.value = true
}

function closeFullScreen() {
  emits('exitFullScreen')
}

function onExitFullScreen() {
  dialogVisible.value = false
}

const sqlShow = ref(false)

function showSql() {
  sqlShow.value = true
}


function copyText() {
  if (props.message?.record?.sql) {
    copy(props.message.record.sql).then(() => {
      copied.value = true
      ElMessage.success(t('common.copy_successful'))
      setTimeout(() => {
        copied.value = false
      }, 2000)
    })
  }
}

const copied = ref(false)
const exportRef = ref()

function exportToExcel() {
  if (chartRef.value && props.recordId) {
    loading.value = true
    chatApi
      .export2Excel(props.recordId)
      .then((res) => {
        const blob = new Blob([res], {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        const link = document.createElement('a')
        link.href = URL.createObjectURL(blob)
        link.download = `${chartObject.value.title ?? 'Excel'}.xlsx`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
      })
      .catch(async (error) => {
        if (error.response) {
          try {
            let text = await error.response.data.text()
            try {
              text = JSON.parse(text)
            } finally {
              ElMessage({
                message: text,
                type: 'error',
                showClose: true,
              })
            }
          } catch (e) {
            // 错误响应处理失败
          }
        } else {
          ElMessage({
            message: error,
            type: 'error',
            showClose: true,
          })
        }
      })
      .finally(() => {
        loading.value = false
      })
    exportRef.value?.hide()
  }
}

function exportToCsv() {
  if (chartRef.value && props.recordId) {
    loading.value = true
    chatApi
      .export2Csv(props.recordId)
      .then((res) => {
        const blob = new Blob([res], { type: 'text/csv; charset=utf-8' })
        const link = document.createElement('a')
        link.href = URL.createObjectURL(blob)
        link.download = `${chartObject.value.title ?? 'data'}.csv`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
      })
      .catch(async (error) => {
        if (error.response) {
          try {
            let text = await error.response.data.text()
            try { text = JSON.parse(text) } finally {
              ElMessage({ message: text, type: 'error', showClose: true })
            }
          } catch (e) { /* ignore */ }
        } else {
          ElMessage({ message: error, type: 'error', showClose: true })
        }
      })
      .finally(() => { loading.value = false })
    exportRef.value?.hide()
  }
}

function exportToImage() {
  const obj = document.getElementById('chart-component-' + chartId.value)
  if (obj) {
    html2canvas(obj, {
      backgroundColor: '#0f0a1a',
      scale: 2,
      useCORS: true,
      logging: false,
      // 确保完整捕获，包括溢出内容
      scrollX: 0,
      scrollY: 0,
      width: obj.scrollWidth,
      height: obj.scrollHeight,
    }).then((canvas) => {
      canvas.toBlob(function (blob) {
        if (blob) {
          const link = document.createElement('a')
          link.download = (chartObject.value.title ?? 'chart') + '.png'
          link.href = URL.createObjectURL(blob)
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
          URL.revokeObjectURL(link.href)
        }
      }, 'image/png')
    })
  }
  exportRef.value?.hide()
}

defineExpose({
  reloadChart,
})

watch(
  () => chartObject.value?.type,
  (val) => {
    if (val) {
      currentChartType.value = val
    }
  }
)

// 监听 message.record 的数据变化，强制重新渲染图表
// 原代码只在 isPredict 时才重新渲染，导致普通图表在 getChatData 异步返回后不更新
watch(
  () => [props.message?.record?.data, props.message?.record?.predict_data],
  ([newData, newPredictData], [oldData, oldPredictData]) => {
    const dataChanged = newData !== oldData
    const predictDataChanged = newPredictData !== oldPredictData
    
    if (dataChanged || predictDataChanged) {
      // 如果是从无数据到有数据（首次加载），跳过 reloadChart
      // 此时 DisplayChartBlock/ChartComponent 刚被 v-if 创建，onMounted 会自行渲染
      // 再调 reloadChart 会导致 destroy+render 与 onMounted 的 render 竞争，引起尺寸异常
      const wasEmpty = !oldData || (Array.isArray(oldData) && oldData.length === 0)
      const isNowFilled = newData && (!Array.isArray(newData) || newData.length > 0)
      if (wasEmpty && isNowFilled && !predictDataChanged) {
        return
      }

      // 等两帧：第一帧让 Vue 完成 DOM 更新（v-if 切换），第二帧让浏览器完成布局
      nextTick(() => {
        requestAnimationFrame(() => {
          reloadChart()
        })
      })
    }
  },
  { deep: true }
)
</script>

<template>
  <div
    v-if="
      !message.isTyping &&
      ((!isPredict && (message?.record?.sql || message?.record?.chart)) ||
        (isPredict && message?.record?.chart && (
          (message?.record?.predict_data && (
            (Array.isArray(message.record.predict_data) && message.record.predict_data.length > 0) ||
            (typeof message.record.predict_data === 'string' && message.record.predict_data.trim().length > 0 && message.record.predict_data.trim().startsWith('['))
          )) ||
          message?.record?.data
        )))
    "
    v-loading.fullscreen.lock="loading"
    class="chart-component-container"
    :class="{ 'full-screen': enlarge }"
  >
    <div class="header-bar">
      <div class="title">
        {{ chartObject.title }}
      </div>
      <div class="buttons-bar">
        <div class="chart-select-container">
          <el-tooltip effect="dark" :offset="8" :content="t('chat.type')" placement="top">
            <ChartPopover
              v-if="chartTypeList.length > 0"
              :chart-type-list="chartTypeList"
              :chart-type="chartType"
              :title="t('chat.type')"
              @type-change="onTypeChange"
            ></ChartPopover>
          </el-tooltip>
          <!-- 不可切换的图表类型：显示静态图标按钮，点击切回原始图表 -->
          <el-tooltip
            v-if="chartTypeList.length === 0 && originalChartIcon"
            effect="dark"
            :offset="8"
            :content="originalChartName"
            placement="top"
          >
            <el-button
              class="tool-btn"
              :class="{ 'chart-active': currentChartType !== 'table' }"
              text
              @click="onTypeChange(chartObject.type)"
            >
              <el-icon size="16">
                <component :is="originalChartIcon" />
              </el-icon>
            </el-button>
          </el-tooltip>

          <el-tooltip
            effect="dark"
            :offset="8"
            :content="t('chat.chart_type.table')"
            placement="top"
          >
            <el-button
              class="tool-btn"
              :class="{ 'chart-active': currentChartType === 'table' }"
              text
              @click="changeTable"
            >
              <el-icon size="16">
                <ICON_TABLE />
              </el-icon>
            </el-button>
          </el-tooltip>
        </div>

        <div v-if="!isPredict && message?.record?.sql">
          <el-tooltip effect="dark" :offset="8" :content="t('chat.show_sql')" placement="top">
            <el-button class="tool-btn" text @click="showSql">
              <el-icon size="16">
                <icon_sql_outlined />
              </el-icon>
            </el-button>
          </el-tooltip>
        </div>
        <div v-if="message?.record?.chart">
          <el-popover
            ref="exportRef"
            trigger="click"
            popper-class="export_to_select"
            placement="bottom"
          >
            <template #reference>
              <div>
                <el-tooltip
                  effect="dark"
                  :offset="8"
                  :content="t('chat.export_to')"
                  placement="top"
                >
                  <el-button class="tool-btn" text>
                    <el-icon size="16">
                      <icon_export_outlined />
                    </el-icon>
                  </el-button>
                </el-tooltip>
              </div>
            </template>
            <div class="popover">
              <div class="popover-content">
                <div class="title">{{ t('chat.export_to') }}</div>
                <div class="popover-item" @click="exportToExcel">
                  <el-icon size="16">
                    <icon_file_excel_colorful />
                  </el-icon>
                  <div class="model-name">{{ t('chat.excel') }}</div>
                </div>
                <div class="popover-item" @click="exportToCsv">
                  <el-icon size="16">
                    <icon_file_excel_colorful />
                  </el-icon>
                  <div class="model-name">CSV</div>
                </div>
                <div
                  v-if="currentChartType !== 'table'"
                  class="popover-item"
                  @click="exportToImage"
                >
                  <el-icon size="16">
                    <icon_file_image_colorful />
                  </el-icon>
                  <div class="model-name">{{ t('chat.picture') }}</div>
                </div>
              </div>
            </div>
          </el-popover>
        </div>

        <div class="divider" />
        <div v-if="!enlarge">
          <el-tooltip
            effect="dark"
            :offset="8"
            :content="!isCompletePage ? $t('common.zoom_in') : t('chat.full_screen')"
            placement="top"
          >
            <el-button class="tool-btn" text @click="openFullScreen">
              <el-icon size="16">
                <icon_window_max_outlined />
              </el-icon>
            </el-button>
          </el-tooltip>
        </div>
        <div v-else>
          <el-tooltip
            effect="dark"
            :offset="8"
            :content="!isCompletePage ? $t('common.zoom_out') : t('chat.exit_full_screen')"
            placement="top"
          >
            <el-button class="tool-btn" text @click="closeFullScreen">
              <el-icon size="16">
                <icon_window_mini_outlined />
              </el-icon>
            </el-button>
          </el-tooltip>
        </div>
      </div>
    </div>

    <template v-if="message?.record?.chart">
      <!-- 数据加载中 -->
      <div v-if="loadingData" class="chart-block loading-block">
        <div class="loading-content">
          <div class="loading-spinner">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span class="loading-text">{{ t('qa.loading_data') }}</span>
        </div>
      </div>
      <!-- 无数据提示 - KPI 类型展示原始图表时不需要检查 data，但切到 table 时需要 -->
      <div v-else-if="!(isKpiType && currentChartType !== 'table') && (!data || data.length === 0)" class="chart-block no-data-block">
        <div class="no-data-content">
          <svg
            class="no-data-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
          >
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M3 9h18M9 21V9" />
            <path d="M14 14h3M14 17h3" />
          </svg>
          <span class="no-data-text">{{ t('qa.no_data') }}</span>
          <span class="no-data-hint">{{ t('qa.no_data_hint') }}</span>
        </div>
      </div>
      <!-- 单行结果自然语言总结（极值查询） -->
      <div v-else-if="singleRowSummary" class="chart-block single-row-block">
        <div class="single-row-summary">{{ singleRowSummary }}</div>
      </div>
      <!-- 正常显示图表 -->
      <div v-else class="chart-block">
        <DisplayChartBlock
          :id="chartId"
          ref="chartRef"
          :key="`display-chart-${chartId}-${chartType}`"
          :chart-type="chartType"
          :message="message"
          :data="data"
          :loading-data="loadingData"
        />
      </div>
      <div v-if="dataObject.limit" class="over-limit-hint">
        {{ t('chat.data_over_limit', [dataObject.limit]) }}
      </div>
    </template>

    <el-dialog
      v-if="!enlarge"
      v-model="dialogVisible"
      fullscreen
      :show-close="false"
      class="chart-fullscreen-dialog"
      header-class="chart-fullscreen-dialog-header"
      body-class="chart-fullscreen-dialog-body"
    >
      <ChartBlock
        v-if="dialogVisible"
        :message="message"
        :record-id="recordId"
        :is-predict="isPredict"
        :chat-type="chartType"
        :loading-data="loadingData"
        enlarge
        @exit-full-screen="onExitFullScreen"
      />
    </el-dialog>

    <el-drawer
      v-model="sqlShow"
      :size="!isCompletePage ? '100%' : '600px'"
      :title="t('chat.show_sql')"
      direction="rtl"
      body-class="chart-sql-drawer-body"
    >
      <div class="sql-block">
        <SQLComponent
          v-if="message.record?.sql"
          :sql="message.record?.sql"
          style="margin-top: 12px"
        />
        <el-button 
          v-if="message.record?.sql" 
          class="copy-sql-btn-improved" 
          @click="copyText"
        >
          <el-icon size="16">
            <icon_copy_outlined />
          </el-icon>
          <span class="btn-text">{{ copied ? `✓ ${t('common.copy_successful')}` : t('chat.copy_sql') }}</span>
        </el-button>
      </div>
    </el-drawer>

  </div>
</template>

<style lang="less">
.chart-fullscreen-dialog {
  padding: 0;
}

.chart-fullscreen-dialog-header {
  display: none;
}

.chart-fullscreen-dialog-body {
  padding: 0;
}

.chart-sql-drawer-body {
  padding: 24px;
}


.export_to_select.export_to_select {
  padding: 4px 0;
  width: 120px !important;
  min-width: 120px !important;
  box-shadow: 0px 4px 8px 0px #1f23291a;
  border: 1px solid #dee0e3;

  .popover {
    .popover-content {
      padding: 0 4px;
      max-height: 300px;
      overflow-y: auto;

      .title {
        width: 100%;
        height: 32px;
        margin-bottom: 2px;
        display: flex;
        align-items: center;
        padding-left: 8px;
        color: #8f959e;
      }
    }

    .popover-item {
      height: 32px;
      display: flex;
      align-items: center;
      padding-left: 12px;
      padding-right: 8px;
      margin-bottom: 2px;
      position: relative;
      border-radius: 4px;
      cursor: pointer;

      &:last-child {
        margin-bottom: 0;
      }

      &:hover {
        background: #1f23291a;
      }

      .model-name {
        margin-left: 8px;
        font-weight: 400;
        font-size: 14px;
        line-height: 22px;
        max-width: 220px;
      }

      .done {
        margin-left: auto;
        display: none;
      }

      &.isActive {
        color: var(--ed-color-primary);

        .done {
          display: block;
        }
      }
    }
  }
}
</style>
<style scoped lang="less">
// 深色主题变量
@dark-bg: #0f0a1a;
@dark-bg-card: rgba(26, 18, 37, 0.9);
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.7);
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;

.chart-component-container {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  padding: 16px;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  overflow: hidden;
  position: relative;

  border: 1.5px solid @dark-border;
  border-radius: 14px;
  background: linear-gradient(145deg, rgba(26, 18, 37, 0.85) 0%, rgba(20, 14, 32, 0.9) 100%);
  backdrop-filter: blur(12px);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.03);
  transition: all 0.3s ease;

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
      rgba(139, 92, 246, 0.3) 50%,
      transparent 100%
    );
    pointer-events: none;
  }

  &:hover {
    border-color: rgba(139, 92, 246, 0.3);
    box-shadow:
      0 12px 40px rgba(0, 0, 0, 0.3),
      inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  &.full-screen {
    border: unset;
    border-radius: unset;
    padding: 0;
    background: @dark-bg;
    max-width: none;
    box-shadow: none;

    &::before {
      display: none;
    }

    .header-bar {
      border-bottom: 1px solid @dark-border;
      height: 55px;
      padding: 16px 24px;
    }

    .chart-block {
      margin: unset;
      padding: 16px;
      height: calc(100vh - 56px);
      max-width: none;
    }
  }

  .header-bar {
    height: auto;
    min-height: 36px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    flex-direction: row;
    gap: 14px;

    .tool-btn {
      width: 28px;
      height: 28px;
      min-width: 28px;
      font-size: 16px;
      font-weight: 400;
      line-height: 24px;
      border-radius: 8px;
      color: #ffffff;
      transition: all 0.25s ease;

      .tool-btn-inner {
        display: flex;
        flex-direction: row;
        align-items: center;
      }
      
      :deep(.ed-icon) {
        color: #ffffff;
      }
      
      :deep(svg) {
        fill: currentColor;
        color: #ffffff;
      }
      
      :deep(path) {
        fill: currentColor;
      }

      &:hover {
        background: rgba(139, 92, 246, 0.18);
        color: #a78bfa;
        transform: translateY(-1px);
        
        :deep(.ed-icon) {
          color: #a78bfa;
        }
        
        :deep(svg) {
          color: #a78bfa;
        }
        
        :deep(path) {
          fill: currentColor;
        }
      }

      &:active {
        background: rgba(139, 92, 246, 0.25);
        transform: translateY(0);
      }
    }

    .chart-active {
      background: rgba(139, 92, 246, 0.22);
      color: #a78bfa;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(139, 92, 246, 0.15);
      
      :deep(.ed-icon) {
        color: #a78bfa;
      }
      
      :deep(svg) {
        color: #a78bfa;
      }
      
      :deep(path) {
        fill: currentColor;
      }

      :deep(.ed-select__wrapper) {
        background: transparent;
      }

      :deep(.ed-select__input) {
        color: #a78bfa;
      }

      :deep(.ed-select__placeholder) {
        color: #a78bfa;
      }

      :deep(.ed-select__caret) {
        color: #a78bfa;
      }
    }

    .title {
      flex: 1;
      min-width: 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;

      color: @dark-text;
      font-weight: 600;
      font-size: 16px;
      line-height: 24px;
      letter-spacing: 0.3px;
    }

    .buttons-bar {
      display: flex;
      flex-direction: row;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;

      .divider {
        width: 1px;
        height: 18px;
        background: linear-gradient(180deg, transparent 0%, @dark-border 50%, transparent 100%);
      }
    }

    .chart-select-container {
      padding: 4px;
      display: flex;
      flex-direction: row;
      gap: 4px;
      border-radius: 8px;
      background: rgba(139, 92, 246, 0.06);
      border: 1px solid rgba(139, 92, 246, 0.15);

      .chart-select {
        min-width: 40px;
        width: 40px;
        height: 24px;

        :deep(.ed-select__wrapper) {
          padding: 4px;
          min-height: 24px;
          box-shadow: unset;
          border-radius: 6px;

          &:hover {
            background: rgba(139, 92, 246, 0.15);
          }

          &:active {
            background: rgba(139, 92, 246, 0.2);
          }
        }

        :deep(.ed-select__caret) {
          font-size: 12px !important;
        }
      }
    }
  }

  .chart-block {
    height: 320px;
    width: 100%;
    min-width: 0;
    margin-top: 16px;
    box-sizing: border-box;
    border-radius: 10px;

    &.single-row-block {
      height: auto;
      display: flex;
      align-items: center;
      padding: 20px 24px;
      background: linear-gradient(145deg, rgba(139, 92, 246, 0.08) 0%, rgba(168, 85, 247, 0.04) 100%);
      border: 1px solid rgba(139, 92, 246, 0.2);

      .single-row-summary {
        font-size: 16px;
        font-weight: 600;
        color: rgba(255, 255, 255, 0.95);
        line-height: 1.6;
        letter-spacing: 0.3px;
      }
    }

    &.loading-block,
    &.no-data-block {
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(
        145deg,
        rgba(139, 92, 246, 0.06) 0%,
        rgba(168, 85, 247, 0.03) 100%
      );
      border: 1.5px dashed rgba(139, 92, 246, 0.2);
      border-radius: 12px;
    }

    .loading-content {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 18px;

      .loading-spinner {
        display: flex;
        gap: 8px;

        span {
          width: 12px;
          height: 12px;
          background: linear-gradient(135deg, @primary-400 0%, @primary-500 100%);
          border-radius: 50%;
          animation: bounce 1.4s infinite ease-in-out both;
          box-shadow: 0 2px 8px rgba(139, 92, 246, 0.35);

          &:nth-child(1) {
            animation-delay: -0.32s;
          }
          &:nth-child(2) {
            animation-delay: -0.16s;
          }
          &:nth-child(3) {
            animation-delay: 0s;
          }
        }
      }

      .loading-text {
        font-size: 14px;
        color: @dark-text-muted;
        font-weight: 500;
        letter-spacing: 0.3px;
      }
    }

    .no-data-content {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 14px;

      .no-data-icon {
        width: 52px;
        height: 52px;
        color: @dark-text-muted;
      }

      .no-data-text {
        font-size: 15px;
        font-weight: 600;
        color: @dark-text-secondary;
        letter-spacing: 0.3px;
      }

      .no-data-hint {
        font-size: 13px;
        color: @dark-text-muted;
        text-align: center;
        max-width: 280px;
        line-height: 1.5;
      }
    }
  }

  @keyframes bounce {
    0%,
    80%,
    100% {
      transform: scale(0.6);
      opacity: 0.5;
    }
    40% {
      transform: scale(1);
      opacity: 1;
    }
  }

  .over-limit-hint {
    min-height: 24px;
    line-height: 24px;
    font-size: 13px;
    color: @dark-text-muted;
    margin-top: 12px;
    padding: 8px 12px;
    background: rgba(251, 191, 36, 0.08);
    border: 1px solid rgba(251, 191, 36, 0.15);
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 8px;

    &::before {
      content: '⚠️';
      font-size: 14px;
    }
  }
}

// 响应式适配 - 平板
@media (max-width: 1024px) {
  .chart-component-container {
    padding: 14px;
    border-radius: 12px;

    .header-bar {
      gap: 12px;

      .title {
        font-size: 15px;
      }

      .buttons-bar {
        gap: 10px;
      }
    }

    .chart-block {
      height: 300px;
      margin-top: 14px;
    }
  }
}

// 响应式适配 - 手机
@media (max-width: 768px) {
  .chart-component-container {
    padding: 12px;
    border-radius: 12px;

    .header-bar {
      gap: 10px;

      .title {
        font-size: 14px;
        flex-basis: 100%;
        margin-bottom: 8px;
      }

      .buttons-bar {
        gap: 8px;
        width: 100%;
        justify-content: flex-start;

        .divider {
          height: 16px;
        }
      }

      .tool-btn {
        width: 26px;
        height: 26px;
        min-width: 26px;
      }
    }

    .chart-block {
      height: 260px;
      margin-top: 12px;
    }

    .over-limit-hint {
      font-size: 12px;
      padding: 6px 10px;
    }
  }
}

// 超小屏幕
@media (max-width: 480px) {
  .chart-component-container {
    padding: 10px;
    border-radius: 10px;

    .header-bar {
      .title {
        font-size: 13px;
      }

      .tool-btn {
        width: 24px;
        height: 24px;
        min-width: 24px;
        border-radius: 6px;
      }
    }

    .chart-block {
      height: 220px;
      margin-top: 10px;
    }
  }
}

.sql-block {
  position: relative;

  .copy-sql-btn-improved {
    position: absolute;
    top: 12px;
    right: 12px;
    padding: 8px 16px;
    height: auto;
    min-height: 32px;
    background: rgba(139, 92, 246, 0.12);
    border: 1px solid rgba(139, 92, 246, 0.2);
    border-radius: 8px;
    color: @primary-400;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 6px;
    z-index: 10;

    &:hover {
      background: rgba(139, 92, 246, 0.2);
      border-color: rgba(139, 92, 246, 0.35);
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(139, 92, 246, 0.2);
    }

    &:active {
      transform: translateY(0);
    }

    .btn-text {
      font-size: 13px;
      font-weight: 500;
      color: @primary-400;
    }
  }

  .input-icon {
    min-width: unset;
    position: absolute;
    top: 12px;
    right: 12px;
    color: @dark-text-secondary;
    display: none;
    background-color: transparent !important;

    border-color: @dark-border;
    box-shadow: 0px 4px 8px 0px rgba(0, 0, 0, 0.3);

    &:hover,
    &:focus {
      color: @primary-400;
    }

    &:active {
      color: @primary-500;
    }
  }

  &:hover {
    .input-icon {
      display: flex;
    }
  }
}
</style>
