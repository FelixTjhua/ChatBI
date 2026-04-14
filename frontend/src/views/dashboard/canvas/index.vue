<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus-secondary'
import { dashboardApi } from '@/api/dashboard'
import html2canvas from 'html2canvas'
import icon_arrow_left_outlined from '@/assets/svg/icon_arrow-left_outlined.svg'
import icon_undo_outlined from '@/assets/svg/icon_undo_outlined.svg'
import icon_redo_outlined from '@/assets/svg/icon_redo_outlined.svg'
import icon_export_outlined from '@/assets/svg/icon_export_outlined.svg'
import { Icon } from '@/components/icon-custom'
import ChartComponent from '@/views/chat/component/ChartComponent.vue'
import InsightCard from '@/views/dashboard/components/InsightCard.vue'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()

const isEmbedded = computed(() => route.query.embedded === 'true')

const dashboardName = ref('')
const dashboardId = ref<any>(null)
const loading = ref(false)
const selectedComponentIndex = ref<number | null>(null)
const canvasData = ref<any>({
  componentData: [],
  canvasStyleData: { width: 1920, height: 1080, scale: 100, color: '#0f0a1a', opacity: 1, background: '#0f0a1a' },
  canvasViewInfo: {},
})

// Undo/Redo history
const history = reactive<{ past: string[]; future: string[] }>({ past: [], future: [] })
const canUndo = computed(() => history.past.length > 0)
const canRedo = computed(() => history.future.length > 0)

function pushHistory() {
  history.past.push(JSON.stringify(canvasData.value.componentData))
  if (history.past.length > 30) history.past.shift()
  history.future = []
}

async function undo() {
  if (!canUndo.value) return
  history.future.push(JSON.stringify(canvasData.value.componentData))
  canvasData.value.componentData = JSON.parse(history.past.pop()!)
  selectedComponentIndex.value = null
  await autoSave()
}

async function redo() {
  if (!canRedo.value) return
  history.past.push(JSON.stringify(canvasData.value.componentData))
  canvasData.value.componentData = JSON.parse(history.future.pop()!)
  selectedComponentIndex.value = null
  await autoSave()
}

/** 自动保存到后端（静默） */
async function autoSave() {
  if (!dashboardId.value) return
  try {
    await dashboardApi.update_canvas({
      id: dashboardId.value, name: dashboardName.value,
      component_data: JSON.stringify(canvasData.value.componentData),
      canvas_style_data: JSON.stringify(canvasData.value.canvasStyleData),
      canvas_view_info: JSON.stringify(canvasData.value.canvasViewInfo),
      opt: 'updateLeaf', pid: 'root', node_type: 'leaf', type: 'dashboard',
      workspace_id: '', org_id: '', level: 0, create_by: 0, description: '',
    })
    lastSavedSnapshot.value = JSON.stringify(canvasData.value.componentData)
  } catch { /* 静默 */ }
}

// Drag logic
const dragging = ref(false)
const dragOffset = reactive({ x: 0, y: 0 })
const dragIndex = ref<number | null>(null)

function onDragStart(e: MouseEvent, index: number) {
  const target = e.target as HTMLElement
  if (target.closest('.resize-handle') || target.closest('.component-actions')) return
  e.preventDefault()
  pushHistory()
  dragging.value = true
  dragIndex.value = index
  selectedComponentIndex.value = index
  const comp = canvasData.value.componentData[index]
  dragOffset.x = e.clientX - comp.style.left
  dragOffset.y = e.clientY - comp.style.top
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
}

function onDragMove(e: MouseEvent) {
  if (!dragging.value || dragIndex.value === null) return
  const comp = canvasData.value.componentData[dragIndex.value]
  comp.style.left = Math.max(0, e.clientX - dragOffset.x)
  comp.style.top = Math.max(0, e.clientY - dragOffset.y)
}

function onDragEnd() {
  dragging.value = false
  dragIndex.value = null
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  autoSave()
}

// Resize logic
const resizing = ref(false)
const resizeIndex = ref<number | null>(null)
const resizeStart = reactive({ x: 0, y: 0, w: 0, h: 0 })

function onResizeStart(e: MouseEvent, index: number) {
  e.preventDefault()
  e.stopPropagation()
  pushHistory()
  resizing.value = true
  resizeIndex.value = index
  selectedComponentIndex.value = index
  const comp = canvasData.value.componentData[index]
  resizeStart.x = e.clientX
  resizeStart.y = e.clientY
  resizeStart.w = comp.style.width
  resizeStart.h = comp.style.height
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup', onResizeEnd)
}

function onResizeMove(e: MouseEvent) {
  if (!resizing.value || resizeIndex.value === null) return
  const comp = canvasData.value.componentData[resizeIndex.value]
  comp.style.width = Math.max(200, resizeStart.w + (e.clientX - resizeStart.x))
  comp.style.height = Math.max(150, resizeStart.h + (e.clientY - resizeStart.y))
}

function onResizeEnd() {
  resizing.value = false
  resizeIndex.value = null
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
  autoSave()
}

function selectComponent(index: number) { selectedComponentIndex.value = index }
function deselectAll(e: MouseEvent) {
  if ((e.target as HTMLElement).closest('.canvas-component')) return
  selectedComponentIndex.value = null
}

// 跟踪是否有未保存的更改（上次保存后的快照）
const lastSavedSnapshot = ref<string>('')

const loadDashboard = async () => {
  const resourceId = route.query.resourceId
  if (!resourceId) { dashboardName.value = t('dashboard.new_dashboard'); return }
  loading.value = true
  try {
    const res = await dashboardApi.load_resource({ id: resourceId })
    dashboardName.value = res.name || ''
    dashboardId.value = res.id
    if (res.component_data) try { canvasData.value.componentData = JSON.parse(res.component_data) } catch {}
    if (res.canvas_style_data) try { canvasData.value.canvasStyleData = JSON.parse(res.canvas_style_data) } catch {}
    if (res.canvas_view_info) try { canvasData.value.canvasViewInfo = JSON.parse(res.canvas_view_info) } catch {}
    lastSavedSnapshot.value = JSON.stringify(canvasData.value.componentData)
  } catch (error) { ElMessage.error(t('common.load_failed')) }
  finally { loading.value = false }
}

const goBack = () => {
  if (isEmbedded.value) window.parent.postMessage({ type: 'dashboard-back' }, '*')
  else router.push('/dashboard')
}

const saveDashboard = async () => {
  if (!dashboardId.value) {
    // 自动创建新仪表板
    if (!dashboardName.value.trim()) { dashboardName.value = t('dashboard.new_dashboard') }
    try {
      const res = await dashboardApi.create_resource({
        name: dashboardName.value, pid: 'root', node_type: 'leaf', type: 'dashboard', opt: 'newLeaf',
        workspace_id: '', org_id: '', level: 0, create_by: 0,
        canvas_style_data: JSON.stringify(canvasData.value.canvasStyleData),
        component_data: JSON.stringify(canvasData.value.componentData),
        canvas_view_info: JSON.stringify(canvasData.value.canvasViewInfo),
        description: '',
      })
      dashboardId.value = res.id || res
      // 更新 URL，使刷新后仍能加载此仪表板
      router.replace({ path: '/canvas', query: { resourceId: dashboardId.value } })
      lastSavedSnapshot.value = JSON.stringify(canvasData.value.componentData)
      ElMessage.success(t('dashboard.save_success'))
    } catch { ElMessage.error(t('dashboard.save_failed')) }
    return
  }
  try {
    await dashboardApi.update_canvas({
      id: dashboardId.value, name: dashboardName.value,
      component_data: JSON.stringify(canvasData.value.componentData),
      canvas_style_data: JSON.stringify(canvasData.value.canvasStyleData),
      canvas_view_info: JSON.stringify(canvasData.value.canvasViewInfo),
      opt: 'updateLeaf', pid: 'root', node_type: 'leaf', type: 'dashboard',
      workspace_id: '', org_id: '', level: 0, create_by: 0, description: '',
    })
    lastSavedSnapshot.value = JSON.stringify(canvasData.value.componentData)
    ElMessage.success(t('dashboard.save_success'))
  } catch { ElMessage.error(t('dashboard.save_failed')) }
}

const previewDashboard = async () => {
  // 先保存当前画布数据，确保预览看到的是最新内容
  if (dashboardId.value) {
    try {
      await autoSave()
    } catch { /* 静默，仍然打开预览 */ }
  }
  const url = router.resolve({ path: '/canvas', query: { resourceId: dashboardId.value, embedded: 'true' } }).href
  window.open(url, '_blank')
}

const removeComponent = async (index: number) => {
  pushHistory()
  canvasData.value.componentData.splice(index, 1)
  selectedComponentIndex.value = null
  await autoSave()
  ElMessage.success(t('dashboard.delete_success'))
}

// ========== 下载功能 ==========
const downloadLoading = ref(false)

/** 根据卡片类型返回可用的下载格式列表 */
function getDownloadOptions(index: number): Array<{ key: string; label: string; icon: string }> {
  const comp = canvasData.value.componentData[index]
  const pv = comp?.propValue
  if (!pv) return []
  const cardType = pv.cardType || 'chart'
  const hasChart = !!pv.chartType
  const hasData = pv.data && pv.data.length > 0
  const hasContent = !!pv.content

  if (cardType === 'chart') {
    // 纯图表：PNG + CSV
    const opts = [{ key: 'png', label: t('dashboard.dl_png'), icon: '🖼️' }]
    if (hasData) opts.push({ key: 'csv', label: t('dashboard.dl_csv'), icon: '📊' })
    return opts
  }
  if (cardType === 'data_table') {
    // 数据表：CSV
    return hasData ? [{ key: 'csv', label: t('dashboard.dl_csv'), icon: '📊' }] : []
  }
  if (cardType === 'analysis' || cardType === 'prediction') {
    const opts: Array<{ key: string; label: string; icon: string }> = []
    if (hasChart) opts.push({ key: 'png', label: t('dashboard.dl_png'), icon: '🖼️' })
    if (hasData) opts.push({ key: 'csv', label: t('dashboard.dl_csv'), icon: '📊' })
    if (hasContent) opts.push({ key: 'md', label: t('dashboard.dl_markdown'), icon: '📝' })
    return opts
  }
  if (cardType === 'document_qa') {
    // 文档问答：Markdown
    return hasContent ? [{ key: 'md', label: t('dashboard.dl_markdown'), icon: '📝' }] : []
  }
  return []
}

/** 处理下载命令 */
function handleDownload(command: string, index: number) {
  const [format, idxStr] = command.split(':')
  const i = parseInt(idxStr, 10)
  if (format === 'png') downloadAsPng(i)
  else if (format === 'csv') downloadAsCsv(i)
  else if (format === 'md') downloadAsMarkdown(i)
}

/** 下载为 PNG 图片（只截取图表区域） */
function downloadAsPng(index: number) {
  const comp = canvasData.value.componentData[index]
  const pv = comp?.propValue
  const wrapper = document.querySelectorAll('.canvas-component')[index] as HTMLElement
  if (!wrapper) { ElMessage.warning(t('dashboard.download_no_data')); return }
  // 优先截取图表区域：mini-chart（analysis/prediction）或 component-body
  const el = wrapper.querySelector('.insight-card__mini-chart') as HTMLElement
    || wrapper.querySelector('.component-body') as HTMLElement
  if (!el) { ElMessage.warning(t('dashboard.download_no_data')); return }
  downloadLoading.value = true
  html2canvas(el, { backgroundColor: '#0f0a1a', scale: 2, useCORS: true })
    .then((canvas) => {
      canvas.toBlob((blob) => {
        if (blob) triggerDownload(blob, `${pv?.title || 'chart'}.png`)
        else ElMessage.error(t('dashboard.download_no_data'))
      }, 'image/png')
    })
    .catch(() => ElMessage.error(t('dashboard.download_no_data')))
    .finally(() => { downloadLoading.value = false })
}

/** 下载为 CSV */
function downloadAsCsv(index: number) {
  const comp = canvasData.value.componentData[index]
  const pv = comp?.propValue
  if (!pv) return
  const data = pv.data
  if (!data || !data.length) { ElMessage.warning(t('dashboard.download_no_data')); return }
  const fields = pv.fields?.length ? pv.fields : Object.keys(data[0])
  const header = fields.join(',')
  const rows = data.map((row: any) =>
    fields.map((f: string) => {
      const str = String(row[f] ?? '')
      return (str.includes(',') || str.includes('"') || str.includes('\n'))
        ? `"${str.replace(/"/g, '""')}"` : str
    }).join(',')
  )
  const csv = '\uFEFF' + header + '\n' + rows.join('\n')
  triggerDownload(new Blob([csv], { type: 'text/csv; charset=utf-8' }), `${pv.title || 'data'}.csv`)
}

/** 下载为 Markdown */
function downloadAsMarkdown(index: number) {
  const comp = canvasData.value.componentData[index]
  const pv = comp?.propValue
  if (!pv || !pv.content) { ElMessage.warning(t('dashboard.download_no_data')); return }
  let md = `# ${pv.title || ''}\n\n`
  if (pv.question) md += `> ${pv.question}\n\n`
  md += pv.content
  if (pv.sources?.length) {
    md += '\n\n---\n\n## ' + t('dashboard.sources') + '\n\n'
    pv.sources.forEach((src: any) => {
      md += `- ${src.source_name || src.filename || 'PDF'}`
      if (src.page_number) md += ` P${src.page_number}`
      if (src.section_title) md += ` ${src.section_title}`
      md += '\n'
    })
  }
  triggerDownload(new Blob([md], { type: 'text/markdown; charset=utf-8' }), `${pv.title || 'report'}.md`)
}



function triggerDownload(blob: Blob, filename: string) {
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(link.href)
}

// Auto arrange
const autoArrange = async () => {
  pushHistory()
  const cols = 2, w = 600, h = 400, gap = 20
  canvasData.value.componentData.forEach((comp: any, i: number) => {
    comp.style = { ...comp.style, left: (i % cols) * (w + gap) + gap, top: Math.floor(i / cols) * (h + gap) + gap, width: w, height: h }
  })
  await autoSave()
}

onMounted(() => { loadDashboard() })

onBeforeUnmount(() => {
  // 组件卸载时清理拖拽/缩放的全局事件监听器，防止内存泄漏
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
})
</script>

<template>
  <div class="canvas-page-modern" :class="{ embedded: isEmbedded }">
    <div v-if="!isEmbedded" class="canvas-toolbar">
      <div class="toolbar-left">
        <el-button text class="back-btn" @click="goBack">
          <template #icon><Icon name="icon_arrow_left"><icon_arrow_left_outlined class="svg-icon" /></Icon></template>
          {{ t('dashboard.back') }}
        </el-button>
        <div class="divider"></div>
        <input class="dashboard-name" v-model="dashboardName" :placeholder="t('dashboard.new_dashboard')" maxlength="64" />
        <div class="divider"></div>
        <div class="history-controls">
          <el-tooltip :content="t('dashboard.undo')" placement="bottom">
            <div class="history-btn" :class="{ disabled: !canUndo }" @click="undo">
              <Icon name="undo"><icon_undo_outlined class="svg-icon" /></Icon>
            </div>
          </el-tooltip>
          <el-tooltip :content="t('dashboard.reduction')" placement="bottom">
            <div class="history-btn" :class="{ disabled: !canRedo }" @click="redo">
              <Icon name="redo"><icon_redo_outlined class="svg-icon" /></Icon>
            </div>
          </el-tooltip>
        </div>
      </div>
      <div class="toolbar-center">
        <div class="component-buttons">
          <div class="component-btn" @click="autoArrange">
            <svg viewBox="0 0 16 16" fill="currentColor" width="16" height="16"><rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>
            <span class="btn-text">{{ t('dashboard.auto_arrange') }}</span>
          </div>
        </div>
      </div>
      <div class="toolbar-right">
        <el-button class="preview-btn" :disabled="!dashboardId" @click="previewDashboard">{{ t('dashboard.preview') }}</el-button>

        <el-button type="primary" @click="saveDashboard">{{ t('dashboard.save') }}</el-button>
      </div>
    </div>

    <div v-loading="loading" class="canvas-area" @mousedown="deselectAll">
      <div class="canvas-container" :class="{ 'canvas-empty': canvasData.componentData.length === 0 }" :style="canvasData.componentData.length === 0 ? { background: canvasData.canvasStyleData.background } : { width: canvasData.canvasStyleData.width + 'px', height: canvasData.canvasStyleData.height + 'px', background: canvasData.canvasStyleData.background }">
        <div v-for="(component, index) in canvasData.componentData" :key="component.id" class="canvas-component" :class="{ selected: selectedComponentIndex === index, dragging: dragging && dragIndex === index }" :style="{ left: component.style.left + 'px', top: component.style.top + 'px', width: component.style.width + 'px', height: component.style.height + 'px' }" @mousedown.stop="selectComponent(index)">
          <div class="component-header" @mousedown="onDragStart($event, index)">
            <span class="component-title">{{ component.propValue?.title || t('dashboard.chart') }}</span>
            <div class="component-actions">
              <el-dropdown trigger="click" popper-class="download-dropdown-popper" @command="(cmd: string) => handleDownload(cmd, index)">
                <el-button text size="small" class="download-btn" @click.stop>
                  <Icon name="icon_export"><icon_export_outlined class="svg-icon" /></Icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      v-for="opt in getDownloadOptions(index)"
                      :key="opt.key"
                      :command="`${opt.key}:${index}`"
                    >{{ opt.icon }} {{ opt.label }}</el-dropdown-item>
                    <el-dropdown-item v-if="getDownloadOptions(index).length === 0" disabled>
                      {{ t('dashboard.download_no_data') }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-button text size="small" class="delete-btn" @click.stop="removeComponent(index)">{{ t('common.delete') }}</el-button>
            </div>
          </div>
          <div class="component-body">
            <InsightCard
              v-if="component.propValue?.cardType && component.propValue.cardType !== 'chart'"
              :id="component.id"
              :card-type="component.propValue.cardType"
              :prop-value="component.propValue"
            />
            <ChartComponent v-else-if="component.propValue" :id="component.id" :type="component.propValue.chartType" :data="component.propValue.data" :columns="component.propValue.columns || []" :x="component.propValue.xAxis || []" :y="component.propValue.yAxis || []" :series="component.propValue.series || []" />
          </div>
          <div v-if="selectedComponentIndex === index" class="resize-handle" @mousedown="onResizeStart($event, index)"></div>
        </div>

        <div v-if="canvasData.componentData.length === 0" class="canvas-placeholder">
          <div class="placeholder-icon">
            <svg viewBox="0 0 64 64" fill="none"><rect x="8" y="8" width="48" height="48" rx="4" stroke="currentColor" stroke-width="2"/><path d="M8 20h48M20 8v48" stroke="currentColor" stroke-width="2"/></svg>
          </div>
          <p class="placeholder-text">{{ t('dashboard.no_charts_yet') }}</p>
          <p class="placeholder-hint">{{ t('dashboard.no_charts_hint') }}</p>
          <div class="placeholder-steps">
            <div class="step-item">
              <span class="step-num">1</span>
              <span class="step-text">{{ t('dashboard.how_to_add_step1') }}</span>
            </div>
            <div class="step-item">
              <span class="step-num">2</span>
              <span class="step-text">{{ t('dashboard.how_to_add_step2') }}</span>
            </div>
            <div class="step-item">
              <span class="step-num">3</span>
              <span class="step-text">{{ t('dashboard.how_to_add_step3') }}</span>
            </div>
          </div>
          <el-button type="primary" class="placeholder-btn" @click="router.push('/chat')">
            {{ t('dashboard.go_to_chat') }}
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="less" scoped>
@primary: #8b5cf6;

.canvas-page-modern {
  width: 100%; height: 100vh; display: flex; flex-direction: column; background: #0f0a1a;

  &.embedded {
    .canvas-area { padding: 20px; height: 100vh; }
    .canvas-container { margin: 0; border-radius: 0; border: none; box-shadow: none; width: 100% !important; height: 100% !important; }
  }

  .canvas-toolbar {
    height: 64px; display: flex; align-items: center; justify-content: space-between; padding: 0 20px;
    background: linear-gradient(145deg, rgba(30,18,69,0.85) 0%, rgba(26,16,51,0.85) 100%);
    border-bottom: 1px solid rgba(139,92,246,0.18); backdrop-filter: blur(12px);

    .toolbar-left {
      display: flex; align-items: center; gap: 12px; flex: 1;
      .back-btn { color: #cbd5e1; font-weight: 500; font-size: 14px; padding: 8px 12px; &:hover { color: #a78bfa; } }
      .divider { width: 1px; height: 24px; background: rgba(139,92,246,0.25); }
      .dashboard-name { font-size: 15px; font-weight: 600; color: #e2e8f0; margin: 0; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 2px 8px; outline: none; cursor: text;
        &:hover { border-color: rgba(139,92,246,0.25); }
        &:focus { border-color: rgba(139,92,246,0.5); background: rgba(139,92,246,0.08); }
      }
      .history-controls {
        display: flex; gap: 6px;
        .history-btn {
          width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
          border-radius: 6px; background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.15);
          color: #a78bfa; cursor: pointer; transition: all 0.2s;
          &:hover:not(.disabled) { background: rgba(139,92,246,0.15); transform: scale(1.05); }
          &.disabled { opacity: 0.35; cursor: not-allowed; }
        }
      }
    }

    .toolbar-center {
      display: flex; justify-content: center; flex: 1;
      .component-buttons {
        display: flex; gap: 8px; padding: 4px; background: rgba(139,92,246,0.06); border: 1px solid rgba(139,92,246,0.12); border-radius: 10px;
        .component-btn {
          display: flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 7px;
          background: transparent; border: 1px solid transparent; color: #cbd5e1; cursor: pointer; transition: all 0.2s;
          .btn-text { font-size: 13px; font-weight: 500; white-space: nowrap; }
          &:hover { background: rgba(139,92,246,0.12); border-color: rgba(139,92,246,0.2); color: #e9d5ff; }
          &.primary { background: rgba(139,92,246,0.18); border-color: rgba(139,92,246,0.25); color: #e9d5ff; }
        }
      }
    }

    .toolbar-right {
      display: flex; gap: 10px; flex: 1; justify-content: flex-end;
      .preview-btn { background: rgba(139,92,246,0.08); border-color: rgba(139,92,246,0.18); color: #cbd5e1; height: 36px; font-size: 14px; font-weight: 500; &:hover { background: rgba(139,92,246,0.12); color: #e9d5ff; } }
      :deep(.ed-button--primary) { height: 36px; padding: 0 20px; font-size: 14px; font-weight: 600; background: linear-gradient(135deg, @primary 0%, #7c3aed 100%); border: none; box-shadow: 0 2px 8px rgba(139,92,246,0.3); &:hover { box-shadow: 0 4px 12px rgba(139,92,246,0.4); transform: translateY(-1px); } }
    }
  }

  .canvas-area {
    flex: 1; overflow: auto; padding: 28px; background: #0f0a1a;
    &::-webkit-scrollbar { width: 8px; height: 8px; }
    &::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.3); border-radius: 4px; }

    .canvas-container {
      margin: 0 auto; position: relative;
      box-shadow: 0 12px 40px rgba(0,0,0,0.35); border: 1px solid rgba(139,92,246,0.2); border-radius: 10px; overflow: hidden;

      &.canvas-empty {
        width: 100%; height: calc(100vh - 120px);
      }

      .canvas-component {
        position: absolute;
        background: linear-gradient(145deg, rgba(30,18,69,0.8) 0%, rgba(26,16,51,0.8) 100%);
        border: 2px solid transparent; border-radius: 12px; overflow: visible;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3); transition: border-color 0.15s, box-shadow 0.15s;
        &.selected { border-color: @primary; box-shadow: 0 0 0 1px @primary, 0 8px 24px rgba(139,92,246,0.25); }
        &.dragging { opacity: 0.85; cursor: grabbing; z-index: 100; }

        .component-header {
          display: flex; align-items: center; justify-content: space-between; padding: 10px 14px;
          background: rgba(139,92,246,0.1); border-bottom: 1px solid rgba(139,92,246,0.2);
          cursor: grab; user-select: none;
          .component-title { font-size: 14px; font-weight: 600; color: #e2e8f0; pointer-events: none; }
          .delete-btn { color: #f87171; font-size: 12px; &:hover { color: #ef4444; } }
          .download-btn { color: #a78bfa; font-size: 12px; padding: 2px 4px; cursor: pointer; &:hover { color: #c4b5fd; } }
        }

        .component-body { padding: 12px; height: calc(100% - 45px); overflow: auto; }

        .resize-handle {
          position: absolute; right: -5px; bottom: -5px; width: 14px; height: 14px;
          background: @primary; border: 2px solid #1a0f2e; border-radius: 3px;
          cursor: nwse-resize; z-index: 10; &:hover { transform: scale(1.3); }
        }
      }

      .canvas-placeholder {
        width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px 40px;
        .placeholder-icon { width: 120px; height: 120px; margin-bottom: 24px; color: rgba(139,92,246,0.4); svg { width: 100%; height: 100%; } }
        .placeholder-text { font-size: 18px; font-weight: 600; color: #cbd5e1; margin: 0 0 8px; }
        .placeholder-hint { font-size: 14px; color: #64748b; margin: 0 0 24px; max-width: 400px; text-align: center; }
        .placeholder-steps {
          display: flex; flex-direction: column; gap: 10px; margin-bottom: 24px;
          .step-item {
            display: flex; align-items: center; gap: 10px;
            .step-num {
              width: 24px; height: 24px; border-radius: 50%; background: rgba(139,92,246,0.2);
              color: #a78bfa; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
            }
            .step-text { font-size: 13px; color: #94a3b8; }
          }
        }
        .placeholder-btn {
          background: linear-gradient(135deg, @primary 0%, #7c3aed 100%); border: none;
          padding: 10px 28px; font-size: 14px; font-weight: 600; border-radius: 8px;
          box-shadow: 0 2px 8px rgba(139,92,246,0.3);
          &:hover { box-shadow: 0 4px 12px rgba(139,92,246,0.4); transform: translateY(-1px); }
        }
      }
    }
  }
}
</style>

<style lang="less">
.download-dropdown-popper {
  background: #1a1033 !important;
  border: 1px solid rgba(139, 92, 246, 0.25) !important;
  border-radius: 10px !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5) !important;
  padding: 6px !important;

  .ed-dropdown-menu,
  .el-dropdown-menu {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
  }

  .ed-dropdown-menu__item,
  .el-dropdown-menu__item {
    color: #cbd5e1 !important;
    font-size: 13px;
    padding: 8px 14px;
    border-radius: 7px;
    margin-bottom: 2px;

    &:hover, &:focus {
      background: rgba(139, 92, 246, 0.15) !important;
      color: #e9d5ff !important;
    }

    &.is-disabled {
      color: rgba(148, 163, 184, 0.4) !important;
    }
  }

  .ed-popper__arrow::before,
  .el-popper__arrow::before {
    background: #1a1033 !important;
    border-color: rgba(139, 92, 246, 0.25) !important;
  }
}
</style>
