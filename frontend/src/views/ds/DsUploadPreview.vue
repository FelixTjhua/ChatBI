<script setup lang="ts">
/**
 * 数据源上传结果预览组件（统一4种数据源）
 *
 * 展示数据源上传/连接后的完整处理流水线结果：
 * - PDF:  文件信息 → 文档解析 → 表格识别 → 文档分块 → 向量入库 → 就绪
 * - Excel: 文件信息 → 数据解析 → 工作表结构 → 数据清洗 → 数据入库 → 就绪
 * - CSV:  文件信息 → 编码检测 → 数据结构 → 数据清洗 → 数据入库 → 就绪
 * - Database: 连接信息 → 表结构 → 字段统计 → 就绪
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Check, Document, Grid, Coin, Connection, ChatDotRound, DataBoard } from '@element-plus/icons-vue'

const { t } = useI18n()

const props = defineProps<{
  /** 数据源类型: pdf / excel / csv / database */
  dsType: string
  /** PDF 上传结果 */
  pdfData?: {
    stats: any
    preview: any
  } | null
  /** Excel/CSV 上传结果 */
  excelData?: any | null
  /** Database 连接结果（表列表） */
  dbData?: {
    tables: Array<{ tableName: string; tableComment?: string }>
    host?: string
    port?: number
    database?: string
    dbType?: string
  } | null
  /** 原始文件名 */
  filename?: string
}>()

const activeSection = ref(0)
const expandedTable = ref<number | null>(null)
const expandedSheet = ref<number | null>(null)

function formatSize(bytes: number): string {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

// ── 根据数据源类型生成流水线阶段 ──
const stages = computed(() => {
  if (props.dsType === 'pdf') {
    return [
      { label: t('ds_upload.file_info') }, { label: t('ds_upload.parse_preview') }, { label: t('ds_upload.table_recognition') },
      { label: t('ds_upload.doc_chunking') }, { label: t('ds_upload.vector_store') }, { label: t('ds_upload.ready') },
    ]
  }
  if (props.dsType === 'csv') {
    return [
      { label: t('ds_upload.file_info') }, { label: t('ds_upload.encoding_delimiter') }, { label: t('ds_upload.data_structure') },
      { label: t('ds_upload.data_cleaning') }, { label: t('ds_upload.data_import') }, { label: t('ds_upload.ready') },
    ]
  }
  if (props.dsType === 'excel') {
    return [
      { label: t('ds_upload.file_info') }, { label: t('ds_upload.sheet_parse') }, { label: t('ds_upload.data_structure') },
      { label: t('ds_upload.data_cleaning') }, { label: t('ds_upload.data_import') }, { label: t('ds_upload.ready') },
    ]
  }
  // database
  return [
    { label: t('ds_upload.connection_info') }, { label: t('ds_upload.table_structure') }, { label: t('ds_upload.field_stats') }, { label: t('ds_upload.ready') },
  ]
})

// ── PDF helpers ──
const pdfStats = computed(() => props.pdfData?.stats || {})
const pdfPreview = computed(() => props.pdfData?.preview || null)

function chunkTypeLabel(type: string) {
  const map: Record<string, string> = {
    section: '📄 ' + t('ds_upload.text_paragraph'), section_split: '📄 ' + t('ds_upload.text_split'), table: '📊 ' + t('ds_pdf.chunk_table'),
    table_overlap: '🔄 ' + t('ds_upload.table_overlap'), sliding_window: '📄 ' + t('ds_upload.sliding_window'),
  }
  return map[type] || '📄 ' + type
}
function chunkTypeClass(type: string) {
  if (type === 'table') return 'tag-table'
  if (type === 'table_overlap') return 'tag-overlap'
  return 'tag-text'
}
function toggleTable(idx: number) { expandedTable.value = expandedTable.value === idx ? null : idx }
function toggleSheet(idx: number) { expandedSheet.value = expandedSheet.value === idx ? null : idx }

function renderMarkdownTable(md: string): string {
  const lines = md.split('\n').filter(l => l.trim())
  if (lines.length < 2) return `<pre>${md}</pre>`
  let html = '<table>'
  lines.forEach((line, i) => {
    if (i === 1 && line.includes('---')) return
    const cells = line.split('|').filter(c => c.trim() !== '')
    const tag = i === 0 ? 'th' : 'td'
    if (line.startsWith('_')) {
      html += `<tr><td colspan="${cells.length || 3}" class="table-more">${line.replace(/_/g, '')}</td></tr>`
    } else {
      html += '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>'
    }
  })
  html += '</table>'
  return html
}

// ── Excel/CSV helpers ──
const excelPreview = computed(() => props.excelData || null)

// ── 就绪摘要 ──
const readySummary = computed(() => {
  if (props.dsType === 'pdf') {
    const s = pdfStats.value
    const parts = [`${s.total_pages || 0} ${t('ds_pdf.pages_unit')}`, `${s.total_sections || 0} ${t('ds_upload.paragraphs')}`, `${s.total_chunks || 0} ${t('ds_upload.chunks')}`, `${s.vectorized_count || 0} ${t('ds_upload.vectors')}`]
    if (s.extracted_tables > 0) parts.push(`${s.extracted_tables} ${t('ds_upload.recognized_tables_text')}`)
    return parts
  }
  if (props.dsType === 'excel' || props.dsType === 'csv') {
    const e = excelPreview.value
    if (!e) return []
    const parts = [`${e.sheet_count || 1} sheets`, `${e.total_rows || 0} rows`, `${e.total_columns || 0} ${t('ds_pdf.fields_unit')}`, `${e.tables_created || 0} ${t('ds_upload.tables_imported')}`]
    return parts
  }
  // database
  const d = props.dbData
  if (!d) return []
  return [`${d.tables?.length || 0} ${t('ds_pdf.tables_unit')}`, `${d.dbType || 'PostgreSQL'}`]
})
</script>

<template>
  <div class="ds-upload-preview">
    <!-- 流水线阶段导航 -->
    <div class="pipeline-nav">
      <div v-for="(stage, idx) in stages" :key="idx" class="pipeline-step"
           :class="{ active: activeSection === idx, completed: true }" @click="activeSection = idx">
        <div class="step-icon"><el-icon :size="14"><Check /></el-icon></div>
        <span class="step-label">{{ stage.label }}</span>
        <span v-if="idx < stages.length - 1" class="step-arrow">→</span>
      </div>
    </div>

    <!-- ╔══════════════════════════════════════════╗ -->
    <!-- ║              PDF 数据源                   ║ -->
    <!-- ╚══════════════════════════════════════════╝ -->
    <template v-if="dsType === 'pdf'">
      <!-- 阶段1：文件信息 -->
      <div v-show="activeSection === 0" class="section-panel">
        <div class="section-title">📋 {{ t('ds_upload.file_basic_info') }}</div>
        <div class="info-grid">
          <div class="info-item"><span class="info-label">{{ t('ds_pdf.filename') }}</span><span class="info-value">{{ filename }}</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_pdf.file_size') }}</span><span class="info-value">{{ formatSize(pdfStats.file_size) }}</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_pdf.total_pages') }}</span><span class="info-value hl">{{ pdfStats.total_pages }} {{ t('ds_pdf.pages_unit') }}</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_pdf.processing_time') }}</span><span class="info-value">{{ (pdfStats.processing_time || 0).toFixed(2) }}s</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_pdf.process_status') }}</span><span class="info-value ok">✅ {{ t('ds_pdf.parse_complete') }}</span></div>
          <div v-if="pdfStats.scanned_pages > 0" class="info-item"><span class="info-label">{{ t('ds_upload.scanned_pages') }}</span><span class="info-value warn">⚠️ {{ pdfStats.scanned_pages }} {{ t('ds_upload.needs_ocr') }}</span></div>
        </div>
      </div>
      <!-- 阶段2：解析预览 -->
      <div v-show="activeSection === 1" class="section-panel">
        <div class="section-title">📖 {{ t('ds_upload.parse_result_preview') }}</div>
        <div class="sub-title">{{ t('ds_upload.parse_result_desc') }}</div>
        <div class="text-preview-box" v-if="pdfPreview?.raw_text_preview">
          <pre class="raw-text">{{ pdfPreview.raw_text_preview }}</pre>
        </div>
        <div v-if="pdfPreview?.sections?.length" class="sections-list">
          <div class="sub-title" style="margin-top:16px">{{ t('ds_upload.sections_found', { count: pdfStats.total_sections }) }}</div>
          <div v-for="(sec, idx) in pdfPreview.sections.slice(0, 15)" :key="idx" class="section-item">
            <span class="sec-badge">{{ t('ds_pdf.page_n', { n: sec.page }) }}</span>
            <span class="sec-title" v-if="sec.title">{{ sec.title }}</span>
            <span class="sec-content">{{ sec.content_preview }}</span>
          </div>
          <div v-if="pdfPreview.sections.length > 15" class="more-hint">...{{ t('ds_upload.total_paragraphs', { count: pdfPreview.sections.length }) }}</div>
        </div>
      </div>
      <!-- 阶段3：表格识别 -->
      <div v-show="activeSection === 2" class="section-panel">
        <div class="section-title">📊 {{ t('ds_upload.table_recognition_result') }}</div>
        <div v-if="pdfPreview?.tables?.length" class="table-results">
          <div class="sub-title">{{ t('ds_upload.tables_found', { total: pdfStats.total_tables, imported: pdfStats.extracted_tables }) }}</div>
          <div v-for="tbl in pdfPreview.tables" :key="tbl.index" class="table-card">
            <div class="table-card-header" @click="toggleTable(tbl.index)">
              <span class="table-card-title">📊 {{ t('ds_upload.table_n', { n: tbl.index }) }}（{{ t('ds_pdf.page_n', { n: tbl.page }) }}）</span>
              <span class="table-card-meta">{{ tbl.columns }} cols × {{ tbl.rows }} rows</span>
              <span class="expand-icon">{{ expandedTable === tbl.index ? '▼' : '▶' }}</span>
            </div>
            <div v-if="expandedTable === tbl.index" class="table-card-body">
              <div class="md-table" v-dompurify-html="renderMarkdownTable(tbl.markdown)"></div>
            </div>
          </div>
        </div>
        <div v-else class="empty-hint">{{ t('ds_upload.no_tables_found') }}</div>
      </div>
      <!-- 阶段4：文档分块 -->
      <div v-show="activeSection === 3" class="section-panel">
        <div class="section-title">🧩 {{ t('ds_upload.chunking_result') }}</div>
        <div class="stat-row">
          <div class="stat-card"><span class="stat-num">{{ pdfStats.total_chunks }}</span><span class="stat-lbl">{{ t('ds_pdf.text_chunks') }}</span></div>
          <div class="stat-card"><span class="stat-num">{{ (pdfPreview?.chunks || []).filter((c: any) => c.chunk_type !== 'table').length }}</span><span class="stat-lbl">{{ t('ds_pdf.text_blocks') }}</span></div>
          <div class="stat-card"><span class="stat-num">{{ (pdfPreview?.chunks || []).filter((c: any) => c.chunk_type === 'table').length }}</span><span class="stat-lbl">{{ t('ds_pdf.table_blocks') }}</span></div>
          <div class="stat-card" v-if="pdfStats.raw_text_length"><span class="stat-num">{{ pdfStats.raw_text_length }}</span><span class="stat-lbl">{{ t('ds_upload.raw_chars') }}</span></div>
          <div class="stat-card" v-if="pdfStats.chunks_total_chars"><span class="stat-num">{{ pdfStats.chunks_total_chars }}</span><span class="stat-lbl">{{ t('ds_upload.chunk_chars') }}</span></div>
        </div>
        <div class="sub-title">{{ t('ds_upload.chunk_preview_desc') }}</div>
        <div v-if="pdfPreview?.chunks?.length" class="chunks-list">
          <div v-for="chunk in pdfPreview.chunks" :key="chunk.index" class="chunk-card">
            <div class="chunk-hdr">
              <span class="chunk-idx">#{{ chunk.index }}</span>
              <span class="chunk-tag" :class="chunkTypeClass(chunk.chunk_type)">{{ chunkTypeLabel(chunk.chunk_type) }}</span>
              <span v-if="chunk.page_number" class="chunk-meta">{{ t('ds_pdf.page_n', { n: chunk.page_number }) }}</span>
              <span v-if="chunk.section_title" class="chunk-meta">📑 {{ chunk.section_title }}</span>
              <span class="chunk-meta chunk-len">{{ t('ds_pdf.n_chars', { n: chunk.text_length }) }}</span>
            </div>
            <div class="chunk-txt">{{ chunk.text_preview }}</div>
          </div>
        </div>
      </div>
      <!-- 阶段5：向量入库 -->
      <div v-show="activeSection === 4" class="section-panel">
        <div class="section-title">🔗 {{ t('ds_upload.vector_status_title') }}</div>
        <div class="status-list">
          <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.vectorization_done') }}</span><span class="sd">{{ t('ds_upload.vectorization_desc', { done: pdfStats.vectorized_count, total: pdfStats.total_chunks }) }}</span></div>
          <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.stored_in_vector_db') }}</span><span class="sd">pgvector (HNSW) · {{ t('ds_upload.cosine_similarity') }}</span></div>
          <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.kb_build_done') }}</span><span class="sd">{{ t('ds_upload.embedding_model_desc') }}</span></div>
          <div v-if="pdfStats.extracted_tables > 0" class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.tables_stored') }}</span><span class="sd">{{ t('ds_upload.tables_stored_desc', { count: pdfStats.extracted_tables }) }}</span></div>
          <div v-if="pdfStats.total_chunks - pdfStats.vectorized_count > 0" class="status-row info-row"><span class="si">ℹ️</span><span class="sd">{{ t('ds_upload.chunks_filtered', { count: pdfStats.total_chunks - pdfStats.vectorized_count }) }}</span></div>
        </div>
      </div>
    </template>

    <!-- ╔══════════════════════════════════════════╗ -->
    <!-- ║          Excel / CSV 数据源               ║ -->
    <!-- ╚══════════════════════════════════════════╝ -->
    <template v-else-if="dsType === 'excel' || dsType === 'csv'">
      <!-- 阶段1：文件信息 -->
      <div v-show="activeSection === 0" class="section-panel">
        <div class="section-title">📋 {{ t('ds_upload.file_basic_info') }}</div>
        <div class="info-grid">
          <div class="info-item"><span class="info-label">{{ t('ds_pdf.filename') }}</span><span class="info-value">{{ filename }}</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_pdf.file_size') }}</span><span class="info-value">{{ formatSize(excelPreview?.file_size) }}</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_pdf.file_type') }}</span><span class="info-value hl">{{ dsType === 'csv' ? t('ds_upload.csv_type_desc') : t('ds_upload.excel_type_desc') }}</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_pdf.sheet_count') }}</span><span class="info-value">{{ excelPreview?.sheet_count || 1 }}</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_pdf.total_rows') }}</span><span class="info-value hl">{{ excelPreview?.total_rows || 0 }} {{ t('ds_pdf.rows_unit') }}</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_pdf.process_status') }}</span><span class="info-value ok">✅ {{ t('ds_pdf.import_complete') }}</span></div>
        </div>
      </div>
      <!-- 阶段2：编码/工作表解析 -->
      <div v-show="activeSection === 1" class="section-panel">
        <div class="section-title">{{ dsType === 'csv' ? '🔍 ' + t('ds_upload.csv_encoding_title') : '📑 ' + t('ds_upload.sheet_parse_result') }}</div>
        <template v-if="dsType === 'csv'">
          <div class="sub-title">{{ t('ds_upload.csv_encoding_desc') }}</div>
          <div class="status-list">
            <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.csv_encoding_parse') }}</span><span class="sd">{{ t('ds_upload.csv_encoding_parse_desc') }}</span></div>
            <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.csv_delimiter_detect') }}</span><span class="sd">{{ t('ds_upload.csv_delimiter_detect_desc') }}</span></div>
            <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.csv_data_read') }}</span><span class="sd">{{ t('ds_upload.csv_data_read_desc') }}</span></div>
          </div>
        </template>
        <template v-else>
          <div class="sub-title">{{ t('ds_upload.sheets_parsed', { count: excelPreview?.sheet_count || 0 }) }}</div>
          <div v-for="(sheet, idx) in (excelPreview?.sheets || [])" :key="idx" class="table-card">
            <div class="table-card-header" @click="toggleSheet(idx)">
              <span class="table-card-title">📑 {{ sheet.name }}</span>
              <span class="table-card-meta">{{ sheet.columns?.length || 0 }} {{ t('ds_upload.cols_unit') }} × {{ sheet.rows_count || 0 }} {{ t('ds_pdf.rows_unit') }}</span>
              <span class="expand-icon">{{ expandedSheet === idx ? '▼' : '▶' }}</span>
            </div>
            <div v-if="expandedSheet === idx" class="table-card-body">
              <div class="field-tags">
                <span v-for="col in sheet.columns" :key="col" class="field-tag"
                      :class="sheet.numeric_columns?.includes(col) ? 'tag-num' : 'tag-str'">
                  {{ col }}
                </span>
              </div>
            </div>
          </div>
        </template>
      </div>
      <!-- 阶段3：数据结构 -->
      <div v-show="activeSection === 2" class="section-panel">
        <div class="section-title">📊 {{ t('ds_upload.data_structure_preview') }}</div>
        <div v-for="(sheet, idx) in (excelPreview?.sheets || [])" :key="idx" class="sheet-preview">
          <div class="sheet-name">📑 {{ sheet.name }} <span class="sheet-meta">{{ sheet.columns?.length }} {{ t('ds_upload.cols_unit') }} · {{ sheet.rows_count }} {{ t('ds_pdf.rows_unit') }}</span></div>
          <div class="field-summary">
            <span v-if="sheet.numeric_columns?.length" class="field-group">
              📐 {{ t('ds_upload.numeric_fields') }}({{ sheet.numeric_columns.length }}): {{ sheet.numeric_columns.slice(0, 5).join(', ') }}{{ sheet.numeric_columns.length > 5 ? '...' : '' }}
            </span>
            <span v-if="sheet.text_columns?.length" class="field-group">
              📝 {{ t('ds_upload.text_fields') }}({{ sheet.text_columns.length }}): {{ sheet.text_columns.slice(0, 5).join(', ') }}{{ sheet.text_columns.length > 5 ? '...' : '' }}
            </span>
          </div>
          <!-- 数据样本 -->
          <div v-if="sheet.sample_rows?.length" class="sample-table-wrap">
            <table class="sample-table">
              <thead><tr><th v-for="col in sheet.columns?.slice(0, 8)" :key="col">{{ col }}</th></tr></thead>
              <tbody>
                <tr v-for="(row, ri) in sheet.sample_rows.slice(0, 5)" :key="ri">
                  <td v-for="col in sheet.columns?.slice(0, 8)" :key="col">{{ row[col] || '' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="(sheet.columns?.length || 0) > 8" class="more-hint">...{{ t('ds_upload.total_columns', { count: sheet.columns?.length }) }}</div>
          </div>
        </div>
      </div>
      <!-- 阶段4：数据清洗 -->
      <div v-show="activeSection === 3" class="section-panel">
        <div class="section-title">🧹 {{ t('ds_upload.data_cleaning') }}</div>
        <div class="sub-title">{{ t('ds_upload.cleaning_auto_desc') }}</div>
        <!-- 有真实清洗统计时展示实际数据 -->
        <template v-if="excelPreview?.cleaning_stats">
          <div class="stat-row">
            <div class="stat-card"><span class="stat-num">{{ excelPreview.cleaning_stats.original_rows }}</span><span class="stat-lbl">{{ t('ds_upload.original_rows') }}</span></div>
            <div class="stat-card"><span class="stat-num">{{ excelPreview.cleaning_stats.dedup_removed }}</span><span class="stat-lbl">{{ t('ds_upload.dedup_removed') }}</span></div>
            <div class="stat-card"><span class="stat-num">{{ excelPreview.cleaning_stats.null_rows_removed }}</span><span class="stat-lbl">{{ t('ds_upload.null_rows_removed') }}</span></div>
            <div class="stat-card"><span class="stat-num">{{ excelPreview.cleaning_stats.cleaned_rows }}</span><span class="stat-lbl">{{ t('ds_upload.cleaned_rows') }}</span></div>
          </div>
        </template>
        <div class="status-list">
          <div class="status-row">
            <span class="si">✅</span><span class="st">{{ t('ds_upload.dedup_title') }}</span>
            <span class="sd">{{ excelPreview?.cleaning_stats ? t('ds_upload.dedup_desc_detail', { count: excelPreview.cleaning_stats.dedup_removed }) : t('ds_upload.dedup_desc') }}</span>
          </div>
          <div class="status-row">
            <span class="si">✅</span><span class="st">{{ t('ds_upload.null_handling_title') }}</span>
            <span class="sd">{{ excelPreview?.cleaning_stats ? t('ds_upload.null_handling_desc_detail', { count: excelPreview.cleaning_stats.null_rows_removed }) : t('ds_upload.null_handling_desc') }}</span>
          </div>
          <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.format_unify_title') }}</span><span class="sd">{{ t('ds_upload.format_unify_desc') }}</span></div>
          <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.outlier_filter_title') }}</span><span class="sd">{{ t('ds_upload.outlier_filter_desc') }}</span></div>
        </div>
      </div>
      <!-- 阶段5：数据入库 -->
      <div v-show="activeSection === 4" class="section-panel">
        <div class="section-title">💾 {{ t('ds_upload.data_import_status') }}</div>
        <div class="status-list">
          <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.import_done') }}</span><span class="sd">{{ t('ds_upload.import_done_desc', { count: excelPreview?.tables_created || 0 }) }}</span></div>
          <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.copy_bulk_import') }}</span><span class="sd">{{ t('ds_upload.copy_bulk_import_desc') }}</span></div>
          <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.sql_query_support') }}</span><span class="sd">{{ t('ds_upload.sql_query_support_desc') }}</span></div>
          <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.rag_kb') }}</span><span class="sd">{{ t('ds_upload.rag_kb_desc') }}</span></div>
        </div>
      </div>
    </template>

    <!-- ╔══════════════════════════════════════════╗ -->
    <!-- ║          Database 数据源                  ║ -->
    <!-- ╚══════════════════════════════════════════╝ -->
    <template v-else-if="dsType === 'database'">
      <!-- 阶段1：连接信息 -->
      <div v-show="activeSection === 0" class="section-panel">
        <div class="section-title">🔌 {{ t('ds_upload.db_connection_info') }}</div>
        <div class="info-grid">
          <div class="info-item"><span class="info-label">{{ t('ds_upload.db_type') }}</span><span class="info-value hl">{{ dbData?.dbType || 'PostgreSQL' }}</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_upload.db_host') }}</span><span class="info-value">{{ dbData?.host || '-' }}</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_upload.db_port') }}</span><span class="info-value">{{ dbData?.port || '-' }}</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_upload.db_name') }}</span><span class="info-value">{{ dbData?.database || '-' }}</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_upload.db_table_count') }}</span><span class="info-value hl">{{ dbData?.tables?.length || 0 }} {{ t('ds_pdf.tables_unit') }}</span></div>
          <div class="info-item"><span class="info-label">{{ t('ds_upload.db_conn_status') }}</span><span class="info-value ok">✅ {{ t('ds.connection_success') }}</span></div>
        </div>
      </div>
      <!-- 阶段2：表结构 -->
      <div v-show="activeSection === 1" class="section-panel">
        <div class="section-title">📊 {{ t('ds_upload.db_table_structure') }}</div>
        <div class="sub-title">{{ t('ds_upload.db_tables_found', { count: dbData?.tables?.length || 0 }) }}</div>
        <div class="db-table-list">
          <div v-for="(tbl, idx) in (dbData?.tables || [])" :key="idx" class="db-table-item">
            <span class="db-tbl-idx">{{ idx + 1 }}</span>
            <span class="db-tbl-name">{{ tbl.tableName }}</span>
            <span v-if="tbl.tableComment" class="db-tbl-comment">{{ tbl.tableComment }}</span>
          </div>
        </div>
      </div>
      <!-- 阶段3：字段统计 -->
      <div v-show="activeSection === 2" class="section-panel">
        <div class="section-title">📐 {{ t('ds_upload.field_stats') }}</div>
        <div class="status-list">
          <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.db_schema_read') }}</span><span class="sd">{{ t('ds_upload.db_schema_read_desc', { count: dbData?.tables?.length || 0 }) }}</span></div>
          <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.sql_query_support') }}</span><span class="sd">{{ t('ds_upload.db_sql_query_desc') }}</span></div>
          <div class="status-row"><span class="si">✅</span><span class="st">{{ t('ds_upload.db_rag_enhance') }}</span><span class="sd">{{ t('ds_upload.db_rag_enhance_desc') }}</span></div>
        </div>
      </div>
    </template>

    <!-- ╔══════════════════════════════════════════╗ -->
    <!-- ║          通用就绪阶段                     ║ -->
    <!-- ╚══════════════════════════════════════════╝ -->
    <div v-show="activeSection === stages.length - 1" class="section-panel ready-panel">
      <div class="ready-icon">🎉</div>
      <div class="ready-title">{{ dsType === 'database' ? t('ds_upload.ready_db') : t('ds_upload.ready_doc') }}</div>
      <div class="ready-summary">
        <template v-for="(item, idx) in readySummary" :key="idx">
          <span>{{ item }}</span>
          <span v-if="idx < readySummary.length - 1" class="dot">·</span>
        </template>
      </div>
      <div class="ready-hint">{{ t('ds_upload.ready_hint') }}</div>
    </div>
  </div>
</template>

<style scoped lang="less">
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@dark-bg-card: rgba(26, 18, 37, 0.85);
@dark-border: rgba(139, 92, 246, 0.15);
@dark-text: rgba(255, 255, 255, 0.92);
@dark-text-sec: rgba(196, 181, 253, 0.7);
@dark-text-muted: rgba(196, 181, 253, 0.45);

.ds-upload-preview { padding: 0 4px; color: @dark-text; }

/* ── 流水线导航 ── */
.pipeline-nav {
  display: flex; align-items: center; gap: 2px;
  padding: 10px 12px; background: rgba(139, 92, 246, 0.06);
  border: 1px solid @dark-border; border-radius: 10px; margin-bottom: 16px; flex-wrap: wrap;
}
.pipeline-step {
  display: flex; align-items: center; gap: 5px; cursor: pointer;
  padding: 4px 8px; border-radius: 6px; font-size: 12px; color: @dark-text-muted; transition: all 0.2s;
  &.active { background: rgba(139, 92, 246, 0.15); color: @primary-400; .step-icon { background: @primary-500; color: #fff; } }
  &.completed .step-icon { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
  &:hover { background: rgba(139, 92, 246, 0.08); }
}
.step-icon { width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; }
.step-label { white-space: nowrap; }
.step-arrow { color: @dark-text-muted; font-size: 10px; margin: 0 2px; }

/* ── 通用面板 ── */
.section-panel { background: @dark-bg-card; border: 1px solid @dark-border; border-radius: 10px; padding: 18px 20px; min-height: 180px; }
.section-title { font-size: 15px; font-weight: 600; color: @dark-text; margin-bottom: 12px; }
.sub-title { font-size: 12px; color: @dark-text-sec; margin-bottom: 10px; }
.hl { color: @primary-400; font-weight: 600; }
.more-hint { text-align: center; color: @dark-text-muted; font-size: 12px; padding: 8px 0; }
.empty-hint { text-align: center; color: @dark-text-muted; padding: 40px 0; font-size: 13px; }

/* ── 信息网格 ── */
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.info-item { display: flex; flex-direction: column; gap: 4px; padding: 10px 14px; background: rgba(139, 92, 246, 0.04); border: 1px solid rgba(139, 92, 246, 0.08); border-radius: 8px; }
.info-label { font-size: 11px; color: @dark-text-muted; }
.info-value { font-size: 14px; color: @dark-text; &.ok { color: #22c55e; } &.warn { color: #f59e0b; } }

/* ── 文本预览 ── */
.text-preview-box { background: rgba(0,0,0,0.3); border: 1px solid rgba(139,92,246,0.1); border-radius: 8px; padding: 14px; max-height: 200px; overflow-y: auto; }
.raw-text { font-size: 12px; line-height: 1.7; color: @dark-text-sec; white-space: pre-wrap; word-break: break-all; margin: 0; font-family: inherit; }

/* ── 章节列表 ── */
.section-item { display: flex; align-items: flex-start; gap: 8px; padding: 6px 0; border-bottom: 1px solid rgba(139,92,246,0.06); font-size: 12px; }
.sec-badge { flex-shrink: 0; background: rgba(139,92,246,0.12); color: @primary-400; padding: 1px 6px; border-radius: 4px; font-size: 10px; }
.sec-title { flex-shrink: 0; color: @dark-text; font-weight: 500; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sec-content { color: @dark-text-muted; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }

/* ── 表格卡片 ── */
.table-card { background: rgba(0,0,0,0.2); border: 1px solid rgba(139,92,246,0.1); border-radius: 8px; margin-bottom: 8px; overflow: hidden; }
.table-card-header { display: flex; align-items: center; gap: 10px; padding: 10px 14px; cursor: pointer; &:hover { background: rgba(139,92,246,0.06); } }
.table-card-title { font-size: 13px; color: @dark-text; font-weight: 500; }
.table-card-meta { font-size: 11px; color: @dark-text-muted; }
.expand-icon { margin-left: auto; font-size: 10px; color: @dark-text-muted; }
.table-card-body { padding: 0 14px 14px; overflow-x: auto; }
.md-table {
  :deep(table) { width: 100%; border-collapse: collapse; font-size: 11px;
    th, td { padding: 5px 8px; border: 1px solid rgba(139,92,246,0.12); color: @dark-text-sec; text-align: left; }
    th { background: rgba(139,92,246,0.08); color: @dark-text; font-weight: 500; }
    .table-more { text-align: center; color: @dark-text-muted; font-style: italic; }
  }
}

/* ── 统计行 ── */
.stat-row { display: flex; gap: 16px; margin-bottom: 14px; }
.stat-card { display: flex; flex-direction: column; align-items: center; padding: 10px 20px; background: rgba(139,92,246,0.06); border: 1px solid rgba(139,92,246,0.1); border-radius: 8px; min-width: 80px; }
.stat-num { font-size: 22px; font-weight: 700; color: @primary-400; }
.stat-lbl { font-size: 11px; color: @dark-text-muted; margin-top: 2px; }

/* ── 分块列表 ── */
.chunks-list { display: flex; flex-direction: column; gap: 6px; max-height: 400px; overflow-y: auto; }
.chunk-card { background: rgba(0,0,0,0.2); border: 1px solid rgba(139,92,246,0.08); border-radius: 8px; padding: 10px 12px; }
.chunk-hdr { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
.chunk-idx { font-size: 11px; color: @dark-text-muted; font-weight: 600; min-width: 24px; }
.chunk-tag { font-size: 10px; padding: 1px 6px; border-radius: 4px;
  &.tag-text { background: rgba(59,130,246,0.15); color: #60a5fa; }
  &.tag-table { background: rgba(34,197,94,0.15); color: #4ade80; }
  &.tag-overlap { background: rgba(245,158,11,0.15); color: #fbbf24; }
}
.chunk-meta { font-size: 10px; color: @dark-text-muted; }
.chunk-len { margin-left: auto; }
.chunk-txt { font-size: 12px; color: @dark-text-sec; line-height: 1.6; word-break: break-all; }

/* ── 状态列表 ── */
.status-list { display: flex; flex-direction: column; gap: 10px; }
.status-row { display: flex; align-items: center; gap: 10px; padding: 11px 16px; background: rgba(34,197,94,0.04); border: 1px solid rgba(34,197,94,0.1); border-radius: 8px; }
.status-row.info-row { background: rgba(245,158,11,0.04); border-color: rgba(245,158,11,0.1); }
.si { font-size: 16px; flex-shrink: 0; }
.st { font-size: 13px; color: @dark-text; font-weight: 500; min-width: 120px; }
.sd { font-size: 12px; color: @dark-text-muted; }

/* ── 字段标签 ── */
.field-tags { display: flex; flex-wrap: wrap; gap: 6px; padding: 4px 0; }
.field-tag { font-size: 11px; padding: 2px 8px; border-radius: 4px;
  &.tag-num { background: rgba(59,130,246,0.12); color: #60a5fa; }
  &.tag-str { background: rgba(139,92,246,0.12); color: @primary-400; }
}

/* ── 工作表预览 ── */
.sheet-preview { margin-bottom: 16px; }
.sheet-name { font-size: 13px; font-weight: 500; color: @dark-text; margin-bottom: 6px; .sheet-meta { font-size: 11px; color: @dark-text-muted; margin-left: 8px; } }
.field-summary { font-size: 12px; color: @dark-text-sec; margin-bottom: 8px; .field-group { display: block; margin-bottom: 2px; } }
.sample-table-wrap { overflow-x: auto; border: 1px solid rgba(139,92,246,0.1); border-radius: 8px; }
.sample-table { width: 100%; border-collapse: collapse; font-size: 11px;
  th, td { padding: 5px 8px; border: 1px solid rgba(139,92,246,0.08); color: @dark-text-sec; text-align: left; white-space: nowrap; max-width: 150px; overflow: hidden; text-overflow: ellipsis; }
  th { background: rgba(139,92,246,0.06); color: @dark-text; font-weight: 500; }
}

/* ── 数据库表列表 ── */
.db-table-list { display: flex; flex-direction: column; gap: 4px; max-height: 400px; overflow-y: auto; }
.db-table-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: rgba(0,0,0,0.15); border: 1px solid rgba(139,92,246,0.06); border-radius: 6px; }
.db-tbl-idx { font-size: 11px; color: @dark-text-muted; min-width: 20px; }
.db-tbl-name { font-size: 13px; color: @dark-text; font-weight: 500; }
.db-tbl-comment { font-size: 11px; color: @dark-text-muted; margin-left: auto; }

/* ── 就绪 ── */
.ready-panel { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; min-height: 240px; }
.ready-icon { font-size: 48px; margin-bottom: 12px; }
.ready-title { font-size: 18px; font-weight: 600; color: @dark-text; margin-bottom: 12px; }
.ready-summary { font-size: 13px; color: @dark-text-sec; margin-bottom: 8px; .dot { margin: 0 6px; color: @dark-text-muted; } }
.ready-hint { font-size: 12px; color: @dark-text-muted; }
</style>
