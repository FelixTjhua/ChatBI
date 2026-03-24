<script lang="ts" setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus-secondary'
import { datasourceApi } from '@/api/datasource'
import icon_right_outlined from '@/assets/svg/icon_right_outlined.svg'
import icon_form_outlined from '@/assets/svg/icon_form_outlined.svg'
import icon_searchOutline_outlined from '@/assets/svg/icon_search-outline_outlined.svg'
import EmptyBackground from '@/components/EmptyBackground.vue'
import edit from '@/assets/svg/icon_edit_outlined.svg'
import { useI18n } from 'vue-i18n'
import ParamsForm from './ParamsForm.vue'
import TableRelationship from '@/views/ds/TableRelationship.vue'
import { decrypted } from './js/aes'
import icon_mindnote_outlined from '@/assets/svg/icon_mindnote_outlined.svg'
interface Table {
  name: string
  host: string
  port: string
  username: string
  password: string
  database: string
  extraJdbc: string
  dbSchema: string
  filename: string
  sheets: string
  mode: string
  timeout: string
  configuration: string
  id: number
}

const props = withDefaults(
  defineProps<{
    info: Table
  }>(),
  {
    info: () => ({
      name: '-',
      host: '-',
      port: '-',
      username: '-',
      password: '-',
      database: '-',
      extraJdbc: '-',
      dbSchema: '-',
      filename: '-',
      sheets: '-',
      mode: '-',
      timeout: '-',
      configuration: '-',
      id: 0,
    }),
  }
)
const { t } = useI18n()
const paramsFormRef = ref()
const tableList = ref([] as any[])
const loading = ref(false)
const initLoading = ref(false)
const activeRelationship = ref(false)
const keywords = ref('')
const tableListWithSearch = computed(() => {
  if (!keywords.value) return tableList.value
  return tableList.value.filter((ele) =>
    ele.table_name.toLowerCase().includes(keywords.value.toLowerCase())
  )
})
const total = ref(0)
const showNum = ref(0)
const currentTable = ref<any>({})
const ds = ref<any>({})
const btnSelect = ref('d')
const isDrag = ref(false)

// ===== 数据源类型检测 =====
const isPdfType = computed(() => {
  const d = ds.value
  if (!d) return false
  if (d.type === 'pdf') return true
  if (d.type_name === 'PDF') return true
  // 移除基于表名前缀 'pdf_' 的回退检测
  // 用户可能创建名为 'pdf_sales' 的普通数据库表，会被错误识别为 PDF 数据源
  // 数据源类型应严格依赖 type/type_name 字段，不做启发式猜测
  return false
})
const isExcelType = computed(() => ds.value?.type === 'excel' || ds.value?.type_name === 'Excel')
const isCsvType = computed(() => ds.value?.type === 'csv' || ds.value?.type_name === 'CSV')
const isFileType = computed(() => isPdfType.value || isExcelType.value || isCsvType.value)
const isDatabaseType = computed(() => !isFileType.value && !!ds.value?.type)

const dsTypeLabel = computed(() => {
  if (isPdfType.value) return t('ds_pdf.type_pdf')
  if (isExcelType.value) return t('ds_pdf.type_excel')
  if (isCsvType.value) return t('ds_pdf.type_csv')
  return ds.value?.type_name || t('ds_pdf.type_database')
})

const dsTypeIcon = computed(() => {
  if (isPdfType.value) return '📄'
  if (isExcelType.value) return '📊'
  if (isCsvType.value) return '📋'
  return '🗄️'
})

// ===== Excel/CSV 概览统计 =====
const fileOverviewStats = computed(() => {
  if (!isExcelType.value && !isCsvType.value) return null
  const tables = tableList.value || []
  const totalFields = fieldStatsCache.value.totalFields
  return { sheetCount: tables.length, totalFields, type: isExcelType.value ? 'Excel' : 'CSV' }
})

const fieldStatsCache = ref<{ totalFields: number; fieldsByTable: Record<string, any[]> }>({
  totalFields: 0, fieldsByTable: {},
})

const loadFieldStats = async () => {
  if (!isExcelType.value && !isCsvType.value && !isDatabaseType.value) return
  const tables = tableList.value
  const targetTables = isDatabaseType.value ? tables.slice(0, 20) : tables
  let total = 0
  const byTable: Record<string, any[]> = {}
  const results = await Promise.allSettled(
    targetTables.map(async (table: any) => {
      try {
        const fields = await datasourceApi.fieldList(table.id)
        return { name: table.table_name, fields }
      } catch { return { name: table.table_name, fields: [] } }
    })
  )
  for (const result of results) {
    if (result.status === 'fulfilled') {
      byTable[result.value.name] = result.value.fields
      total += result.value.fields.length
    }
  }
  fieldStatsCache.value = { totalFields: total, fieldsByTable: byTable }
}

// ===== 数据库连接信息 =====
const dbConnectionInfo = computed(() => {
  if (!isDatabaseType.value) return null
  const d = ds.value
  if (!d?.configuration) return null
  try {
    const conf = JSON.parse(decrypted(d.configuration))
    return { host: conf.host || '-', port: conf.port || '-', database: conf.database || '-', dbSchema: conf.dbSchema || '-' }
  } catch { return null }
})
const dbConnectionStatus = ref<'unknown' | 'connected' | 'disconnected'>('unknown')
const checkDbConnection = () => {
  if (!isDatabaseType.value || !props.info.id) return
  dbConnectionStatus.value = 'unknown'
  datasourceApi.check_by_id(props.info.id).then((res: any) => {
    dbConnectionStatus.value = res ? 'connected' : 'disconnected'
  }).catch(() => { dbConnectionStatus.value = 'disconnected' })
}

const showOverviewPanel = computed(() => {
  if (isPdfType.value) return !currentTable.value.table_name && !activeRelationship.value
  return !currentTable.value.table_name && !activeRelationship.value && tableList.value.length > 0
})
const pdfActiveName = ref('overview')
const pdfDocInfo = ref<any>(null)
const pdfChunks = ref<any[]>([])
const pdfStats = ref<any>(null)
const pdfSections = ref<string[]>([])
const pdfVectorization = ref<any>(null)
const pdfLoading = ref(false)
const pdfLoadError = ref('')
const expandedSection = ref<number | null>(null)
const expandedTableIdx = ref<number | null>(null)
const expandedChunks = ref<Set<number>>(new Set())
const showRawText = ref(false)

const getChunkTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    section: t('ds_pdf.chunk_type_section'),
    section_split: t('ds_pdf.chunk_type_section_split'),
    table: t('ds_pdf.chunk_type_table'),
    table_overlap: t('ds_pdf.chunk_type_table_overlap'),
    sliding_window: t('ds_pdf.chunk_type_sliding_window'),
    text: t('ds_pdf.chunk_type_section'),
  }
  return map[type] || type
}
const getChunkTypeClass = (type: string) => {
  if (type === 'table') return 'tag-table'
  if (type === 'table_overlap') return 'tag-overlap'
  if (type === 'sliding_window') return 'tag-window'
  return 'tag-text'
}
const getChunkTypeIcon = (type: string) => {
  if (type === 'table') return '📊'
  if (type === 'table_overlap') return '🔄'
  if (type === 'sliding_window') return '🪟'
  if (type === 'section_split') return '✂️'
  return '📄'
}
const getSectionChunks = (sectionTitle: string) => pdfChunks.value.filter((c: any) => c.section_title === sectionTitle)
const tableChunksList = computed(() => pdfChunks.value.filter((c: any) => c.chunk_type === 'table'))
const vectorizedPercent = computed(() => {
  const v = pdfVectorization.value
  if (!v || !v.total_chunks) return 0
  return Math.round((v.vectorized_count / v.total_chunks) * 100)
})
const toggleSectionExpand = (idx: number) => { expandedSection.value = expandedSection.value === idx ? null : idx }
const toggleTableIdxExpand = (idx: number) => { expandedTableIdx.value = expandedTableIdx.value === idx ? null : idx }
const toggleChunkExpand = (id: number) => {
  const s = new Set(expandedChunks.value)
  if (s.has(id)) s.delete(id); else s.add(id)
  expandedChunks.value = s
}
const formatFileSize = (bytes: number) => {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// 分块类型分布统计（用于可视化）
const chunkTypeDistribution = computed(() => {
  if (!pdfStats.value) return []
  const items: { type: string; label: string; count: number; icon: string; cls: string }[] = []
  const s = pdfStats.value
  if (s.text_chunks) items.push({ type: 'text', label: t('ds_pdf.chunk_type_section'), count: s.text_chunks, icon: '📄', cls: 'tag-text' })
  if (s.section_split_chunks) items.push({ type: 'section_split', label: t('ds_pdf.chunk_type_section_split'), count: s.section_split_chunks, icon: '✂️', cls: 'tag-text' })
  if (s.table_chunks) items.push({ type: 'table', label: t('ds_pdf.chunk_type_table'), count: s.table_chunks, icon: '📊', cls: 'tag-table' })
  if (s.table_overlap_chunks) items.push({ type: 'table_overlap', label: t('ds_pdf.chunk_type_table_overlap'), count: s.table_overlap_chunks, icon: '🔄', cls: 'tag-overlap' })
  if (s.sliding_window_chunks) items.push({ type: 'sliding_window', label: t('ds_pdf.chunk_type_sliding_window'), count: s.sliding_window_chunks, icon: '🪟', cls: 'tag-window' })
  return items
})
const maxChunkTypeCount = computed(() => Math.max(...chunkTypeDistribution.value.map(d => d.count), 1))

// 平均分块长度
const avgChunkLength = computed(() => {
  if (!pdfStats.value || !pdfStats.value.total_chunks) return 0
  return Math.round((pdfStats.value.total_chunk_chars || 0) / pdfStats.value.total_chunks)
})

// 检索就绪度评估
const searchReadiness = computed(() => {
  const pct = vectorizedPercent.value
  if (pct >= 80) return { level: 'good', label: t('ds_pdf.search_ready_good'), color: '#22c55e' }
  if (pct >= 40) return { level: 'partial', label: t('ds_pdf.search_ready_partial'), color: '#f59e0b' }
  return { level: 'low', label: t('ds_pdf.search_ready_low'), color: '#ef4444' }
})

const loadPdfDocInfo = () => {
  if (!props.info.id) return
  pdfLoadError.value = ''
  pdfLoading.value = true
  datasourceApi.getDocumentByDatasource(props.info.id).then((res: any) => {
    if (!res.document) { pdfLoadError.value = t('ds_pdf.doc_not_found'); return }
    pdfDocInfo.value = res.document
    pdfChunks.value = res.chunks || []
    pdfStats.value = res.stats || null
    pdfSections.value = res.sections || []
    pdfVectorization.value = res.vectorization || null
  }).catch((err: any) => {
    const msg = err?.msg || err?.message || 'Unknown error'
    if (msg.includes('非PDF数据源') || msg.includes('not a PDF')) { pdfLoadError.value = '' }
    else { pdfLoadError.value = t('ds_pdf.load_failed_detail', { msg }) }
  }).finally(() => { pdfLoading.value = false })
}
const tableName = ref<any[]>([])
const pageInfo = reactive({ currentPage: 1, pageSize: 10, total: 0 })
const handleRelationship = () => { activeRelationship.value = !activeRelationship.value; currentTable.value = {} }
const singleDragStartD = (e: DragEvent, ele: any) => { isDrag.value = true; e.dataTransfer!.setData('table', JSON.stringify(ele)) }
const getTableName = (val: any) => { tableName.value = val }
const singleDragEnd = () => { isDrag.value = false }
const handleCurrentChange = (val: number) => { pageInfo.currentPage = val }
const fieldListComputed = computed(() => {
  const { currentPage, pageSize } = pageInfo
  return fieldList.value.slice((currentPage - 1) * pageSize, currentPage * pageSize)
})

const init = () => {
  initLoading.value = true
  datasourceApi.getDs(props.info.id).then((res) => {
    ds.value = res
    fieldList.value = []
    pageInfo.total = 0
    pageInfo.currentPage = 1
    datasourceApi.tableList(props.info.id).then((tableRes) => {
      tableList.value = tableRes
      if (isPdfType.value) loadPdfDocInfo()
      if (isExcelType.value || isCsvType.value || isDatabaseType.value) loadFieldStats()
      if (isDatabaseType.value) checkDbConnection()
    }).catch(() => { ElMessage.error(t('common.load_failed')) }).finally(() => { initLoading.value = false })
  }).catch(() => { ElMessage.error(t('common.load_failed')); initLoading.value = false })
}
onMounted(() => { init() })
const tableComment = ref('')
const fieldDialog = ref<boolean>(false)
const tableDialog = ref<boolean>(false)
const fieldComment = ref('')
const currentField = ref<any>({})
const previewData = ref<any>({})
const fieldList = ref<any>([])

const buildData = () => ({ table: currentTable.value, fields: fieldList.value })
const handleSelectTableList = () => { paramsFormRef.value.open(props.info) }

const clickTable = (table: any) => {
  if (activeRelationship.value) return
  // PDF数据源使用 isPdfType（基于 ds.type/type_name）判断，
  // 移除 table_name?.startsWith('pdf_') 前缀检测——普通数据库表名可能以 pdf_ 开头
  if (isPdfType.value) {
    currentTable.value = {}; return
  }
  loading.value = true
  currentTable.value = table
  fieldList.value = []
  pageInfo.total = 0
  previewData.value = {}
  datasourceApi.fieldList(table.id).then((res) => {
    fieldList.value = res
    pageInfo.total = res.length
    pageInfo.currentPage = 1
    if (btnSelect.value === 'q') {
      datasourceApi.previewData(props.info.id, buildData()).then((res) => {
        previewData.value = res; total.value = res?.data?.length || 0; showNum.value = res?.data?.length || 0
      }).catch(() => { ElMessage.error(t('common.load_failed')) })
    }
  }).catch(() => { ElMessage.error(t('common.load_failed')) }).finally(() => { loading.value = false })
}

const closeTable = () => { tableDialog.value = false }
const editTable = () => { tableComment.value = currentTable.value.custom_comment; tableDialog.value = true }
const saveTable = () => {
  currentTable.value.custom_comment = tableComment.value
  datasourceApi.saveTable(currentTable.value).then(() => {
    closeTable()
    const item = tableList.value.find((t: any) => t.id === currentTable.value.id)
    if (item) item.custom_comment = tableComment.value
    ElMessage({ message: t('common.save_success'), type: 'success', showClose: true })
  }).catch(() => { ElMessage.error(t('common.save_failed')) })
}
const closeField = () => { fieldDialog.value = false }

const refresh = () => {
  emits('refresh')
  datasourceApi.tableList(props.info.id).then((res) => {
    tableList.value = res
    if (!currentTable.value.table_name) return
    const nameArr = tableList.value.map((ele: any) => ele.table_name)
    if (!nameArr.includes(currentTable.value.table_name)) currentTable.value = {}
  }).catch(() => { ElMessage.error(t('common.load_failed')) })
}

const saveField = () => {
  currentField.value.custom_comment = fieldComment.value
  datasourceApi.saveField(currentField.value).then(() => {
    closeField()
    ElMessage({ message: t('common.save_success'), type: 'success', showClose: true })
  }).catch(() => { ElMessage.error(t('common.save_failed')) })
}

const editField = (row: any) => { currentField.value = row; fieldComment.value = currentField.value.custom_comment; fieldDialog.value = true }

const changeStatus = (row: any) => {
  currentField.value = row
  datasourceApi.saveField(currentField.value).then(() => {
    // 移除 closeField() 调用（与 TableList.vue 保持一致）
    // changeStatus 由 el-switch @change 触发，与字段注释编辑对话框无关
    ElMessage({ message: t('common.save_success'), type: 'success', showClose: true })
  }).catch(() => { row.checked = !row.checked; ElMessage.error(t('common.save_failed')) })
}

const emits = defineEmits(['back', 'refresh'])
const back = () => { emits('back') }

const renderHeader = ({ column }: any) => {
  const span = document.createElement('span')
  span.innerText = column.label
  document.body.appendChild(span)
  const spanWidth = span.getBoundingClientRect().width + 20
  column.minWidth = column.minWidth > spanWidth ? column.minWidth : spanWidth
  document.body.removeChild(span)
  return column.label
}

const btnSelectClick = (val: any) => {
  btnSelect.value = val
  loading.value = true
  if (val === 'd') {
    datasourceApi.fieldList(currentTable.value.id).then((res) => {
      fieldList.value = res; pageInfo.total = res.length; pageInfo.currentPage = 1
    }).catch(() => { ElMessage.error(t('common.load_failed')) }).finally(() => { loading.value = false })
  } else {
    datasourceApi.previewData(props.info.id, buildData()).then((res) => {
      previewData.value = res; total.value = res?.data?.length || 0; showNum.value = res?.data?.length || 0
    }).catch(() => { ElMessage.error(t('common.load_failed')) }).finally(() => { loading.value = false })
  }
}
</script>

<template>
  <div class="data-table no-padding">
    <div class="info">
      <el-button text @click="back">{{ $t('ds.title') }}</el-button>
      <el-icon size="12"><icon_right_outlined /></el-icon>
      <div class="name">{{ info.name }}</div>
    </div>
    <div class="content">
      <div class="side-list">
        <div class="select-table_top">
          {{ isPdfType ? t('ds_pdf.document_content') : isExcelType ? t('ds_pdf.sheet_label') : $t('ds.tables') }}
          <el-tooltip v-if="!isPdfType" effect="dark" :content="$t('ds.form.choose_tables')" placement="top">
            <el-icon size="18" @click="handleSelectTableList"><icon_form_outlined /></el-icon>
          </el-tooltip>
        </div>

        <!-- PDF 左侧边栏：文档档案卡 + 流水线导航 -->
        <template v-if="isPdfType">
          <div v-loading="pdfLoading" class="list-content pdf-sidebar">
            <!-- 文档档案卡 -->
            <div v-if="pdfDocInfo" class="pdf-profile-card">
              <div class="profile-icon">📄</div>
              <div class="profile-info">
                <div class="profile-name" :title="pdfDocInfo.filename">{{ pdfDocInfo.filename }}</div>
                <div class="profile-meta">{{ formatFileSize(pdfDocInfo.file_size) }} · {{ pdfDocInfo.processing_time?.toFixed(1) }}s</div>
              </div>
            </div>

            <!-- 快速统计 -->
            <div v-if="pdfStats" class="pdf-quick-stats">
              <div class="qs-item"><span class="qs-num">{{ pdfStats.total_pages }}</span><span class="qs-label">{{ t('ds_pdf.pages_unit') }}</span></div>
              <div class="qs-item"><span class="qs-num">{{ pdfStats.total_sections }}</span><span class="qs-label">{{ t('ds_pdf.section_paragraphs') }}</span></div>
              <div class="qs-item"><span class="qs-num">{{ pdfStats.total_chunks }}</span><span class="qs-label">{{ t('ds_pdf.text_chunks') }}</span></div>
              <div class="qs-item"><span class="qs-num">{{ vectorizedPercent }}%</span><span class="qs-label">{{ t('ds_pdf.vectorized') }}</span></div>
            </div>

            <!-- 流水线阶段导航 → 文档视角导航 -->
            <div class="pdf-nav-stages">
              <div class="nav-stage" :class="{ active: pdfActiveName === 'overview' }" @click="pdfActiveName = 'overview'">
                <span class="nav-icon">📋</span>
                <div class="nav-info">
                  <span class="nav-text">{{ t('ds_pdf.nav_overview') }}</span>
                  <span class="nav-sub">{{ t('ds_pdf.nav_overview_desc') }}</span>
                </div>
              </div>
              <div class="nav-stage" :class="{ active: pdfActiveName === 'content' }" @click="pdfActiveName = 'content'">
                <span class="nav-icon">📖</span>
                <div class="nav-info">
                  <span class="nav-text">{{ t('ds_pdf.nav_content') }}</span>
                  <span class="nav-sub">{{ t('ds_pdf.nav_content_desc') }}</span>
                </div>
              </div>
              <div class="nav-stage" :class="{ active: pdfActiveName === 'search' }" @click="pdfActiveName = 'search'">
                <span class="nav-icon">🔍</span>
                <div class="nav-info">
                  <span class="nav-text">{{ t('ds_pdf.nav_search_quality') }}</span>
                  <span class="nav-sub">{{ t('ds_pdf.nav_search_quality_desc') }}</span>
                </div>
                <span class="nav-readiness-dot" :style="{ background: searchReadiness.color }"></span>
              </div>
            </div>

            <div v-if="!pdfLoading && !pdfDocInfo" class="no-data">
              <div class="no-data-msg" style="text-align: center; padding: 20px 0;">
                <div style="font-size: 32px; margin-bottom: 8px;">📄</div>
                <div style="color: rgba(196, 181, 253, 0.6); font-size: 12px;">{{ t('ds_pdf.pdf_no_tables_hint') }}</div>
              </div>
            </div>
          </div>
        </template>

        <!-- 非PDF数据源：搜索框 + 表列表 -->
        <template v-else>
        <el-input v-model="keywords" clearable :placeholder="$t('datasource.search')">
          <template #prefix><el-icon><icon_searchOutline_outlined class="svg-icon" /></el-icon></template>
        </el-input>
        <div v-loading="initLoading" class="list-content">
          <div v-if="currentTable.table_name" class="model pdf-back-doc" @click="currentTable = {}">
            <span style="margin-right: 6px;">{{ dsTypeIcon }}</span>
            <span class="name">{{ isPdfType ? t('ds_pdf.back_to_doc_overview') : t('ds_pdf.back_to_data_overview') }}</span>
          </div>
          <el-scrollbar v-if="tableListWithSearch.length">
            <div v-for="ele in tableListWithSearch" :key="ele.table_name"
              :draggable="activeRelationship && !tableName.includes(ele.id)" class="model"
              :class="[currentTable.table_name === ele.table_name && 'isActive', tableName.includes(ele.id) && activeRelationship && 'disabled-table']"
              :title="isFileType ? (ele.custom_comment || ele.table_name) : ele.table_name"
              @dragstart="($event: any) => singleDragStartD($event, ele)" @dragend="singleDragEnd" @click="clickTable(ele)">
              <el-icon size="16"><icon_form_outlined /></el-icon>
              <span class="name">{{ isFileType ? (ele.custom_comment || ele.table_name) : ele.table_name }}</span>
            </div>
          </el-scrollbar>
          <EmptyBackground v-if="!!keywords && !tableListWithSearch.length" :description="$t('datasource.relevant_content_found')" img-type="tree" style="width: 100%" />
          <div v-else-if="!initLoading && !tableListWithSearch.length" class="no-data">
            <div v-if="isPdfType" class="no-data-msg" style="text-align: center; padding: 20px 0;">
              <div style="font-size: 32px; margin-bottom: 8px;">📄</div>
              <div style="color: rgba(196, 181, 253, 0.6); font-size: 12px;">{{ t('ds_pdf.pdf_no_tables_hint') }}</div>
            </div>
            <div v-else class="no-data-msg">
              <div>{{ $t('datasource.no_table') }}</div>
              <el-button type="primary" link @click="handleSelectTableList">{{ $t('datasource.go_add') }}</el-button>
            </div>
          </div>
        </div>
        <div class="table-relationship" v-if="!isPdfType">
          <div :class="activeRelationship && 'active'" class="btn" @click="handleRelationship">
            <el-icon size="16"><icon_mindnote_outlined /></el-icon>
            {{ t('training.table_relationship_management') }}
          </div>
        </div>
        </template>
      </div>

      <div v-if="activeRelationship && !isPdfType" class="relationship-content">
        <div class="title">{{ t('training.table_relationship_management') }}</div>
        <div class="content"><TableRelationship :id="info.id" :dragging="isDrag" @get-table-name="getTableName" /></div>
      </div>

      <div v-if="!currentTable.table_name && !activeRelationship && tableList.length === 0 && !initLoading && !isPdfType" class="empty-right-panel">
        <div class="empty-hint">
          <el-icon size="48" style="color: rgba(139, 92, 246, 0.3); margin-bottom: 16px"><icon_form_outlined /></el-icon>
          <p>{{ t('datasource.select_table_hint') }}</p>
        </div>
      </div>

      <!-- ===== 数据源概览面板 ===== -->
      <div v-if="showOverviewPanel && !currentTable.table_name && !activeRelationship"
        v-loading="isPdfType ? pdfLoading : initLoading" class="info-table ds-overview-panel">
        <div class="table-name overview-header">
          <div class="name"><span class="type-icon">{{ dsTypeIcon }}</span>{{ info.name }}</div>
          <div class="notes">
            <span class="ds-type-tag">{{ dsTypeLabel }}</span>
            <span v-if="isDatabaseType && dbConnectionStatus !== 'unknown'" class="connection-indicator" :class="'status-' + dbConnectionStatus">
              <span class="status-dot"></span>
              {{ dbConnectionStatus === 'connected' ? t('ds.status_connected') : t('ds.connection_failed') }}
            </span>
            <span style="margin-left: auto; font-size: 12px; color: rgba(196,181,253,0.5);">
              {{ isPdfType ? (pdfStats?.total_pages ? t('ds_pdf.overview_summary_pages', { count: pdfStats.total_pages }) : '') : isExcelType ? t('ds_pdf.overview_summary_sheets', { count: tableList.length }) : isCsvType ? t('ds_pdf.overview_summary_one_table') : t('ds_pdf.overview_summary_tables', { count: tableList.length }) }}
            </span>
          </div>
        </div>

        <div class="table-content" style="overflow-y: auto;">
          <!-- ========== PDF 概览：RAG 处理报告 ========== -->
          <template v-if="isPdfType">
            <div v-if="pdfLoadError" class="pdf-error-state">
              <div class="error-icon">⚠️</div>
              <p class="error-text">{{ pdfLoadError }}</p>
              <el-button type="primary" size="small" @click="loadPdfDocInfo">{{ t('ds_pdf.reload') }}</el-button>
            </div>
            <template v-else-if="!pdfLoading">

              <!-- ═══ 文档概览 ═══ -->
              <div v-if="pdfActiveName === 'overview'" class="preview-or-schema overflow-preview pdf-stage-view">

                <!-- RAG 处理流水线可视化（水平三阶段） -->
                <div class="pipeline-summary">
                  <div class="ps-stage">
                    <div class="ps-icon">📖</div>
                    <div class="ps-title">{{ t('ds_pdf.parsing_stage') }}</div>
                    <div class="ps-metrics" v-if="pdfStats">
                      <span>{{ pdfStats.total_pages }} {{ t('ds_pdf.pages_unit') }}</span>
                      <span>{{ pdfStats.total_sections }} {{ t('ds_pdf.section_paragraphs') }}</span>
                      <span>{{ pdfStats.table_chunks || 0 }} {{ t('ds_pdf.recognized_tables') }}</span>
                    </div>
                  </div>
                  <div class="ps-arrow">→</div>
                  <div class="ps-stage">
                    <div class="ps-icon">✂️</div>
                    <div class="ps-title">{{ t('ds_pdf.preprocessing_stage') }}</div>
                    <div class="ps-metrics" v-if="pdfStats">
                      <span>{{ pdfStats.total_chunks }} {{ t('ds_pdf.text_chunks') }}</span>
                      <span>{{ avgChunkLength }} {{ t('ds_pdf.chars_unit') }}/{{ t('ds_pdf.chunk_config_title') }}</span>
                    </div>
                  </div>
                  <div class="ps-arrow">→</div>
                  <div class="ps-stage">
                    <div class="ps-icon">🔗</div>
                    <div class="ps-title">{{ t('ds_pdf.vectorization_stage') }}</div>
                    <div class="ps-metrics" v-if="pdfVectorization">
                      <span>{{ pdfVectorization.vectorized_count || 0 }} {{ t('ds_pdf.vec_done_label') }}</span>
                      <span>{{ vectorizedPercent }}%</span>
                    </div>
                    <div class="ps-readiness" :style="{ color: searchReadiness.color }">{{ searchReadiness.label }}</div>
                  </div>
                </div>

              </div>

              <!-- ═══ 内容浏览 ═══ -->
              <div v-if="pdfActiveName === 'content'" class="preview-or-schema overflow-preview pdf-stage-view">

                <!-- 章节内容（可展开） -->
                <div class="pdf-extract-block" v-if="pdfSections.length > 0">
                  <div class="peb-header">
                    <span class="peb-icon">📑</span>
                    <span class="peb-title">{{ t('ds_pdf.content_sections_title') }}</span>
                    <span class="peb-count">{{ pdfSections.length }} {{ t('ds_pdf.section_paragraphs') }}</span>
                  </div>
                  <div class="section-tree">
                    <template v-for="(sec, idx) in pdfSections" :key="idx">
                      <div class="st-node" :class="{ expanded: expandedSection === idx }" @click="toggleSectionExpand(idx)">
                        <span class="st-line"></span>
                        <span class="st-dot"></span>
                        <span class="st-name">{{ sec }}</span>
                        <span class="st-badge">{{ getSectionChunks(sec).length }} {{ t('ds_pdf.text_chunks') }}</span>
                        <span class="st-arrow">{{ expandedSection === idx ? '▾' : '›' }}</span>
                      </div>
                      <div v-if="expandedSection === idx" class="st-content">
                        <template v-for="chunk in getSectionChunks(sec)" :key="chunk.id">
                          <div class="st-chunk">
                            <div class="stc-tags">
                              <span class="chunk-type-tag" :class="getChunkTypeClass(chunk.chunk_type)">{{ getChunkTypeIcon(chunk.chunk_type) }} {{ getChunkTypeLabel(chunk.chunk_type) }}</span>
                              <span class="stc-meta" v-if="chunk.page_number">{{ t('ds_pdf.page_n', { n: chunk.page_number }) }}</span>
                              <span class="stc-meta">{{ chunk.full_length }} {{ t('ds_pdf.chars_unit') }}</span>
                            </div>
                            <div class="stc-text">{{ chunk.full_text || chunk.text }}</div>
                          </div>
                        </template>
                        <div v-if="getSectionChunks(sec).length === 0" class="stc-empty">{{ t('ds_pdf.section_no_chunks') }}</div>
                      </div>
                    </template>
                  </div>
                </div>

                <!-- 文档中的表格 -->
                <div class="pdf-extract-block" v-if="tableChunksList.length > 0">
                  <div class="peb-header">
                    <span class="peb-icon">📊</span>
                    <span class="peb-title">{{ t('ds_pdf.content_tables_title') }}</span>
                    <span class="peb-count">{{ tableChunksList.length }} {{ t('ds_pdf.recognized_tables') }}</span>
                  </div>
                  <div class="table-extract-list">
                    <template v-for="(chunk, idx) in tableChunksList" :key="chunk.id">
                      <div class="tel-item" :class="{ expanded: expandedTableIdx === idx }" @click="toggleTableIdxExpand(idx)">
                        <div class="tel-head">
                          <span class="tel-badge">📊 {{ t('ds_pdf.table_index', { n: idx + 1 }) }}</span>
                          <span class="tel-meta">{{ chunk.page_number ? t('ds_pdf.page_n', { n: chunk.page_number }) : '' }} · {{ chunk.full_length }} {{ t('ds_pdf.chars_unit') }}</span>
                          <span class="tel-arrow">{{ expandedTableIdx === idx ? '▾' : '›' }}</span>
                        </div>
                        <div v-if="expandedTableIdx === idx" class="tel-content" @click.stop>
                          <pre class="tel-markdown">{{ chunk.full_text || chunk.text }}</pre>
                        </div>
                      </div>
                    </template>
                  </div>
                </div>

                <!-- 原始文本预览 -->
                <div class="pdf-extract-block" v-if="pdfDocInfo?.raw_text_preview">
                  <div class="peb-header" @click="showRawText = !showRawText" style="cursor:pointer">
                    <span class="peb-icon">📝</span>
                    <span class="peb-title">{{ t('ds_pdf.content_raw_text_title') }}</span>
                    <span class="peb-count">{{ (pdfDocInfo.raw_text_length || 0).toLocaleString() }} {{ t('ds_pdf.chars_unit') }}</span>
                    <span class="st-arrow" style="margin-left:auto">{{ showRawText ? '▾' : '›' }}</span>
                  </div>
                  <div v-if="showRawText" class="raw-text-preview">{{ pdfDocInfo.raw_text_preview }}</div>
                </div>

                <div v-if="pdfSections.length === 0 && tableChunksList.length === 0 && !pdfDocInfo?.raw_text_preview" class="stc-empty" style="text-align:center; padding: 40px 0;">
                  {{ t('ds_pdf.content_no_content') }}
                </div>
              </div>

              <!-- ═══ 检索质量 ═══ -->
              <div v-if="pdfActiveName === 'search'" class="preview-or-schema overflow-preview pdf-stage-view">

                <!-- 向量化覆盖率（含进度条） -->
                <div class="parse-overview-card">
                  <div class="poc-left">
                    <div class="poc-title">🔍 {{ t('ds_pdf.search_vectorization_coverage') }}</div>
                    <div class="poc-desc">{{ t('ds_pdf.search_quality_score') }}: <span :style="{ color: searchReadiness.color, fontWeight: 700 }">{{ searchReadiness.label }}</span></div>
                  </div>
                  <div class="poc-progress" v-if="pdfVectorization">
                    <div class="vpb-bar-wrap">
                      <div class="vpb-bar" :style="{ width: vectorizedPercent + '%' }"></div>
                    </div>
                    <div class="vpb-text">{{ t('ds_pdf.vectorized_ratio', { done: pdfVectorization.vectorized_count || 0, total: pdfVectorization.total_chunks || 0 }) }} ({{ vectorizedPercent }}%)</div>
                  </div>
                </div>

                <!-- 分块类型分布 -->
                <div class="pdf-extract-block" v-if="chunkTypeDistribution.length > 0">
                  <div class="peb-header">
                    <span class="peb-icon">📊</span>
                    <span class="peb-title">{{ t('ds_pdf.search_chunk_distribution') }}</span>
                  </div>
                  <div class="chunk-dist-bars">
                    <div v-for="item in chunkTypeDistribution" :key="item.type" class="cdb-row">
                      <span class="cdb-icon">{{ item.icon }}</span>
                      <span class="cdb-label">{{ item.label }}</span>
                      <div class="cdb-bar-wrap"><div class="cdb-bar" :class="item.cls" :style="{ width: (item.count / maxChunkTypeCount * 100) + '%' }"></div></div>
                      <span class="cdb-count">{{ item.count }}</span>
                    </div>
                  </div>
                </div>

                <!-- 嵌入与存储配置 -->
                <div class="process-method-row" style="margin-top:16px">
                  <div class="pm-card pm-wide"><div class="pm-head"><span class="pm-icon">🤖</span>{{ t('ds_pdf.search_embedding_config') }}</div><div class="pm-body pm-hl">{{ pdfVectorization?.embedding_model || 'BAAI/bge-base-zh-v1.5' }} · {{ t('ds_pdf.embedding_dim_value', { n: pdfVectorization?.embedding_dim || 768 }) }}</div></div>
                  <div class="pm-card pm-wide"><div class="pm-head"><span class="pm-icon">💾</span>{{ t('ds_pdf.search_storage_config') }}</div><div class="pm-body">{{ t('ds_pdf.vec_storage_desc') }}</div></div>
                </div>

                <!-- 跳过原因 -->
                <div class="pdf-extract-block" v-if="pdfVectorization?.skip_reasons && (pdfVectorization.skip_reasons.table_overlap > 0 || pdfVectorization.skip_reasons.short_text > 0)">
                  <div class="peb-header">
                    <span class="peb-icon">⏭️</span>
                    <span class="peb-title">{{ t('ds_pdf.search_skip_details') }}</span>
                  </div>
                  <div class="skip-reason-list">
                    <div class="sr-item" v-if="pdfVectorization.skip_reasons.table_overlap > 0"><span class="sr-icon">🔄</span><span class="sr-text">{{ t('ds_pdf.skip_reason_overlap') }}</span><span class="sr-num">{{ pdfVectorization.skip_reasons.table_overlap }}</span></div>
                    <div class="sr-item" v-if="pdfVectorization.skip_reasons.short_text > 0"><span class="sr-icon">📏</span><span class="sr-text">{{ t('ds_pdf.skip_reason_short') }}</span><span class="sr-num">{{ pdfVectorization.skip_reasons.short_text }}</span></div>
                  </div>
                </div>

                <!-- 全部分块状态 -->
                <div class="pdf-extract-block">
                  <div class="peb-header">
                    <span class="peb-icon">🧩</span>
                    <span class="peb-title">{{ t('ds_pdf.search_all_chunks') }}</span>
                    <span class="peb-count">{{ pdfChunks.length }} {{ t('ds_pdf.text_chunks') }}</span>
                  </div>
                  <div class="peb-hint">{{ t('ds_pdf.all_chunks_desc') }}</div>
                  <div class="chunk-card-list">
                    <div v-for="chunk in pdfChunks" :key="chunk.id" class="cc-item" :class="{ overlap: chunk.chunk_type === 'table_overlap' }" @click="toggleChunkExpand(chunk.id)">
                      <div class="cc-head">
                        <span class="cc-idx">{{ t('ds_pdf.chunk_index_label', { n: chunk.chunk_index }) }}</span>
                        <span class="chunk-type-tag" :class="getChunkTypeClass(chunk.chunk_type)">{{ getChunkTypeIcon(chunk.chunk_type) }} {{ getChunkTypeLabel(chunk.chunk_type) }}</span>
                        <span class="cc-meta" v-if="chunk.section_title">📑 {{ chunk.section_title }}</span>
                        <span class="cc-meta" v-if="chunk.page_number">{{ t('ds_pdf.page_n', { n: chunk.page_number }) }}</span>
                        <span class="cc-len">{{ chunk.full_length }} {{ t('ds_pdf.chars_unit') }}</span>
                        <span class="cc-vec" :class="chunk.has_embedding ? 'vec-y' : 'vec-n'">{{ chunk.has_embedding ? '✅' : '⏭️' }}</span>
                        <span class="st-arrow">{{ expandedChunks.has(chunk.id) ? '▾' : '›' }}</span>
                      </div>
                      <div v-if="expandedChunks.has(chunk.id)" class="cc-full" @click.stop>{{ chunk.full_text || chunk.text }}</div>
                      <div v-else class="cc-preview">{{ chunk.text }}</div>
                    </div>
                  </div>
                </div>
              </div>

            </template>
          </template>

          <!-- ========== Excel / CSV 统一概览 ========== -->
          <template v-if="isExcelType || isCsvType">
            <div class="preview-or-schema overflow-preview" style="margin-top: 16px;">
              <!-- NL2SQL 处理流水线可视化（水平三阶段：导入→元数据→查询就绪） -->
              <div class="pipeline-summary">
                <div class="ps-stage">
                  <div class="ps-icon">📥</div>
                  <div class="ps-title">{{ t('ds_pdf.data_pipeline_import') }}</div>
                  <div class="ps-metrics">
                    <span>{{ t('ds_pdf.data_import_upload') }}</span>
                    <span>{{ isExcelType ? t('ds_pdf.overview_summary_sheets', { count: fileOverviewStats?.sheetCount || 0 }) : t('ds_pdf.overview_summary_one_table') }}</span>
                    <span>{{ t('ds_pdf.data_import_storage') }}</span>
                  </div>
                </div>
                <div class="ps-arrow">→</div>
                <div class="ps-stage">
                  <div class="ps-icon">🔍</div>
                  <div class="ps-title">{{ t('ds_pdf.data_pipeline_metadata') }}</div>
                  <div class="ps-metrics">
                    <span>{{ t('ds_pdf.data_metadata_schema') }}</span>
                    <span>{{ fileOverviewStats?.totalFields || 0 }} {{ t('ds_pdf.fields_unit') }}</span>
                  </div>
                </div>
                <div class="ps-arrow">→</div>
                <div class="ps-stage">
                  <div class="ps-icon">⚡</div>
                  <div class="ps-title">{{ t('ds_pdf.data_pipeline_ready') }}</div>
                  <div class="ps-metrics">
                    <span>{{ t('ds_pdf.data_query_path') }}</span>
                    <span>6 {{ t('ds_pdf.data_query_components') }}</span>
                  </div>
                  <div class="ps-readiness" style="color: #22c55e;">{{ t('ds_pdf.data_ready_good') }}</div>
                </div>
              </div>

              <div class="overview-section" style="margin-top: 16px;">
                <div class="section-title">{{ isExcelType ? '📊 ' + t('ds_pdf.sheet_label') + ' ' + t('ds_pdf.data_structure') : '📋 ' + t('ds_pdf.data_structure') }}</div>
                <div class="structured-table-list">
                  <div v-for="(table, idx) in tableList" :key="table.table_name" class="structured-table-card" @click="clickTable(table)">
                    <div class="table-card-header">
                      <span class="item-idx">{{ idx + 1 }}</span>
                      <span class="table-card-name">{{ table.custom_comment || table.table_name }}</span>
                      <span class="table-card-field-count" v-if="fieldStatsCache.fieldsByTable[table.table_name]">{{ fieldStatsCache.fieldsByTable[table.table_name].length }} {{ t('ds_pdf.fields_unit') }}</span>
                      <span class="item-arrow">→</span>
                    </div>
                    <div class="table-card-fields" v-if="fieldStatsCache.fieldsByTable[table.table_name]?.length">
                      <span v-for="field in fieldStatsCache.fieldsByTable[table.table_name].slice(0, 6)" :key="field.field_name" class="field-chip">{{ field.custom_comment || field.field_name }}</span>
                      <span v-if="fieldStatsCache.fieldsByTable[table.table_name].length > 6" class="field-chip more">+{{ fieldStatsCache.fieldsByTable[table.table_name].length - 6 }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <!-- ========== 数据库概览 ========== -->
          <template v-if="isDatabaseType">
            <div class="preview-or-schema overflow-preview" style="margin-top: 16px;">
              <!-- NL2SQL 处理流水线可视化（水平三阶段：连接→元数据→查询就绪） -->
              <div class="pipeline-summary">
                <div class="ps-stage">
                  <div class="ps-icon">🔌</div>
                  <div class="ps-title">{{ t('ds_pdf.data_pipeline_import') }}</div>
                  <div class="ps-metrics">
                    <span>{{ t('ds_pdf.data_import_connect') }}</span>
                    <span>{{ tableList.length }} {{ t('ds_pdf.tables_unit') }}</span>
                  </div>
                  <div v-if="dbConnectionStatus !== 'unknown'" class="ps-readiness" :style="{ color: dbConnectionStatus === 'connected' ? '#22c55e' : '#ef4444' }">
                    {{ dbConnectionStatus === 'connected' ? t('ds.status_connected') : t('ds.connection_failed') }}
                  </div>
                </div>
                <div class="ps-arrow">→</div>
                <div class="ps-stage">
                  <div class="ps-icon">🔍</div>
                  <div class="ps-title">{{ t('ds_pdf.data_pipeline_metadata') }}</div>
                  <div class="ps-metrics">
                    <span>{{ t('ds_pdf.data_metadata_schema') }}</span>
                    <span>{{ fieldStatsCache.totalFields }} {{ t('ds_pdf.fields_unit') }}</span>
                  </div>
                </div>
                <div class="ps-arrow">→</div>
                <div class="ps-stage">
                  <div class="ps-icon">⚡</div>
                  <div class="ps-title">{{ t('ds_pdf.data_pipeline_ready') }}</div>
                  <div class="ps-metrics">
                    <span>{{ t('ds_pdf.data_query_path') }}</span>
                    <span>6 {{ t('ds_pdf.data_query_components') }}</span>
                  </div>
                  <div class="ps-readiness" style="color: #22c55e;">{{ t('ds_pdf.data_ready_good') }}</div>
                </div>
              </div>

              <div class="db-connection-panel" v-if="dbConnectionInfo">
                <div class="db-conn-row"><span class="db-conn-label">{{ t('ds.form.host') }}</span><span class="db-conn-value">{{ dbConnectionInfo.host }}:{{ dbConnectionInfo.port }}</span></div>
                <div class="db-conn-row"><span class="db-conn-label">{{ t('ds.form.database') }}</span><span class="db-conn-value">{{ dbConnectionInfo.database }}</span></div>
                <div class="db-conn-row" v-if="dbConnectionInfo.dbSchema && dbConnectionInfo.dbSchema !== '-'"><span class="db-conn-label">Schema</span><span class="db-conn-value">{{ dbConnectionInfo.dbSchema }}</span></div>
                <div class="db-conn-row"><span class="db-conn-label">{{ t('ds.type') }}</span><span class="db-conn-value">{{ ds.type_name || ds.type }}</span></div>
                <div class="db-conn-row"><span class="db-conn-label">{{ t('ds_pdf.selected_tables') }}</span><span class="db-conn-value">{{ tableList.length }} {{ t('ds_pdf.tables_unit') }} · {{ fieldStatsCache.totalFields }} {{ t('ds_pdf.fields_unit') }}</span></div>
              </div>
              <div class="overview-section" style="margin-top: 16px;">
                <div class="section-title">🗄️ {{ t('ds_pdf.table_structure_overview') }}</div>
                <div class="structured-table-list">
                  <div v-for="(table, idx) in tableList.slice(0, 20)" :key="table.table_name" class="structured-table-card" @click="clickTable(table)">
                    <div class="table-card-header">
                      <span class="item-idx">{{ idx + 1 }}</span>
                      <span class="table-card-name">{{ table.table_name }}</span>
                      <span class="table-card-comment" v-if="table.custom_comment">{{ table.custom_comment }}</span>
                      <span class="table-card-field-count" v-if="fieldStatsCache.fieldsByTable[table.table_name]">{{ fieldStatsCache.fieldsByTable[table.table_name].length }} {{ t('ds_pdf.fields_unit') }}</span>
                      <span class="item-arrow">→</span>
                    </div>
                    <div class="table-card-fields" v-if="fieldStatsCache.fieldsByTable[table.table_name]?.length">
                      <span v-for="field in fieldStatsCache.fieldsByTable[table.table_name].slice(0, 6)" :key="field.field_name" class="field-chip">{{ field.custom_comment || field.field_name }}</span>
                      <span v-if="fieldStatsCache.fieldsByTable[table.table_name].length > 6" class="field-chip more">+{{ fieldStatsCache.fieldsByTable[table.table_name].length - 6 }}</span>
                    </div>
                  </div>
                  <div v-if="tableList.length > 20" class="section-item" style="justify-content: center; color: rgba(196,181,253,0.5);">{{ t('ds_pdf.more_tables_hint', { count: tableList.length - 20 }) }}</div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- 选中表后的详情视图 -->
      <div v-if="currentTable.table_name && !activeRelationship" v-loading="loading" class="info-table">
        <div class="table-name">
          <div class="name">{{ isFileType ? (currentTable.custom_comment || currentTable.table_name) : currentTable.table_name }}</div>
          <div class="notes">
            <template v-if="isFileType && currentTable.custom_comment">{{ t('ds_pdf.table_name_label') }}: {{ currentTable.table_name }}</template>
            <template v-else>{{ $t('about.remark') }}: <span :title="currentTable.custom_comment" class="field-notes">{{ currentTable.custom_comment || '-' }}</span></template>
            <el-tooltip :offset="14" effect="dark" :content="$t('datasource.edit')" placement="top">
              <el-icon style="margin-left: 8px; cursor: pointer" size="16" @click="editTable"><edit /></el-icon>
            </el-tooltip>
          </div>
        </div>
        <div class="table-content">
          <div class="btn-select">
            <el-button :class="[btnSelect === 'd' && 'is-active']" text @click="btnSelectClick('d')">{{ t('ds.table_schema') }}</el-button>
            <el-button :class="[btnSelect === 'q' && 'is-active']" text @click="btnSelectClick('q')">{{ t('ds.preview') }}</el-button>
          </div>
          <div v-if="!loading" class="preview-or-schema" :class="btnSelect === 'q' && 'overflow-preview'">
            <div v-if="btnSelect === 'd'" class="table-content_preview">
              <el-table row-class-name="hover-icon_edit" :data="fieldListComputed" style="width: 100%">
                <el-table-column prop="field_name" :label="t('datasource.field_name')" width="180" />
                <el-table-column prop="field_type" :label="t('datasource.field_type')" width="180" />
                <el-table-column prop="field_comment" :label="t('datasource.field_original_notes')" />
                <el-table-column :label="t('datasource.field_notes_1')">
                  <template #default="scope">
                    <div class="field-comment">
                      <span :title="scope.row.custom_comment" class="notes-in_table">{{ scope.row.custom_comment }}</span>
                      <el-tooltip :offset="14" effect="dark" :content="$t('datasource.edit')" placement="top">
                        <el-icon class="action-btn" size="16" @click="editField(scope.row)"><edit /></el-icon>
                      </el-tooltip>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column :label="t('datasource.enabled_status')" width="180">
                  <template #default="scope">
                    <div style="display: flex; align-items: center"><el-switch v-model="scope.row.checked" size="small" @change="changeStatus(scope.row)" /></div>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <div v-if="fieldList.length && btnSelect === 'd'" class="pagination-container">
              <el-pagination :current-page="pageInfo.currentPage" :page-size="10"
                :background="true" layout="total, prev, pager, next, jumper"
                :total="pageInfo.total" @current-change="handleCurrentChange" />
            </div>
            <template v-if="btnSelect === 'q'">
              <template v-if="previewData.data && previewData.data.length">
                <div class="preview-num">{{ t('ds.pieces_in_total', { msg: total, ms: showNum }) }}</div>
                <el-table :data="previewData.data" style="width: 100%">
                  <el-table-column v-for="(c, index) in previewData.fields" :key="index" :prop="c" :label="c" :render-header="renderHeader" />
                </el-table>
              </template>
              <EmptyBackground v-else :description="t('datasource.no_preview_data')" img-type="tree" style="width: 100%; margin-top: 40px" />
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
  <!-- 对话框 -->
  <el-dialog v-model="tableDialog" :title="t('datasource.table_notes')" width="600" :destroy-on-close="true" :close-on-click-modal="false" :show-close="false" modal-class="notes-dialog" @closed="closeTable">
    <el-input v-model="tableComment" :placeholder="$t('datasource.please_enter')" :autosize="{ minRows: 3.64, maxRows: 11.095 }" type="textarea" clearable />
    <div style="display: flex; justify-content: flex-end; margin-top: 20px">
      <el-button secondary @click="closeTable">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" @click="saveTable">{{ t('common.save') }}</el-button>
    </div>
  </el-dialog>
  <el-dialog v-model="fieldDialog" :title="t('datasource.field_notes')" width="600" :destroy-on-close="true" :close-on-click-modal="false" :show-close="false" modal-class="notes-dialog" @closed="closeField">
    <el-input v-model="fieldComment" :placeholder="$t('datasource.please_enter')" :autosize="{ minRows: 3.64, maxRows: 11.095 }" clearable type="textarea" />
    <div style="display: flex; justify-content: flex-end; margin-top: 20px">
      <el-button secondary @click="closeField">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" @click="saveField">{{ t('common.save') }}</el-button>
    </div>
  </el-dialog>
  <ParamsForm ref="paramsFormRef" @refresh="refresh"></ParamsForm>
</template>

<style lang="less" scoped>
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@dark-bg: #0f0a1a;
@dark-bg-secondary: #1a1225;
@dark-bg-card: rgba(26, 18, 37, 0.85);
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

.data-table {
  height: 100%;
  background: linear-gradient(180deg, @dark-bg 0%, @dark-bg-secondary 100%);
  .info {
    height: 56px; width: 100%; padding-left: 20px;
    display: flex; align-items: center;
    font-weight: 400; font-size: 14px; line-height: 22px;
    color: @dark-text-muted;
    border-bottom: 1px solid @dark-border;
    background: rgba(139, 92, 246, 0.03);
    .ed-button { height: 22px; line-height: 22px; color: @dark-text-secondary; transition: all 0.2s ease;
      &:hover { background: rgba(139, 92, 246, 0.15); color: @primary-400; }
      &:active { color: @primary-500; background: rgba(139, 92, 246, 0.25); }
    }
    .ed-icon { color: @dark-text-muted; }
    .name { color: @dark-text; margin-left: 4px; font-weight: 500; }
  }
  .content {
    height: calc(100% - 56px); position: relative; display: flex;
    .side-list {
      width: 280px; padding: 8px 16px; height: 100%;
      border-right: 1px solid @dark-border;
      background: rgba(139, 92, 246, 0.02);
      overflow: hidden; box-sizing: border-box;
      .table-relationship {
        height: 56px; width: 100%; display: flex; align-items: center; margin-top: 20px; position: relative;
        &::after { content: ''; width: calc(100% + 32px); position: absolute; left: -16px; background-color: @dark-border; top: 0; height: 1px; }
        .btn {
          width: 100%; height: 36px; cursor: pointer; border-radius: 10px;
          display: flex; align-items: center; padding-left: 12px;
          color: @dark-text-secondary; font-weight: 500; transition: all 0.2s ease;
          .ed-icon { color: @dark-text-muted; margin-right: 10px; transition: color 0.2s ease; }
          &:hover { background: rgba(139, 92, 246, 0.1); color: @dark-text; .ed-icon { color: @primary-400; } }
          &.active { color: @primary-400; background: rgba(139, 92, 246, 0.2); .ed-icon { color: @primary-400; } }
        }
      }
      .select-table_top {
        height: 40px; display: flex; align-items: center; justify-content: space-between;
        padding: 8px; font-weight: 600; color: @dark-text;
        .ed-icon { cursor: pointer; color: @primary-400; transition: all 0.2s ease;
          &:hover { color: @primary-500; transform: scale(1.1); }
        }
      }
      .ed-input {
        margin: 8px 0; width: 100%; box-sizing: border-box;
        :deep(.ed-input__wrapper) { background: rgba(139, 92, 246, 0.08) !important; border: 1px solid @dark-border !important; border-radius: 10px; box-shadow: none !important;
          &:hover { border-color: rgba(139, 92, 246, 0.35) !important; }
          &:focus-within { border-color: @primary-500 !important; box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15) !important; }
        }
        :deep(.ed-input__inner) { color: @dark-text !important; &::placeholder { color: @dark-text-muted !important; } }
        :deep(.ed-input__prefix) { color: @dark-text-muted; }
      }
      .list-content {
        height: calc(100% - 180px);
        .no-result { margin-top: 72px; font-weight: 400; font-size: 14px; line-height: 22px; text-align: center; color: @dark-text-muted; }
        .model {
          width: 100%; height: 36px; display: flex; align-items: center; padding-left: 12px;
          border-radius: 10px; cursor: pointer; color: @dark-text-secondary; transition: all 0.2s ease; margin-bottom: 4px;
          &.disabled-table { background: rgba(139, 92, 246, 0.05) !important; color: @dark-text-muted; cursor: not-allowed; opacity: 0.6; }
          .ed-icon { color: @dark-text-muted; transition: color 0.2s ease; }
          .name { margin-left: 10px; font-weight: 500; font-size: 14px; line-height: 22px; max-width: 80%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
          &:hover { background: rgba(139, 92, 246, 0.12); color: @dark-text; .ed-icon { color: @primary-400; } }
          &.isActive { background: rgba(139, 92, 246, 0.2); color: @primary-400; .ed-icon { color: @primary-400; } }
        }
        :deep(.ed-scrollbar__wrap) {
          &::-webkit-scrollbar { width: 5px; }
          &::-webkit-scrollbar-track { background: transparent; }
          &::-webkit-scrollbar-thumb { background: rgba(139, 92, 246, 0.3); border-radius: 3px; &:hover { background: rgba(139, 92, 246, 0.5); } }
        }
      }
      .no-data {
        height: 100%; text-align: center; display: flex; align-items: center; width: 100%;
        .no-data-msg { display: inline; width: 100%; color: @dark-text-muted; font-size: 14px;
          .ed-button { color: @primary-400 !important; &:hover { color: @primary-500 !important; } }
        }
      }
    }
    .relationship-content {
      position: absolute; right: 0; top: 0; width: calc(100% - 280px); height: 100%; background: @dark-bg-secondary;
      .content { height: calc(100% - 56px); width: 100%; }
      .title { height: 56px; padding-left: 24px; line-height: 56px; font-weight: 600; font-size: 16px; color: @dark-text; border-bottom: 1px solid @dark-border; background: rgba(139, 92, 246, 0.03); }
    }
    .empty-right-panel {
      position: absolute; right: 0; top: 0; width: calc(100% - 280px); height: 100%; background: @dark-bg-secondary;
      display: flex; align-items: center; justify-content: center;
      .empty-hint { text-align: center; color: @dark-text-muted; font-size: 15px; p { margin: 0; } }
    }
    .info-table {
      position: absolute; right: 0; top: 0; width: calc(100% - 280px); height: 100%; background: @dark-bg-secondary; overflow: hidden;
      .table-name {
        height: 80px; padding: 16px 24px 0 24px; border-bottom: 1px solid @dark-border; background: rgba(139, 92, 246, 0.03);
        .name { font-weight: 600; font-size: 16px; line-height: 24px; color: @dark-text; }
        .ed-icon { position: relative; cursor: pointer; margin-top: 4px; margin-left: 8px; color: @dark-text-muted; transition: all 0.2s ease;
          &::after { content: ''; background-color: rgba(139, 92, 246, 0.15); position: absolute; border-radius: 6px; width: 24px; height: 24px; transform: translate(-50%, -50%); top: 50%; left: 50%; display: none; }
          &:hover { color: @primary-400; &::after { display: block; } }
        }
        .notes {
          font-weight: 400; font-size: 14px; line-height: 22px; color: @dark-text-muted; display: flex; align-items: center;
          .field-notes { display: inline-block; max-width: calc(100% - 75px); text-overflow: ellipsis; white-space: nowrap; overflow: hidden; color: @dark-text-secondary; }
        }
      }
      .table-content {
        padding: 16px 24px; height: calc(100% - 80px); box-sizing: border-box; overflow: hidden;
        .btn-select {
          height: 36px; padding: 4px; display: inline-flex; background: rgba(139, 92, 246, 0.08); align-items: center; border: 1px solid @dark-border; border-radius: 10px;
          .is-active { background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%) !important; color: #fff !important; border-radius: 8px; box-shadow: 0 2px 8px rgba(139, 92, 246, 0.3); }
          .ed-button:not(.is-active) { color: @dark-text-secondary; &:hover { color: @dark-text; background: rgba(139, 92, 246, 0.1); } }
          .ed-button.is-text { height: 28px; width: auto; padding: 0 12px; line-height: 28px; border-radius: 8px; transition: all 0.2s ease; }
          .ed-button + .ed-button { margin-left: 4px; }
        }
        .preview-or-schema {
          margin-top: 16px; height: calc(100% - 50px); overflow-x: hidden;
          &.overflow-preview { overflow-y: auto;
            &::-webkit-scrollbar { width: 6px; }
            &::-webkit-scrollbar-track { background: transparent; }
            &::-webkit-scrollbar-thumb { background: rgba(139, 92, 246, 0.3); border-radius: 3px; &:hover { background: rgba(139, 92, 246, 0.5); } }
          }
          .table-content_preview { max-height: calc(100% - 50px); overflow-y: auto; margin-bottom: 16px; border-radius: 12px; overflow: hidden; }
          :deep(.ed-table) {
            background: transparent !important;
            &::before { background-color: @dark-border !important; }
            .ed-table__header-wrapper th { background: rgba(139, 92, 246, 0.1) !important; border-bottom: 1px solid @dark-border !important; color: @dark-text !important; font-weight: 600; }
            .ed-table__body-wrapper { tr { background: transparent !important; &:hover td { background: rgba(139, 92, 246, 0.08) !important; } } td { background: transparent !important; border-bottom: 1px solid @dark-border !important; color: @dark-text-secondary !important; } }
            .ed-table__empty-block { background: transparent !important; .ed-table__empty-text { color: @dark-text-muted !important; } }
          }
          .pagination-container {
            display: flex; justify-content: flex-end; flex-wrap: wrap; overflow: hidden; padding: 12px 0;
            :deep(.ed-pagination) {
              flex-wrap: wrap; gap: 4px;
              .ed-pagination__total { color: @dark-text-secondary; }
              .ed-pagination__sizes .ed-input__wrapper { background: rgba(139, 92, 246, 0.08) !important; border: 1px solid @dark-border !important; .ed-input__inner { color: @dark-text-secondary !important; } }
              .ed-pager li { background: rgba(139, 92, 246, 0.08) !important; color: @dark-text-secondary !important; border: 1px solid @dark-border; &:hover { color: @primary-400 !important; } &.is-active { background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%) !important; color: #fff !important; border-color: transparent; } }
              .btn-prev, .btn-next { background: rgba(139, 92, 246, 0.08) !important; color: @dark-text-secondary !important; border: 1px solid @dark-border; &:hover { color: @primary-400 !important; } &:disabled { color: @dark-text-muted !important; } }
              .ed-pagination__jump { color: @dark-text-secondary; .ed-input__wrapper { background: rgba(139, 92, 246, 0.08) !important; border: 1px solid @dark-border !important; .ed-input__inner { color: @dark-text-secondary !important; } } }
            }
          }
          .hover-icon_edit:hover .ed-icon { display: block; }
          .field-comment {
            display: flex; align-items: center; min-height: 24px;
            .notes-in_table { max-width: 100%; display: -webkit-box; max-height: 66px; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; text-overflow: ellipsis; }
            .ed-icon { position: relative; cursor: pointer; margin-left: 8px; display: none; color: @dark-text-muted; transition: all 0.2s ease;
              &::after { content: ''; background-color: rgba(139, 92, 246, 0.15); position: absolute; border-radius: 6px; width: 24px; height: 24px; transform: translate(-50%, -50%); top: 50%; left: 50%; display: none; }
              &:hover { color: @primary-400; &::after { display: block; } }
            }
          }
          .preview-num { margin: 12px 0; font-weight: 400; font-size: 14px; line-height: 22px; color: @dark-text-muted; }
        }
      }
    }
  }
}

@media (max-width: 1024px) {
  .data-table .content {
    .side-list { width: 240px; }
    .relationship-content, .info-table, .empty-right-panel { width: calc(100% - 240px); }
  }
}
@media (max-width: 768px) {
  .data-table .content {
    flex-direction: column;
    .side-list { width: 100%; height: auto; max-height: 200px; border-right: none; border-bottom: 1px solid @dark-border; .list-content { height: 120px; } .table-relationship { display: none; } }
    .relationship-content, .info-table, .empty-right-panel { position: relative; width: 100%; height: calc(100% - 200px); }
  }
}

// ===== 数据源概览面板 =====
.ds-overview-panel {
  .overview-header {
    .type-icon { margin-right: 8px; font-size: 20px; }
    .ds-type-tag { display: inline-flex; align-items: center; padding: 3px 12px; font-size: 11px; font-weight: 600; color: @primary-400; background: rgba(139, 92, 246, 0.18); border: 1px solid rgba(139, 92, 246, 0.25); border-radius: 8px; }
    .connection-indicator {
      display: inline-flex; align-items: center; gap: 6px; padding: 3px 12px; font-size: 11px; font-weight: 600; border-radius: 8px; margin-left: 10px;
      .status-dot { width: 7px; height: 7px; border-radius: 50%; }
      &.status-connected { color: #4ade80; background: rgba(74, 222, 128, 0.12); border: 1px solid rgba(74, 222, 128, 0.25); .status-dot { background: #4ade80; box-shadow: 0 0 6px rgba(74, 222, 128, 0.5); } }
      &.status-disconnected { color: #f87171; background: rgba(248, 113, 113, 0.12); border: 1px solid rgba(248, 113, 113, 0.25); .status-dot { background: #f87171; } }
    }
  }
  .overview-section {
    .section-title { font-size: 14px; font-weight: 600; color: @dark-text; margin-bottom: 10px; }
    .section-item { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: rgba(139, 92, 246, 0.05); border: 1px solid transparent; border-radius: 8px; transition: all 0.2s ease;
      &.clickable { cursor: pointer; &:hover { background: rgba(139, 92, 246, 0.12); border-color: rgba(139, 92, 246, 0.2); } }
      .item-idx { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 50%; background: rgba(139, 92, 246, 0.15); font-size: 11px; font-weight: 700; color: @primary-400; flex-shrink: 0; }
      .item-name { font-size: 13px; color: @dark-text-secondary; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .item-meta { font-size: 11px; color: @dark-text-muted; flex-shrink: 0; }
      .item-arrow { font-size: 12px; color: @dark-text-muted; flex-shrink: 0; }
    }
  }
}

.structured-table-list { display: flex; flex-direction: column; gap: 8px; }
.structured-table-card {
  padding: 12px 14px; background: rgba(139, 92, 246, 0.04); border: 1px solid transparent; border-radius: 10px; cursor: pointer; transition: all 0.2s ease;
  &:hover { background: rgba(139, 92, 246, 0.1); border-color: rgba(139, 92, 246, 0.2); }
  .table-card-header { display: flex; align-items: center; gap: 10px;
    .table-card-name { font-size: 13px; font-weight: 600; color: @dark-text-secondary; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .table-card-comment { font-size: 11px; color: @dark-text-muted; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .table-card-field-count { font-size: 11px; color: @dark-text-muted; flex-shrink: 0; }
  }
  .table-card-fields { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; padding-left: 34px; }
}
.field-chip { display: inline-block; padding: 2px 8px; font-size: 11px; color: @dark-text-muted; background: rgba(139, 92, 246, 0.08); border: 1px solid rgba(139, 92, 246, 0.12); border-radius: 4px; &.more { color: @primary-400; background: rgba(139, 92, 246, 0.15); font-weight: 600; } }
.db-connection-panel {
  padding: 14px 16px; background: rgba(139, 92, 246, 0.06); border: 1px solid @dark-border; border-radius: 10px; display: flex; flex-direction: column; gap: 8px;
  .db-conn-row { display: flex; align-items: center; gap: 12px;
    .db-conn-label { font-size: 12px; color: @dark-text-muted; width: 56px; flex-shrink: 0; text-align: right; }
    .db-conn-value { font-size: 13px; color: @dark-text-secondary; font-weight: 500; font-family: 'SF Mono', 'Fira Code', monospace; }
  }
}
.pdf-error-state { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; padding: 60px 40px; text-align: center; .error-icon { font-size: 48px; margin-bottom: 16px; } .error-text { font-size: 14px; color: @dark-text-secondary; line-height: 1.6; margin: 0 0 20px 0; max-width: 400px; } }
.pdf-back-doc { color: rgba(167, 139, 250, 0.9) !important; border-bottom: 1px solid rgba(139, 92, 246, 0.15); margin-bottom: 4px; padding-bottom: 8px !important; font-size: 13px; &:hover { background: rgba(139, 92, 246, 0.12) !important; color: #a78bfa !important; } }

// ===== PDF 左侧边栏重新设计 =====
.pdf-sidebar {
  display: flex; flex-direction: column; gap: 0; overflow-y: auto; height: calc(100% - 48px) !important;
  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb { background: rgba(139, 92, 246, 0.25); border-radius: 2px; }
}
.pdf-profile-card {
  display: flex; align-items: center; gap: 10px; padding: 12px; margin-bottom: 8px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.12) 0%, rgba(139, 92, 246, 0.04) 100%);
  border: 1px solid rgba(139, 92, 246, 0.2); border-radius: 10px;
  .profile-icon { font-size: 28px; flex-shrink: 0; }
  .profile-info { flex: 1; min-width: 0;
    .profile-name { font-size: 13px; font-weight: 600; color: @dark-text; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .profile-meta { font-size: 11px; color: @dark-text-muted; margin-top: 2px; }
  }
}
.pdf-quick-stats {
  display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 10px;
  .qs-item {
    display: flex; flex-direction: column; align-items: center; padding: 8px 4px;
    background: rgba(139, 92, 246, 0.06); border: 1px solid rgba(139, 92, 246, 0.12); border-radius: 8px;
    .qs-num { font-size: 16px; font-weight: 700; color: @primary-400; line-height: 1.2; }
    .qs-label { font-size: 10px; color: @dark-text-muted; margin-top: 2px; white-space: nowrap; }
  }
}

// 文档视角导航（替代旧的流水线阶段导航）
.pdf-nav-stages {
  display: flex; flex-direction: column; gap: 2px; padding: 8px 0; margin-bottom: 8px;
  border-top: 1px solid rgba(139, 92, 246, 0.1); border-bottom: 1px solid rgba(139, 92, 246, 0.1);
  .nav-stage {
    display: flex; align-items: center; gap: 10px; padding: 10px 10px; border-radius: 8px; cursor: pointer; transition: all 0.2s ease;
    &:hover { background: rgba(139, 92, 246, 0.08); }
    &.active { background: rgba(139, 92, 246, 0.15); .nav-text { color: @primary-400; font-weight: 600; } .nav-icon { transform: scale(1.1); } }
    .nav-icon { font-size: 18px; flex-shrink: 0; transition: transform 0.2s ease; }
    .nav-info { display: flex; flex-direction: column; flex: 1; min-width: 0; }
    .nav-text { font-size: 13px; color: @dark-text-secondary; }
    .nav-sub { font-size: 10px; color: @dark-text-muted; margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .nav-readiness-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; box-shadow: 0 0 6px currentColor; }
  }
}

// 章节快速跳转
.pdf-section-quick-nav {
  flex: 1; overflow-y: auto; min-height: 0;
  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb { background: rgba(139, 92, 246, 0.25); border-radius: 2px; }
  .sqn-title { font-size: 11px; font-weight: 600; color: @dark-text-muted; padding: 6px 8px; text-transform: uppercase; letter-spacing: 0.5px; }
  .sqn-item {
    display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px; cursor: pointer; transition: all 0.15s ease;
    &:hover { background: rgba(139, 92, 246, 0.08); }
    &.active { background: rgba(139, 92, 246, 0.15); .sqn-name { color: @primary-400; } }
    .sqn-idx { font-size: 10px; font-weight: 700; color: @dark-text-muted; width: 18px; text-align: center; flex-shrink: 0; }
    .sqn-name { font-size: 12px; color: @dark-text-secondary; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; }
  }
}

// ===== PDF 右侧阶段视图 =====
.pdf-stage-view { padding-bottom: 24px; }

// RAG 处理流水线可视化（水平三阶段）
.pipeline-summary {
  display: flex; align-items: stretch; gap: 0; margin-bottom: 20px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.08) 0%, rgba(59, 130, 246, 0.04) 100%);
  border: 1px solid rgba(139, 92, 246, 0.2); border-radius: 12px; overflow: hidden;
  .ps-stage {
    flex: 1; padding: 16px 14px; display: flex; flex-direction: column; align-items: center; text-align: center;
    border-right: 1px solid rgba(139, 92, 246, 0.1);
    &:last-child { border-right: none; }
    .ps-icon { font-size: 24px; margin-bottom: 6px; }
    .ps-title { font-size: 12px; font-weight: 700; color: @dark-text; margin-bottom: 8px; }
    .ps-metrics { display: flex; flex-direction: column; gap: 3px;
      span { font-size: 11px; color: @dark-text-muted; }
    }
    .ps-readiness { margin-top: 6px; font-size: 11px; font-weight: 700; }
  }
  .ps-arrow { display: flex; align-items: center; padding: 0 4px; font-size: 16px; color: @dark-text-muted; flex-shrink: 0; }
}

// 解析概况卡片（每个阶段顶部）
.parse-overview-card {
  display: flex; flex-direction: column; margin-bottom: 20px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.1) 0%, rgba(59, 130, 246, 0.06) 100%);
  border: 1px solid rgba(139, 92, 246, 0.2); border-radius: 12px; overflow: hidden;
  .poc-left { padding: 18px 20px;
    .poc-title { font-size: 15px; font-weight: 700; color: @dark-text; margin-bottom: 6px; }
    .poc-desc { font-size: 12px; color: @dark-text-muted; line-height: 1.6; }
  }
  .poc-progress {
    padding: 0 20px 18px;
    .vpb-bar-wrap {
      height: 10px; background: rgba(139, 92, 246, 0.1); border-radius: 5px; overflow: hidden; margin-bottom: 8px;
      .vpb-bar { height: 100%; background: linear-gradient(90deg, @primary-500, #22c55e); border-radius: 5px; transition: width 0.5s ease; }
    }
    .vpb-text { font-size: 12px; color: @dark-text-secondary; text-align: center; }
  }
}

// 提取内容区块
.pdf-extract-block {
  margin-bottom: 20px;
  .peb-header {
    display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
    .peb-icon { font-size: 16px; }
    .peb-title { font-size: 14px; font-weight: 600; color: @dark-text; }
    .peb-count { font-size: 11px; color: @dark-text-muted; margin-left: auto; }
  }
  .peb-hint { font-size: 12px; color: @dark-text-muted; margin-bottom: 8px; }
}

// 章节树形结构
.section-tree {
  position: relative; padding-left: 4px;
  .st-node {
    display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 8px; cursor: pointer; transition: all 0.15s ease; position: relative;
    &:hover { background: rgba(139, 92, 246, 0.08); }
    &.expanded { background: rgba(139, 92, 246, 0.1); .st-name { color: @primary-400; } }
    .st-line { position: absolute; left: 11px; top: 0; bottom: 0; width: 1px; background: rgba(139, 92, 246, 0.12); }
    .st-dot { width: 8px; height: 8px; border-radius: 50%; background: rgba(139, 92, 246, 0.3); border: 2px solid rgba(139, 92, 246, 0.5); flex-shrink: 0; z-index: 1; }
    .st-name { font-size: 13px; color: @dark-text-secondary; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .st-badge { font-size: 10px; color: @dark-text-muted; background: rgba(139, 92, 246, 0.08); padding: 2px 6px; border-radius: 4px; flex-shrink: 0; }
    .st-arrow { font-size: 12px; color: @dark-text-muted; flex-shrink: 0; width: 14px; text-align: center; }
  }
  .st-content {
    padding: 6px 8px 12px 32px; display: flex; flex-direction: column; gap: 8px;
    .st-chunk {
      padding: 10px 12px; background: rgba(0, 0, 0, 0.15); border: 1px solid rgba(139, 92, 246, 0.08); border-radius: 8px;
      .stc-tags { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
      .stc-meta { font-size: 11px; color: @dark-text-muted; }
      .stc-text { font-size: 13px; line-height: 1.7; color: @dark-text-secondary; white-space: pre-wrap; word-break: break-word; }
    }
    .stc-empty { font-size: 12px; color: @dark-text-muted; padding: 8px 0; }
  }
}

// 表格提取列表
.table-extract-list {
  display: flex; flex-direction: column; gap: 6px;
  .tel-item {
    border: 1px solid rgba(139, 92, 246, 0.1); border-radius: 8px; overflow: hidden; transition: all 0.15s ease;
    &:hover { border-color: rgba(139, 92, 246, 0.25); }
    &.expanded { border-color: rgba(251, 191, 36, 0.3); background: rgba(251, 191, 36, 0.03); }
    .tel-head { display: flex; align-items: center; gap: 10px; padding: 10px 14px; cursor: pointer;
      .tel-badge { font-size: 12px; font-weight: 600; color: #fbbf24; }
      .tel-meta { font-size: 11px; color: @dark-text-muted; flex: 1; }
      .tel-arrow { font-size: 12px; color: @dark-text-muted; }
    }
    .tel-content { padding: 0 14px 14px;
      .tel-markdown { font-size: 12px; line-height: 1.6; color: @dark-text-secondary; white-space: pre-wrap; word-break: break-word; font-family: 'SF Mono', 'Fira Code', monospace; background: rgba(0, 0, 0, 0.2); padding: 12px; border-radius: 6px; margin: 0; max-height: 300px; overflow-y: auto;
        &::-webkit-scrollbar { width: 5px; }
        &::-webkit-scrollbar-thumb { background: rgba(139, 92, 246, 0.3); border-radius: 3px; }
      }
    }
  }
}

// 原始文本预览
.raw-text-preview {
  padding: 14px 16px; background: rgba(0, 0, 0, 0.2); border: 1px solid rgba(139, 92, 246, 0.1); border-radius: 8px;
  font-size: 12px; line-height: 1.7; color: @dark-text-secondary; white-space: pre-wrap; word-break: break-word;
  max-height: 300px; overflow-y: auto; font-family: 'SF Mono', 'Fira Code', monospace;
  &::-webkit-scrollbar { width: 5px; }
  &::-webkit-scrollbar-thumb { background: rgba(139, 92, 246, 0.3); border-radius: 3px; }
}

// 处理方法卡片行
.process-method-row {
  display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 18px;
  .pm-card {
    padding: 12px 14px; background: rgba(139, 92, 246, 0.04); border: 1px solid rgba(139, 92, 246, 0.1); border-radius: 8px; transition: all 0.2s ease;
    &:hover { background: rgba(139, 92, 246, 0.08); border-color: rgba(139, 92, 246, 0.2); }
    &.pm-wide { grid-column: span 1; }
    .pm-head { font-size: 12px; font-weight: 700; color: @dark-text; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; .pm-icon { font-size: 16px; } }
    .pm-body { font-size: 11px; color: @dark-text-muted; line-height: 1.5; &.pm-hl { color: @primary-400; font-weight: 600; } }
  }
}

// 分块类型分布条形图
.chunk-dist-bars {
  display: flex; flex-direction: column; gap: 8px;
  .cdb-row {
    display: flex; align-items: center; gap: 8px;
    .cdb-icon { font-size: 14px; flex-shrink: 0; width: 20px; text-align: center; }
    .cdb-label { font-size: 12px; color: @dark-text-secondary; width: 100px; flex-shrink: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .cdb-bar-wrap { flex: 1; height: 8px; background: rgba(139, 92, 246, 0.08); border-radius: 4px; overflow: hidden;
      .cdb-bar { height: 100%; border-radius: 4px; transition: width 0.5s ease;
        &.tag-text { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
        &.tag-table { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
        &.tag-overlap { background: linear-gradient(90deg, #ef4444, #f87171); opacity: 0.6; }
        &.tag-window { background: linear-gradient(90deg, #22c55e, #4ade80); }
      }
    }
    .cdb-count { font-size: 12px; font-weight: 700; color: @primary-400; width: 32px; text-align: right; flex-shrink: 0; }
  }
}

// 分块卡片列表（阶段二）
.chunk-card-list {
  display: flex; flex-direction: column; gap: 6px;
  .cc-item {
    padding: 10px 14px; background: rgba(139, 92, 246, 0.03); border: 1px solid rgba(139, 92, 246, 0.1); border-radius: 8px; cursor: pointer; transition: all 0.15s ease;
    &:hover { border-color: rgba(139, 92, 246, 0.25); background: rgba(139, 92, 246, 0.06); }
    &.overlap { opacity: 0.5; border-color: rgba(245, 158, 11, 0.2); }
    .cc-head { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; flex-wrap: wrap;
      .cc-idx { font-size: 11px; font-weight: 700; color: @primary-400; background: rgba(139, 92, 246, 0.12); padding: 1px 6px; border-radius: 4px; }
      .cc-meta { font-size: 11px; color: @dark-text-muted; }
      .cc-len { font-size: 11px; color: @dark-text-muted; margin-left: auto; }
      .cc-vec { font-size: 10px; &.vec-y { color: #22c55e; } &.vec-n { color: #f59e0b; } }
    }
    .cc-preview { font-size: 12px; line-height: 1.5; color: @dark-text-muted; max-height: 40px; overflow: hidden; position: relative;
      &::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 20px; background: linear-gradient(transparent, rgba(15, 10, 26, 0.95)); }
    }
    .cc-full { font-size: 12px; line-height: 1.7; color: @dark-text-secondary; white-space: pre-wrap; word-break: break-word; max-height: 300px; overflow-y: auto; padding: 8px; background: rgba(0, 0, 0, 0.15); border-radius: 6px; margin-top: 6px;
      &::-webkit-scrollbar { width: 5px; }
      &::-webkit-scrollbar-thumb { background: rgba(139, 92, 246, 0.3); border-radius: 3px; }
    }
  }
}

// 跳过原因列表
.skip-reason-list {
  display: flex; flex-direction: column; gap: 6px;
  .sr-item { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: rgba(139, 92, 246, 0.04); border: 1px solid rgba(139, 92, 246, 0.08); border-radius: 8px;
    .sr-icon { font-size: 16px; flex-shrink: 0; }
    .sr-text { font-size: 13px; color: @dark-text; font-weight: 500; flex: 1; }
    .sr-num { font-size: 13px; font-weight: 700; color: #f59e0b; }
  }
}

// 向量化状态网格
.vec-status-grid {
  display: flex; flex-wrap: wrap; gap: 4px; max-height: 400px; overflow-y: auto;
  &::-webkit-scrollbar { width: 5px; }
  &::-webkit-scrollbar-thumb { background: rgba(139, 92, 246, 0.3); border-radius: 3px; }
  .vsg-item {
    display: flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 6px; border: 1px solid transparent; font-size: 11px;
    &.vsg-yes { background: rgba(34, 197, 94, 0.04); border-color: rgba(34, 197, 94, 0.12); }
    &.vsg-no { background: rgba(245, 158, 11, 0.04); border-color: rgba(245, 158, 11, 0.12); opacity: 0.6; }
    .vsg-idx { font-weight: 700; color: @primary-400; }
    .vsg-len { color: @dark-text-muted; }
    .vsg-badge { margin-left: auto; font-size: 10px; }
  }
}

// 通用标签样式
.chunk-type-tag {
  font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 600; white-space: nowrap;
  &.tag-text { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
  &.tag-table { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
  &.tag-overlap { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
  &.tag-window { background: rgba(34, 197, 94, 0.15); color: #22c55e; }
  &.sm { padding: 1px 4px; font-size: 10px; }
}
.st-arrow { font-size: 12px; color: @dark-text-muted; flex-shrink: 0; width: 14px; text-align: center; }
</style>

<style lang="less">
@dark-bg-secondary: #1a1225;
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;

.notes-dialog {
  .ed-dialog {
    background: @dark-bg-secondary !important; border: 1px solid @dark-border !important; border-radius: 16px !important;
    box-shadow: 0 12px 48px rgba(0, 0, 0, 0.5);
  }
  .ed-dialog__header { background: transparent !important; border-bottom: 1px solid @dark-border; padding: 16px 20px;
    .ed-dialog__title { color: @dark-text !important; font-weight: 600; }
  }
  .ed-dialog__body { padding: 20px; }
  .ed-textarea__inner {
    background: rgba(139, 92, 246, 0.08) !important; border: 1px solid @dark-border !important; color: @dark-text !important; border-radius: 10px;
    &::placeholder { color: @dark-text-muted !important; }
    &:focus { border-color: @primary-500 !important; box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15) !important; }
  }
}
</style>
