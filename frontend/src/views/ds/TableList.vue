<template>
  <div class="table-list-page">
    <!-- 顶部导航栏 -->
    <div class="page-header">
      <div class="header-left">
        <el-button class="back-btn" text :icon="ArrowLeft" @click="back()" />
        <div class="chatbi-page-title">
          <span class="title-text">{{ props.dsName }}</span>
        </div>
      </div>
      <el-button v-if="!isPdfType" class="edit-tables-btn" :icon="CreditCard" @click="editTables(ds)">
        {{ t('ds.manage_tables') }}
      </el-button>
    </div>

    <!-- 主内容区 -->
    <div class="page-content">
      <!-- 左侧表列表 -->
      <div class="tables-sidebar">
        <div class="sidebar-header">
          <h3 class="sidebar-title">{{ isPdfType ? t('ds_pdf.document_content') : t('ds.tables') }}</h3>
          <span class="table-count">{{ isPdfType ? (pdfStats?.total_chunks || 0) : tableList.length }}</span>
        </div>
        
        <el-input
          v-model="searchValue"
          class="search-input"
          clearable
          :placeholder="t('ds.Search Datasource')"
          :prefix-icon="Search"
        />
        
        <div class="table-list">
          <!-- PDF数据源：显示章节列表 -->
          <template v-if="isPdfType && pdfSections.length > 0">
            <div class="table-item pdf-section-sidebar" v-for="(sec, idx) in pdfSections" :key="'sec-' + idx"
                 @click="pdfActiveName = 'content'; expandedSection = expandedSection === idx ? null : idx">
              <span class="section-sidebar-icon">§</span>
              <span class="table-name">{{ sec }}</span>
            </div>
          </template>
          <!-- 非PDF数据源：表列表 -->
          <template v-if="!isPdfType">
          <div
            v-for="(item, _index) in tableList"
            :key="_index"
            class="table-item"
            :class="{ active: currentTable.id === item.id }"
            @click="clickTable(item)"
          >
            <el-icon class="table-icon"><Document /></el-icon>
            <span class="table-name">{{ item.table_name }}</span>
          </div>
          </template>
        </div>
      </div>

      <!-- 右侧详情区 -->
      <div class="table-details">
        <!--  PDF文档视图：RAG流水线三阶段展示（文档解析/提取 → 文本预处理 → 向量化） -->
        <div v-if="isPdfType" class="details-content" v-loading="pdfLoading">
          <!-- PDF加载错误/空状态提示 -->
          <div v-if="pdfLoadError" class="pdf-error-state">
            <div class="error-icon">⚠️</div>
            <p class="error-text">{{ pdfLoadError }}</p>
            <el-button type="primary" size="small" @click="loadPdfDocInfo">{{ t('ds_pdf.reload') }}</el-button>
          </div>

          <template v-else-if="!pdfLoading">
          <!-- 顶部：文件信息 + 流水线进度条 -->
          <div class="details-header">
            <div class="table-info">
              <h2 class="table-title">📄 {{ pdfDocInfo?.filename || props.dsName }}</h2>
              <div class="table-meta" v-if="pdfDocInfo">
                <span class="meta-label">{{ t('ds_pdf.file_size') }}:</span>
                <span class="meta-value">{{ formatFileSize(pdfDocInfo.file_size) }}</span>
                <span class="meta-label" style="margin-left: 16px;">{{ t('ds_pdf.processing_time') }}:</span>
                <span class="meta-value">{{ pdfDocInfo.processing_time?.toFixed(2) }}s</span>
                <span class="meta-label" style="margin-left: 16px;">{{ t('ds_pdf.raw_text_total') }}:</span>
                <span class="meta-value">{{ (pdfDocInfo.raw_text_length || 0).toLocaleString() }} {{ t('ds_pdf.chars_unit') }}</span>
              </div>
            </div>
            <!-- 文档视角导航 -->
            <div class="pipeline-indicator">
              <div class="pip-step" :class="{ active: pdfActiveName === 'overview' }" @click="pdfActiveName = 'overview'">
                <span class="pip-icon">📋</span><span class="pip-label">{{ t('ds_pdf.nav_overview') }}</span>
              </div>
              <div class="pip-step" :class="{ active: pdfActiveName === 'content' }" @click="pdfActiveName = 'content'">
                <span class="pip-icon">📖</span><span class="pip-label">{{ t('ds_pdf.nav_content') }}</span>
              </div>
              <div class="pip-step" :class="{ active: pdfActiveName === 'search' }" @click="pdfActiveName = 'search'">
                <span class="pip-icon">🔍</span><span class="pip-label">{{ t('ds_pdf.nav_search_quality') }}</span>
              </div>
            </div>
          </div>

          <el-tabs v-model="pdfActiveName" class="details-tabs">
            <!-- ═══ Tab 1: 文档概览 — RAG 处理流水线可视化 ═══ -->
            <el-tab-pane :label="t('ds_pdf.nav_overview')" name="overview">
              <!-- RAG 处理流水线可视化（水平三阶段：解析→预处理→向量化） -->
              <div class="pipeline-summary">
                <div class="ps-stage">
                  <div class="ps-icon">📥</div>
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
            </el-tab-pane>

            <!-- ═══ Tab 2: 内容浏览 — 章节、表格与原始文本 ═══ -->
            <el-tab-pane :label="t('ds_pdf.nav_content')" name="content">
              <!-- 章节内容（可展开） -->
              <div class="pdf-sections" v-if="pdfSections.length > 0">
                <div class="pdf-section-title">📑 {{ t('ds_pdf.content_sections_title') }}</div>
                <div class="pdf-section-list">
                  <template v-for="(sec, idx) in pdfSections" :key="idx">
                    <div class="pdf-section-item clickable"
                         :class="{ active: expandedSection === idx }" @click="toggleSection(idx)">
                      <span class="section-idx">{{ idx + 1 }}</span>
                      <span class="section-name">{{ sec }}</span>
                      <span class="section-badge">{{ getSectionChunks(sec).length }} {{ t('ds_pdf.text_chunks') }}</span>
                      <span class="section-expand-icon">{{ expandedSection === idx ? '▼' : '▶' }}</span>
                    </div>
                    <div v-if="expandedSection === idx" class="section-expanded-content">
                      <template v-for="chunk in getSectionChunks(sec)" :key="chunk.id">
                        <div class="expanded-chunk-item">
                          <div class="expanded-chunk-meta">
                            <span class="chunk-type-tag" :class="getChunkTypeClass(chunk.chunk_type)">{{ getChunkTypeLabel(chunk.chunk_type) }}</span>
                            <span class="chunk-meta" v-if="chunk.page_number">{{ t('ds_pdf.page_n', { n: chunk.page_number }) }}</span>
                            <span class="chunk-meta">{{ t('ds_pdf.section_content_chars', { n: chunk.full_length }) }}</span>
                          </div>
                          <div class="expanded-chunk-text">{{ chunk.full_text || chunk.text }}</div>
                        </div>
                      </template>
                      <div v-if="getSectionChunks(sec).length === 0" class="empty-hint-small">{{ t('ds_pdf.section_no_chunks') }}</div>
                    </div>
                  </template>
                </div>
              </div>

              <!-- 文档中的表格 -->
              <div class="pdf-sections" v-if="tableChunksList.length > 0" style="margin-top: 20px;">
                <div class="pdf-section-title">🗃️ {{ t('ds_pdf.content_tables_title') }}</div>
                <div class="pdf-section-list">
                  <template v-for="(chunk, idx) in tableChunksList" :key="chunk.id">
                    <div class="pdf-section-item clickable"
                         :class="{ active: expandedTable === idx }" @click="toggleTableExpand(idx)">
                      <span class="section-idx">▦</span>
                      <span class="section-name">{{ t('ds_pdf.table_index', { n: idx + 1 }) }} · {{ chunk.page_number ? t('ds_pdf.page_n', { n: chunk.page_number }) : '' }} · {{ t('ds_pdf.n_chars', { n: chunk.full_length }) }}</span>
                      <span class="section-expand-icon">{{ expandedTable === idx ? '▼' : '▶' }}</span>
                    </div>
                    <div v-if="expandedTable === idx" class="section-expanded-content">
                      <div class="expanded-chunk-text table-text">{{ chunk.full_text || chunk.text }}</div>
                    </div>
                  </template>
                </div>
              </div>

              <!-- 原始文本预览 -->
              <div class="pdf-sections" v-if="pdfDocInfo?.raw_text_preview" style="margin-top: 20px;">
                <div class="pdf-section-title clickable-title" @click="showRawText = !showRawText">
                  📝 {{ t('ds_pdf.content_raw_text_title') }}
                  <span class="title-meta">{{ (pdfDocInfo.raw_text_length || 0).toLocaleString() }} {{ t('ds_pdf.chars_unit') }}</span>
                  <span class="section-expand-icon">{{ showRawText ? '▼' : '▶' }}</span>
                </div>
                <div v-if="showRawText" class="raw-text-preview">{{ pdfDocInfo.raw_text_preview }}</div>
              </div>

              <div v-if="pdfSections.length === 0 && tableChunksList.length === 0 && !pdfDocInfo?.raw_text_preview" class="empty-hint-small" style="text-align:center; padding: 40px 0;">
                {{ t('ds_pdf.content_no_content') }}
              </div>
            </el-tab-pane>

            <!-- ═══ Tab 3: 检索质量 — 向量化覆盖与分块分布 ═══ -->
            <el-tab-pane :label="t('ds_pdf.nav_search_quality')" name="search">
              <!-- 向量化覆盖率（含进度条） -->
              <div class="search-coverage-card">
                <div class="scc-left">
                  <div class="scc-title">🎯 {{ t('ds_pdf.search_vectorization_coverage') }}</div>
                  <div class="scc-desc">{{ t('ds_pdf.search_quality_score') }}: <span :style="{ color: searchReadiness.color, fontWeight: 700 }">{{ searchReadiness.label }}</span></div>
                </div>
                <div class="scc-progress" v-if="pdfVectorization">
                  <div class="progress-bar-wrap">
                    <div class="progress-bar-fill" :style="{ width: vectorizedPercent + '%' }"></div>
                  </div>
                  <div class="progress-text">{{ t('ds_pdf.vectorized_ratio', { done: pdfVectorization.vectorized_count || 0, total: pdfVectorization.total_chunks || 0 }) }} ({{ vectorizedPercent }}%)</div>
                </div>
              </div>

              <!-- 分块类型分布 -->
              <div class="pdf-sections" v-if="chunkTypeDistribution.length > 0" style="margin-top: 20px;">
                <div class="pdf-section-title">📈 {{ t('ds_pdf.search_chunk_distribution') }}</div>
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
              <div class="pipeline-info-grid" style="margin-top: 20px;">
                <div class="info-card">
                  <span class="info-card-label">🧠 {{ t('ds_pdf.search_embedding_config') }}</span>
                  <span class="info-card-value hl">{{ pdfVectorization?.embedding_model || 'BAAI/bge-base-zh-v1.5' }} · {{ t('ds_pdf.embedding_dim_value', { n: pdfVectorization?.embedding_dim || 768 }) }}</span>
                </div>
                <div class="info-card">
                  <span class="info-card-label">🗄️ {{ t('ds_pdf.search_storage_config') }}</span>
                  <span class="info-card-value">{{ t('ds_pdf.vec_storage_desc') }}</span>
                </div>
              </div>

              <!-- 跳过原因 -->
              <div class="pdf-sections" v-if="pdfVectorization?.skip_reasons && (pdfVectorization.skip_reasons.table_overlap > 0 || pdfVectorization.skip_reasons.short_text > 0)" style="margin-top: 20px;">
                <div class="pdf-section-title">⏭️ {{ t('ds_pdf.search_skip_details') }}</div>
                <div class="status-list">
                  <div class="status-row" v-if="pdfVectorization.skip_reasons.table_overlap > 0">
                    <span class="si">🔄</span>
                    <span class="st">{{ t('ds_pdf.skip_reason_overlap') }}</span>
                    <span class="sd">{{ pdfVectorization.skip_reasons.table_overlap }}</span>
                  </div>
                  <div class="status-row" v-if="pdfVectorization.skip_reasons.short_text > 0">
                    <span class="si">📏</span>
                    <span class="st">{{ t('ds_pdf.skip_reason_short') }}</span>
                    <span class="sd">{{ pdfVectorization.skip_reasons.short_text }}</span>
                  </div>
                </div>
              </div>

              <!-- 全部分块状态 -->
              <div class="pdf-sections" style="margin-top: 20px;">
                <div class="pdf-section-title">🧩 {{ t('ds_pdf.search_all_chunks') }} <span class="title-meta">{{ pdfChunks.length }} {{ t('ds_pdf.text_chunks') }}</span></div>
                <div class="pdf-section-title" style="font-size: 12px; font-weight: 400; color: rgba(196,181,253,0.5); margin-top: -6px;">{{ t('ds_pdf.all_chunks_desc') }}</div>
                <div class="pdf-chunks-list">
                  <div v-for="chunk in pdfChunks" :key="chunk.id" class="pdf-chunk-card"
                       :class="{ 'chunk-overlap': chunk.chunk_type === 'table_overlap' }"
                       @click="toggleChunkExpand(chunk.id)">
                    <div class="chunk-header">
                      <span class="chunk-idx-badge">{{ t('ds_pdf.chunk_index_label', { n: chunk.chunk_index }) }}</span>
                      <span class="chunk-type-tag" :class="getChunkTypeClass(chunk.chunk_type)">{{ getChunkTypeLabel(chunk.chunk_type) }}</span>
                      <span class="chunk-meta" v-if="chunk.section_title">📑 {{ chunk.section_title }}</span>
                      <span class="chunk-meta" v-if="chunk.page_number">{{ t('ds_pdf.page_n', { n: chunk.page_number }) }}</span>
                      <span class="chunk-meta chunk-len">{{ chunk.full_length }} {{ t('ds_pdf.chars_unit') }}</span>
                      <span class="chunk-embed-badge" :class="chunk.has_embedding ? 'badge-yes' : 'badge-no'">
                        {{ chunk.has_embedding ? '✅' : '⏭️' }}
                      </span>
                      <span class="chunk-expand-icon">{{ expandedChunks.has(chunk.id) ? '▼' : '▶' }}</span>
                    </div>
                    <div v-if="expandedChunks.has(chunk.id)" class="chunk-text-full" @click.stop>{{ chunk.full_text || chunk.text }}</div>
                    <div v-else class="chunk-text">{{ chunk.text }}</div>
                  </div>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
          </template>
        </div>

        <!-- 非PDF数据源：原有逻辑 -->
        <div v-else-if="fieldList.length === 0" class="empty-state">
          <div class="empty-icon">
            <el-icon><Document /></el-icon>
          </div>
          <p class="empty-text">{{ t('ds.no_data_tip') }}</p>
        </div>
        
        <div v-else class="details-content">
          <!-- 表信息头部 -->
          <div class="details-header">
            <div class="table-info">
              <h2 class="table-title">{{ currentTable.table_name }}</h2>
              <div class="table-meta">
                <span class="meta-label">{{ t('ds.comment') }}:</span>
                <span class="meta-value">{{ currentTable.custom_comment || t('ds.no_comment') }}</span>
                <el-button
                  class="edit-btn"
                  text
                  :icon="IconOpeEdit"
                  @click="editTable"
                />
              </div>
            </div>
          </div>

          <!-- 标签页 -->
          <el-tabs v-model="activeName" class="details-tabs" @tab-click="handleClick">
            <el-tab-pane :label="t('ds.table_schema')" name="schema">
              <el-table :data="fieldList" class="fields-table">
                <el-table-column prop="field_name" :label="t('ds.field.name')" width="200" />
                <el-table-column prop="field_type" :label="t('ds.field.type')" width="150" />
                <el-table-column prop="field_comment" :label="t('ds.field.comment')" min-width="200" />
                <el-table-column :label="t('ds.field.custom_comment')" min-width="250">
                  <template #default="scope">
                    <div class="field-comment">
                      <span class="comment-text">{{ scope.row.custom_comment || t('ds.no_comment') }}</span>
                      <el-button
                        class="edit-btn"
                        text
                        :icon="IconOpeEdit"
                        @click="editField(scope.row)"
                      />
                    </div>
                  </template>
                </el-table-column>
                <el-table-column :label="t('ds.field.status')" width="100" align="center">
                  <template #default="scope">
                    <el-switch
                      v-model="scope.row.checked"
                      size="small"
                      @change="changeStatus(scope.row)"
                    />
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
            
            <el-tab-pane :label="t('ds.preview')" name="preview">
              <div class="preview-tip">{{ t('ds.preview_tip') }}</div>
              <el-table :data="previewData.data" class="preview-table" max-height="600">
                <el-table-column
                  v-for="(c, index) in previewData.fields"
                  :key="index"
                  :prop="c"
                  :label="c"
                  min-width="150"
                />
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>
    </div>

    <!-- 编辑表注释对话框 -->
    <el-dialog
      v-model="tableDialog"
      :title="t('ds.edit.table_comment')"
      width="600"
      :destroy-on-close="true"
      :close-on-click-modal="false"
      :show-close="false"
      @closed="closeTable"
    >
      <div class="dialog-label">{{ t('ds.edit.table_comment_label') }}</div>
      <el-input v-model="tableComment" clearable :rows="3" type="textarea" />
      <template #footer>
        <div class="dialog-footer">
          <el-button secondary @click="closeTable">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" @click="saveTable">{{ t('common.confirm') }}</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 编辑字段注释对话框 -->
    <el-dialog
      v-model="fieldDialog"
      :title="t('ds.edit.field_comment')"
      width="600"
      :destroy-on-close="true"
      :close-on-click-modal="false"
      :show-close="false"
      @closed="closeField"
    >
      <div class="dialog-label">{{ t('ds.edit.field_comment_label') }}</div>
      <el-input v-model="fieldComment" clearable :rows="3" type="textarea" />
      <template #footer>
        <div class="dialog-footer">
          <el-button secondary @click="closeField">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" @click="saveField">{{ t('common.confirm') }}</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
  <DsForm ref="dsForm" @refresh="refresh" />
</template>

<script setup lang="tsx">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus-secondary'
import { datasourceApi } from '@/api/datasource'
import { onMounted, watch, computed } from 'vue'
import { ArrowLeft, Search, Document, CreditCard } from '@element-plus/icons-vue'
import type { TabsPaneContext } from 'element-plus-secondary'
import IconOpeEdit from '@/assets/svg/operate/ope-edit.svg'
import DsForm from './form.vue'

const props = defineProps({
  dsId: { type: [Number], required: true },
  dsName: { type: [String], required: true },
})

const { t } = useI18n()

// eslint-disable-next-line vue/no-dupe-keys
const dsId = ref<number>(0)
const searchValue = ref('')
const tableList = ref<any>([])
const allTableList = ref<any>([])  //  保存完整列表用于搜索过滤
const currentTable = ref<any>({})
const currentField = ref<any>({})
const fieldList = ref<any>([])
const previewData = ref<any>({})

const activeName = ref('schema')
const tableDialog = ref<boolean>(false)
const fieldDialog = ref<boolean>(false)
const dsForm = ref()
const ds = ref<any>({})
const tableComment = ref('')
const fieldComment = ref('')

// PDF文档预览相关状态
const isPdfType = computed(() => {
  const d = ds.value
  if (!d) return false
  if (d.type === 'pdf') return true
  if (d.type_name === 'PDF') return true
  return false
})
const pdfActiveName = ref('overview')
const pdfDocInfo = ref<any>(null)
const pdfChunks = ref<any[]>([])
const pdfStats = ref<any>(null)
const pdfSections = ref<string[]>([])
const pdfVectorization = ref<any>(null)
const pdfLoading = ref(false)
const expandedSection = ref<number | null>(null)
const expandedTable = ref<number | null>(null)
const expandedChunks = ref<Set<number>>(new Set())

const formatFileSize = (bytes: number) => {
  if (!bytes) return t('ds_pdf.unknown')
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// 分块类型标签和样式
const getChunkTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    section: '📄 ' + t('ds_pdf.chunk_type_section'),
    section_split: '📄 ' + t('ds_pdf.chunk_type_section_split'),
    table: '📊 ' + t('ds_pdf.chunk_type_table'),
    table_overlap: '🔄 ' + t('ds_pdf.chunk_type_table_overlap'),
    sliding_window: '📄 ' + t('ds_pdf.chunk_type_sliding_window'),
    text: '📄 ' + t('ds_pdf.chunk_type_section'),
  }
  return map[type] || '📄 ' + type
}
const getChunkTypeClass = (type: string) => {
  if (type === 'table') return 'tag-table'
  if (type === 'table_overlap') return 'tag-overlap'
  if (type === 'sliding_window') return 'tag-window'
  return 'tag-text'
}

// 获取某章节下的所有chunk
const getSectionChunks = (sectionTitle: string) => {
  return pdfChunks.value.filter((c: any) => c.section_title === sectionTitle)
}

// 表格类型的chunk列表
const tableChunksList = computed(() => {
  return pdfChunks.value.filter((c: any) => c.chunk_type === 'table')
})

// 向量化百分比
const vectorizedPercent = computed(() => {
  const v = pdfVectorization.value
  if (!v || !v.total_chunks) return 0
  return Math.round((v.vectorized_count / v.total_chunks) * 100)
})

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

// 分块类型分布统计
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

const showRawText = ref(false)

// 展开/收起
const toggleSection = (idx: number) => { expandedSection.value = expandedSection.value === idx ? null : idx }
const toggleTableExpand = (idx: number) => { expandedTable.value = expandedTable.value === idx ? null : idx }
const toggleChunkExpand = (id: number) => {
  const s = new Set(expandedChunks.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  expandedChunks.value = s
}

const pdfLoadError = ref('')

const loadPdfDocInfo = () => {
  if (!dsId.value) return
  pdfLoadError.value = ''
  pdfLoading.value = true
  datasourceApi.getDocumentByDatasource(dsId.value).then((res: any) => {
    if (!res.document) {
      pdfLoadError.value = t('ds_pdf.doc_not_found')
      return
    }
    pdfDocInfo.value = res.document
    pdfChunks.value = res.chunks || []
    pdfStats.value = res.stats || null
    pdfSections.value = res.sections || []
    pdfVectorization.value = res.vectorization || null
  }).catch((err: any) => {
    const msg = err?.msg || err?.message || 'Unknown error'
    if (msg.includes('非PDF数据源') || msg.includes('not a PDF')) {
      pdfLoadError.value = ''
    } else {
      pdfLoadError.value = t('ds_pdf.load_failed_detail', { msg })
    }
  }).finally(() => {
    pdfLoading.value = false
  })
}

const buildData = () => {
  return { table: currentTable.value, fields: fieldList.value }
}

const back = () => {
  history.back()
}

// const save = () => {

const editTable = () => {
  tableComment.value = currentTable.value.custom_comment
  tableDialog.value = true
}

const closeTable = () => {
  tableDialog.value = false
}

const saveTable = () => {
  currentTable.value.custom_comment = tableComment.value
  datasourceApi.saveTable(currentTable.value).then(() => {
    closeTable()
    ElMessage({
      message: t('common.save_success'),
      type: 'success',
      showClose: true,
    })
  }).catch(() => {
    ElMessage.error(t('common.save_failed'))
  })
}

const editField = (row: any) => {
  currentField.value = row
  fieldComment.value = currentField.value.custom_comment
  fieldDialog.value = true
}

const changeStatus = (row: any) => {
  currentField.value = row
  datasourceApi.saveField(currentField.value).then(() => {
    // 移除 closeField() 调用
    // changeStatus 由 el-switch @change 触发，与字段注释编辑对话框无关
    ElMessage({
      message: t('common.save_success'),
      type: 'success',
      showClose: true,
    })
  }).catch(() => {
    // 保存失败时回滚 switch 状态
    row.checked = !row.checked
    ElMessage.error(t('common.save_failed'))
  })
}

const closeField = () => {
  fieldDialog.value = false
}

const saveField = () => {
  currentField.value.custom_comment = fieldComment.value
  datasourceApi.saveField(currentField.value).then(() => {
    closeField()
    ElMessage({
      message: t('common.save_success'),
      type: 'success',
      showClose: true,
    })
  }).catch(() => {
    ElMessage.error(t('common.save_failed'))
  })
}

const clickTable = (table: any) => {
  currentTable.value = table
  fieldList.value = []
  previewData.value = {}
  datasourceApi.fieldList(table.id).then((res) => {
    fieldList.value = res
    // 仅在预览标签页时才加载预览数据（懒加载优化，避免浪费带宽）
    if (activeName.value === 'preview') {
      datasourceApi.previewData(dsId.value, buildData()).then((res) => {
        previewData.value = res
      }).catch(() => {
        ElMessage.error(t('common.load_failed'))
      })
    }
  }).catch(() => {
    ElMessage.error(t('common.load_failed'))
  })
}

const handleClick = (tab: TabsPaneContext) => {
  if (tab.paneName === 'preview') {
    datasourceApi.previewData(dsId.value, buildData()).then((res) => {
      previewData.value = res
    }).catch(() => {
      ElMessage.error(t('common.load_failed'))
    })
  }
}

const editTables = (item: any) => {
  dsForm.value.open(item, true)
}

const refresh = () => {
  init()
}

const init = () => {
  dsId.value = props.dsId
  datasourceApi.getDs(dsId.value).then((res) => {
    ds.value = res
    fieldList.value = []
    datasourceApi.tableList(props.dsId).then((tableRes) => {
      allTableList.value = tableRes
      tableList.value = tableRes
      // PDF数据源：加载文档分块预览（严格依赖 type/type_name 字段判断）
      // 移除 tableRes.every(t => t.table_name?.startsWith('pdf_')) 回退检测
      // 普通数据库表名可能以 pdf_ 开头（如 pdf_sales），会导致误判为 PDF 数据源
      if (res.type === 'pdf' || res.type_name === 'PDF') {
        loadPdfDocInfo()
      }
    }).catch(() => {
      ElMessage.error(t('common.load_failed'))
    })
  }).catch(() => {
    ElMessage.error(t('common.load_failed'))
  })
}

// 搜索过滤功能（searchValue 之前定义了但未使用）
watch(searchValue, (val) => {
  if (!val) {
    tableList.value = allTableList.value
  } else {
    tableList.value = allTableList.value.filter((item: any) =>
      item.table_name.toLowerCase().includes(val.toLowerCase())
    )
  }
})

onMounted(() => {
  init()
})
</script>

<style lang="less" scoped>
// ChatBI 表列表页面 - 深色主题设计
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

.table-list-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(180deg, @dark-bg 0%, @dark-bg-secondary 100%);
}

// 顶部导航栏
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: rgba(26, 18, 37, 0.95);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid @dark-border;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .back-btn {
    color: @dark-text-secondary !important;
    font-size: 18px;
    padding: 8px;
    transition: all 0.2s ease;

    &:hover {
      color: @primary-400 !important;
      background: rgba(139, 92, 246, 0.1);
    }
  }

  .edit-tables-btn {
    height: 40px;
    padding: 0 20px;
    background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%);
    border: none;
    border-radius: 10px;
    color: white;
    font-weight: 500;
    box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
    transition: all 0.25s ease;

    &:hover {
      box-shadow: 0 6px 20px rgba(139, 92, 246, 0.4);
      transform: translateY(-2px);
    }
  }
}

// 主内容区
.page-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

// 左侧表列表
.tables-sidebar {
  width: 280px;
  min-width: 280px;
  max-width: 280px;
  display: flex;
  flex-direction: column;
  background: @dark-bg-card;
  backdrop-filter: blur(16px);
  border-right: 1px solid @dark-border;
  padding: 20px;
  overflow: hidden;

  .sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    flex-shrink: 0;

    .sidebar-title {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: @dark-text;
    }

    .table-count {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 24px;
      height: 24px;
      padding: 0 8px;
      background: rgba(139, 92, 246, 0.2);
      border: 1px solid @dark-border;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
      color: @primary-400;
      flex-shrink: 0;
    }
  }

  .search-input {
    margin-bottom: 16px;
    flex-shrink: 0;
    width: 100%;

    :deep(.ed-input__wrapper),
    :deep(.el-input__wrapper) {
      background: rgba(139, 92, 246, 0.08);
      border: 1px solid @dark-border;
      border-radius: 10px;
      box-shadow: none;
      width: 100%;

      &:hover {
        border-color: rgba(139, 92, 246, 0.3);
      }

      &:focus-within {
        border-color: @primary-500;
        background: rgba(139, 92, 246, 0.12);
      }
    }

    :deep(.ed-input__inner),
    :deep(.el-input__inner) {
      color: @dark-text;

      &::placeholder {
        color: @dark-text-muted;
      }
    }
  }

  .table-list {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-height: 0;

    &::-webkit-scrollbar {
      width: 6px;
    }

    &::-webkit-scrollbar-thumb {
      background: rgba(139, 92, 246, 0.3);
      border-radius: 3px;

      &:hover {
        background: rgba(139, 92, 246, 0.5);
      }
    }
  }

  .table-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    background: rgba(139, 92, 246, 0.05);
    border: 1px solid transparent;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
    flex-shrink: 0;
    min-width: 0;

    .table-icon {
      color: @dark-text-muted;
      font-size: 16px;
      flex-shrink: 0;
    }

    .table-name {
      flex: 1;
      font-size: 14px;
      color: @dark-text-secondary;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      min-width: 0;
    }

    &:hover {
      background: rgba(139, 92, 246, 0.12);
      border-color: rgba(139, 92, 246, 0.2);

      .table-icon {
        color: @primary-400;
      }

      .table-name {
        color: @dark-text;
      }
    }

    &.active {
      background: rgba(139, 92, 246, 0.2);
      border-color: rgba(139, 92, 246, 0.35);

      .table-icon {
        color: @primary-400;
      }

      .table-name {
        color: @dark-text;
        font-weight: 500;
      }
    }
  }

  .pdf-section-sidebar {
    .section-sidebar-icon {
      font-size: 14px;
      flex-shrink: 0;
    }
  }

  .sidebar-divider {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    font-size: 11px;
    color: @dark-text-muted;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;

    &::after {
      content: '';
      flex: 1;
      height: 1px;
      background: @dark-border;
    }
  }
}

// 右侧详情区
.table-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: @dark-bg;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 40px;

  .empty-icon {
    width: 80px;
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(139, 92, 246, 0.1);
    border: 2px solid @dark-border;
    border-radius: 50%;
    margin-bottom: 20px;

    :deep(.el-icon) {
      font-size: 36px;
      color: @primary-400;
    }
  }

  .empty-text {
    font-size: 15px;
    color: @dark-text-muted;
    margin: 0;
  }
}

.details-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.details-header {
  padding: 24px;
  background: @dark-bg-card;
  backdrop-filter: blur(16px);
  border-bottom: 1px solid @dark-border;

  .table-info {
    .table-title {
      margin: 0 0 12px 0;
      font-size: 20px;
      font-weight: 600;
      color: @dark-text;
    }

    .table-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;

      .meta-label {
        color: @dark-text-muted;
      }

      .meta-value {
        color: @dark-text-secondary;
      }

      .edit-btn {
        color: @primary-400;
        padding: 4px 8px;

        &:hover {
          background: rgba(139, 92, 246, 0.15);
        }
      }
    }
  }
}

.details-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0 24px 24px 24px;

  :deep(.ed-tabs__header),
  :deep(.el-tabs__header) {
    margin-bottom: 20px;
  }

  :deep(.ed-tabs__content),
  :deep(.el-tabs__content) {
    flex: 1;
    overflow: hidden;
  }

  :deep(.ed-tab-pane),
  :deep(.el-tab-pane) {
    height: 100%;
    overflow: auto;
  }
}

.fields-table,
.preview-table {
  :deep(.ed-table),
  :deep(.el-table) {
    background: transparent;
    color: @dark-text;

    th {
      background: rgba(139, 92, 246, 0.1);
      color: @dark-text-secondary;
      font-weight: 600;
    }

    tr {
      background: transparent;

      &:hover {
        background: rgba(139, 92, 246, 0.05);
      }
    }

    td {
      border-color: @dark-border;
    }
  }
}

.field-comment {
  display: flex;
  align-items: center;
  gap: 8px;

  .comment-text {
    flex: 1;
    color: @dark-text-secondary;
  }

  .edit-btn {
    color: @primary-400;
    padding: 4px 8px;

    &:hover {
      background: rgba(139, 92, 246, 0.15);
    }
  }
}

.preview-tip {
  padding: 12px 16px;
  margin-bottom: 16px;
  background: rgba(139, 92, 246, 0.1);
  border: 1px solid @dark-border;
  border-radius: 10px;
  font-size: 13px;
  color: @dark-text-secondary;
}

// 对话框样式
.dialog-label {
  margin-bottom: 12px;
  font-size: 14px;
  color: @dark-text-secondary;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

// 响应式适配
@media (max-width: 1024px) {
  .tables-sidebar {
    width: 240px;
    min-width: 240px;
    max-width: 240px;
  }
}

@media (max-width: 768px) {
  .page-header {
    padding: 12px 16px;
  }

  .tables-sidebar {
    width: 200px;
    min-width: 200px;
    max-width: 200px;
    padding: 16px;
  }

  .details-header {
    padding: 16px;

    .table-title {
      font-size: 18px;
    }
  }

  .details-tabs {
    padding: 0 16px 16px 16px;
  }
}

// ===== PDF RAG流水线详情页样式 =====
.pdf-error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 60px 40px;
  text-align: center;

  .error-icon {
    font-size: 48px;
    margin-bottom: 16px;
  }

  .error-text {
    font-size: 14px;
    color: @dark-text-secondary;
    line-height: 1.6;
    margin: 0 0 20px 0;
    max-width: 400px;
  }
}

// 流水线进度指示条
.pipeline-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 16px;
  background: rgba(139, 92, 246, 0.06);
  border: 1px solid @dark-border;
  border-radius: 10px;
  margin-top: 14px;
  flex-wrap: wrap;

  .pip-step {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    color: @dark-text-muted;
    transition: all 0.2s ease;

    &:hover {
      background: rgba(139, 92, 246, 0.1);
      color: @dark-text-secondary;
    }

    &.active {
      background: rgba(139, 92, 246, 0.18);
      color: @primary-400;
      font-weight: 600;
    }

    &.pip-done {
      color: #22c55e;
    }

    .pip-icon { font-size: 14px; }
    .pip-label { white-space: nowrap; }
  }

  .pip-arrow {
    color: @dark-text-muted;
    font-size: 12px;
    margin: 0 2px;
  }
}

// 信息网格卡片
.pipeline-info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 18px;

  .info-card {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 12px 16px;
    background: rgba(139, 92, 246, 0.04);
    border: 1px solid rgba(139, 92, 246, 0.1);
    border-radius: 8px;

    .info-card-label {
      font-size: 11px;
      color: @dark-text-muted;
      font-weight: 600;
    }

    .info-card-value {
      font-size: 13px;
      color: @dark-text-secondary;
      line-height: 1.5;

      &.hl {
        color: @primary-400;
        font-weight: 600;
      }
    }
  }
}

.pdf-stats-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;

  .pdf-stat-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 14px 20px;
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid @dark-border;
    border-radius: 10px;
    min-width: 80px;

    .stat-num {
      font-size: 22px;
      font-weight: 700;
      color: @primary-400;

      &.stat-warn {
        color: #f59e0b;
      }
    }

    .stat-label {
      font-size: 12px;
      color: @dark-text-muted;
      margin-top: 4px;
      text-align: center;
    }

    &.stat-card-success {
      border-color: rgba(34, 197, 94, 0.3);
      background: rgba(34, 197, 94, 0.08);
      .stat-num { color: #22c55e; }
    }

    &.stat-card-warn {
      border-color: rgba(245, 158, 11, 0.3);
      background: rgba(245, 158, 11, 0.08);
      .stat-num { color: #f59e0b; }
    }
  }
}

.pdf-sections {
  .pdf-section-title {
    font-size: 14px;
    font-weight: 600;
    color: @dark-text;
    margin-bottom: 10px;
  }

  .pdf-section-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .pdf-section-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    background: rgba(139, 92, 246, 0.05);
    border: 1px solid transparent;
    border-radius: 8px;
    transition: all 0.2s ease;

    &.clickable {
      cursor: pointer;
      &:hover {
        background: rgba(139, 92, 246, 0.12);
        border-color: rgba(139, 92, 246, 0.2);
      }
      &.active {
        background: rgba(139, 92, 246, 0.18);
        border-color: rgba(139, 92, 246, 0.3);
      }
    }

    .section-idx {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: rgba(139, 92, 246, 0.15);
      font-size: 11px;
      font-weight: 700;
      color: @primary-400;
      flex-shrink: 0;
    }

    .section-name {
      font-size: 13px;
      color: @dark-text-secondary;
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .section-expand-icon {
      font-size: 10px;
      color: @dark-text-muted;
      flex-shrink: 0;
    }
  }
}

// 展开的章节/表格内容
.section-expanded-content {
  padding: 10px 14px 14px 48px;
  display: flex;
  flex-direction: column;
  gap: 8px;

  .expanded-chunk-item {
    padding: 10px 12px;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(139, 92, 246, 0.08);
    border-radius: 8px;

    .expanded-chunk-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
      flex-wrap: wrap;
    }

    .expanded-chunk-text {
      font-size: 13px;
      line-height: 1.7;
      color: @dark-text-secondary;
      white-space: pre-wrap;
      word-break: break-word;
    }
  }

  .empty-hint-small {
    font-size: 12px;
    color: @dark-text-muted;
    padding: 8px 0;
  }
}

.table-text {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px !important;
}

// 分块列表样式
.pdf-chunks-list {
  display: flex;
  flex-direction: column;
  gap: 8px;

  .pdf-chunk-card {
    padding: 12px 14px;
    background: rgba(139, 92, 246, 0.04);
    border: 1px solid @dark-border;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      border-color: rgba(139, 92, 246, 0.3);
      background: rgba(139, 92, 246, 0.08);
    }

    &.chunk-overlap {
      opacity: 0.6;
      border-color: rgba(245, 158, 11, 0.2);
      background: rgba(245, 158, 11, 0.04);
    }

    .chunk-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
      flex-wrap: wrap;
    }

    .chunk-idx-badge {
      font-size: 11px;
      font-weight: 700;
      color: @primary-400;
      background: rgba(139, 92, 246, 0.15);
      padding: 1px 6px;
      border-radius: 4px;
    }

    .chunk-type-tag {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 4px;
      font-weight: 600;

      &.tag-text {
        background: rgba(59, 130, 246, 0.15);
        color: #60a5fa;
      }

      &.tag-table {
        background: rgba(251, 191, 36, 0.15);
        color: #fbbf24;
      }

      &.tag-overlap {
        background: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
      }

      &.tag-window {
        background: rgba(34, 197, 94, 0.15);
        color: #22c55e;
      }
    }

    .chunk-meta {
      font-size: 11px;
      color: @dark-text-muted;
    }

    .chunk-len {
      margin-left: auto;
    }

    .chunk-embed-badge {
      font-size: 10px;
      padding: 1px 6px;
      border-radius: 4px;

      &.badge-yes {
        background: rgba(34, 197, 94, 0.12);
        color: #22c55e;
      }

      &.badge-no {
        background: rgba(245, 158, 11, 0.12);
        color: #f59e0b;
      }
    }

    .chunk-expand-icon {
      font-size: 10px;
      color: @dark-text-muted;
    }

    .chunk-text {
      font-size: 13px;
      line-height: 1.6;
      color: @dark-text-secondary;
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 60px;
      overflow: hidden;
      position: relative;

      &::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 30px;
        background: linear-gradient(transparent, rgba(15, 10, 26, 0.9));
      }
    }

    .chunk-text-full {
      font-size: 13px;
      line-height: 1.7;
      color: @dark-text-secondary;
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 400px;
      overflow-y: auto;
      padding: 8px;
      background: rgba(0, 0, 0, 0.2);
      border-radius: 6px;
      margin-top: 6px;

      &::-webkit-scrollbar {
        width: 6px;
      }
      &::-webkit-scrollbar-thumb {
        background: rgba(139, 92, 246, 0.3);
        border-radius: 3px;
      }
    }
  }
}

// 跳过原因列表
.status-list {
  display: flex;
  flex-direction: column;
  gap: 8px;

  .status-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    background: rgba(139, 92, 246, 0.04);
    border: 1px solid rgba(139, 92, 246, 0.08);
    border-radius: 8px;

    .si { font-size: 16px; flex-shrink: 0; }
    .st { font-size: 13px; color: @dark-text; font-weight: 500; white-space: nowrap; }
    .sd { font-size: 12px; color: @dark-text-muted; }
  }
}

// 向量化分块明细列表
.vec-chunk-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 400px;
  overflow-y: auto;

  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(139, 92, 246, 0.3);
    border-radius: 3px;
  }

  .vec-chunk-item {
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid transparent;

    &.vec-yes {
      background: rgba(34, 197, 94, 0.04);
      border-color: rgba(34, 197, 94, 0.1);
    }

    &.vec-no {
      background: rgba(245, 158, 11, 0.04);
      border-color: rgba(245, 158, 11, 0.1);
      opacity: 0.7;
    }

    .vec-chunk-header {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .vec-status-badge {
      font-size: 11px;
      padding: 1px 8px;
      border-radius: 4px;
      margin-left: auto;

      &.badge-yes {
        background: rgba(34, 197, 94, 0.12);
        color: #22c55e;
      }

      &.badge-no {
        background: rgba(245, 158, 11, 0.12);
        color: #f59e0b;
      }
    }
  }
}

// ===== RAG 处理流水线可视化（水平三阶段） =====
.pipeline-summary {
  display: flex;
  align-items: stretch;
  gap: 0;
  margin-bottom: 20px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.08) 0%, rgba(59, 130, 246, 0.04) 100%);
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 12px;
  overflow: hidden;

  .ps-stage {
    flex: 1;
    padding: 16px 14px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    border-right: 1px solid rgba(139, 92, 246, 0.1);
    &:last-child { border-right: none; }
    .ps-icon { font-size: 24px; margin-bottom: 6px; }
    .ps-title { font-size: 12px; font-weight: 700; color: @dark-text; margin-bottom: 8px; }
    .ps-metrics {
      display: flex; flex-direction: column; gap: 3px;
      span { font-size: 11px; color: @dark-text-muted; }
    }
    .ps-readiness { margin-top: 6px; font-size: 11px; font-weight: 700; }
  }
  .ps-arrow {
    display: flex; align-items: center; padding: 0 4px;
    font-size: 16px; color: @dark-text-muted; flex-shrink: 0;
  }
}

// ===== 检索质量覆盖率卡片 =====
.search-coverage-card {
  display: flex;
  flex-direction: column;
  margin-bottom: 20px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.1) 0%, rgba(59, 130, 246, 0.06) 100%);
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 12px;
  overflow: hidden;

  .scc-left {
    padding: 18px 20px;
    .scc-title { font-size: 15px; font-weight: 700; color: @dark-text; margin-bottom: 6px; }
    .scc-desc { font-size: 12px; color: @dark-text-muted; line-height: 1.6; }
  }
  .scc-progress {
    padding: 0 20px 18px;
    .progress-bar-wrap {
      height: 10px; background: rgba(139, 92, 246, 0.1); border-radius: 5px; overflow: hidden; margin-bottom: 8px;
      .progress-bar-fill {
        height: 100%; background: linear-gradient(90deg, @primary-500, #22c55e); border-radius: 5px; transition: width 0.5s ease;
      }
    }
    .progress-text { font-size: 12px; color: @dark-text-secondary; text-align: center; }
  }
}

// ===== 分块类型分布条形图 =====
.chunk-dist-bars {
  display: flex; flex-direction: column; gap: 8px;
  .cdb-row {
    display: flex; align-items: center; gap: 8px;
    .cdb-icon { font-size: 14px; flex-shrink: 0; width: 20px; text-align: center; }
    .cdb-label { font-size: 12px; color: @dark-text-secondary; width: 100px; flex-shrink: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .cdb-bar-wrap {
      flex: 1; height: 8px; background: rgba(139, 92, 246, 0.08); border-radius: 4px; overflow: hidden;
      .cdb-bar {
        height: 100%; border-radius: 4px; transition: width 0.5s ease;
        &.tag-text { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
        &.tag-table { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
        &.tag-overlap { background: linear-gradient(90deg, #ef4444, #f87171); opacity: 0.6; }
        &.tag-window { background: linear-gradient(90deg, #22c55e, #4ade80); }
      }
    }
    .cdb-count { font-size: 12px; font-weight: 700; color: @primary-400; width: 32px; text-align: right; flex-shrink: 0; }
  }
}

// ===== 原始文本预览 =====
.raw-text-preview {
  padding: 14px 16px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(139, 92, 246, 0.1);
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.7;
  color: @dark-text-secondary;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  margin-top: 8px;

  &::-webkit-scrollbar { width: 5px; }
  &::-webkit-scrollbar-thumb { background: rgba(139, 92, 246, 0.3); border-radius: 3px; }
}

// ===== 可点击标题 =====
.clickable-title {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: color 0.2s ease;
  &:hover { color: @primary-400; }
  .title-meta { font-size: 11px; color: @dark-text-muted; margin-left: auto; font-weight: 400; }
}

// ===== 章节分块数量标签 =====
.section-badge {
  font-size: 10px;
  color: @dark-text-muted;
  background: rgba(139, 92, 246, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
  margin-left: auto;
}
</style>
