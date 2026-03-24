<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus-secondary'
import { dashboardApi } from '@/api/dashboard'
import icon_dashboard from '@/assets/permission/icon_dashboard.svg'
import icon_add_outlined from '@/assets/svg/icon_add_outlined.svg'
import { Icon } from '@/components/icon-custom'

const { t } = useI18n()

const dialogVisible = ref(false)
const dashboardList = ref<any[]>([])
const selectedDashboard = ref<any>(null)
const newDashboardName = ref('')
const createMode = ref(false)
const chartData = ref<any>(null)
const loading = ref(false)

const loadDashboards = async () => {
  try {
    const res = await dashboardApi.list_resource({ node_type: 'leaf' })
    const data = Array.isArray(res) ? res : (res?.data ? (Array.isArray(res.data) ? res.data : []) : [])
    dashboardList.value = flattenTree(data)
    // 没有已有仪表板时自动进入新建模式
    if (dashboardList.value.length === 0) {
      createMode.value = true
    }
  } catch {
    dashboardList.value = []
    createMode.value = true
  }
}

const flattenTree = (tree: any[]): any[] => {
  const result: any[] = []
  const traverse = (nodes: any[]) => {
    nodes.forEach((node) => {
      if (node.node_type === 'leaf') result.push(node)
      if (node.children?.length) traverse(node.children)
    })
  }
  traverse(tree)
  return result
}

const open = (data: any) => {
  chartData.value = data
  dialogVisible.value = true
  createMode.value = false
  selectedDashboard.value = null
  newDashboardName.value = ''
  loadDashboards()
}

const toggleCreateMode = () => {
  createMode.value = !createMode.value
  if (createMode.value) selectedDashboard.value = null
  else newDashboardName.value = ''
}

const selectDashboard = (dashboard: any) => {
  selectedDashboard.value = dashboard
  createMode.value = false
}

const confirm = async () => {
  if (createMode.value) {
    if (!newDashboardName.value.trim()) {
      ElMessage.warning(t('dashboard.add_dashboard_name_tips'))
      return
    }
    await createAndAddChart()
  } else {
    if (!selectedDashboard.value) {
      ElMessage.warning(t('dashboard.please_select_dashboard'))
      return
    }
    await addChartToExisting()
  }
}

const createAndAddChart = async () => {
  loading.value = true
  try {
    await dashboardApi.create_resource({
      name: newDashboardName.value, pid: 'root', node_type: 'leaf', type: 'dashboard', opt: 'newLeaf',
      workspace_id: '', org_id: '', level: 0, create_by: 0,
      canvas_style_data: JSON.stringify({ width: 1920, height: 1080, scale: 100, color: '#0f0a1a', opacity: 1, background: '#0f0a1a' }),
      component_data: JSON.stringify([chartData.value]),
      canvas_view_info: JSON.stringify({}), description: '',
    })
    ElMessage.success(t('dashboard.add_chart_success'))
    dialogVisible.value = false
  } catch { ElMessage.error(t('dashboard.add_chart_failed')) }
  finally { loading.value = false }
}

const addChartToExisting = async () => {
  loading.value = true
  try {
    const dashboard = await dashboardApi.load_resource({ id: selectedDashboard.value.id })
    let componentData = []
    try { componentData = JSON.parse(dashboard.component_data || '[]') } catch { componentData = [] }

    // 去重检查
    if (chartData.value.propValue?.recordId) {
      const targetCardType = chartData.value.propValue.cardType
      const targetHasChart = !!chartData.value.propValue.chartType
      const exists = componentData.some(
        (c: any) => c.propValue?.recordId === chartData.value.propValue.recordId
          && c.propValue?.cardType === targetCardType
          && !!c.propValue?.chartType === targetHasChart
      )
      if (exists) {
        ElMessage.warning(t('dashboard.chart_already_exists'))
        loading.value = false
        return
      }
    }
    const colCount = 2
    const idx = componentData.length
    const col = idx % colCount
    const row = Math.floor(idx / colCount)
    const positioned = {
      ...chartData.value,
      style: {
        ...(chartData.value.style || {}),
        left: col * 620 + 20, top: row * 440 + 20,
        width: chartData.value.style?.width || 600, height: chartData.value.style?.height || 400, rotate: 0,
      },
    }
    componentData.push(positioned)

    await dashboardApi.update_canvas({
      id: selectedDashboard.value.id, name: selectedDashboard.value.name,
      component_data: JSON.stringify(componentData),
      canvas_style_data: dashboard.canvas_style_data || JSON.stringify({ width: 1920, height: 1080, scale: 100, color: '#0f0a1a', opacity: 1, background: '#0f0a1a' }),
      canvas_view_info: dashboard.canvas_view_info || JSON.stringify({}),
      opt: 'updateLeaf', pid: 'root', node_type: 'leaf', type: 'dashboard',
      workspace_id: '', org_id: '', level: 0, create_by: 0, description: '',
    })
    ElMessage.success(t('dashboard.add_chart_success'))
    dialogVisible.value = false
  } catch { ElMessage.error(t('dashboard.add_chart_failed')) }
  finally { loading.value = false }
}

defineExpose({ open })
</script>

<template>
  <el-dialog v-model="dialogVisible" :title="t('dashboard.add_to_dashboard')" width="480px" class="add-chart-dialog">
    <div v-loading="loading" class="dialog-content">
      <!-- 新建仪表板 -->
      <div class="create-section">
        <el-button class="create-btn" :type="createMode ? 'primary' : 'default'" @click="toggleCreateMode">
          <template #icon><Icon name="icon_add_outlined"><icon_add_outlined class="svg-icon" /></Icon></template>
          {{ t('dashboard.create_new_dashboard') }}
        </el-button>
        <el-input v-if="createMode" v-model="newDashboardName" :placeholder="t('dashboard.add_dashboard_name_tips')" size="large" class="create-input" maxlength="64" show-word-limit />
      </div>

      <!-- 选择已有仪表板 -->
      <div v-if="!createMode" class="dashboard-list">
        <div class="list-header">
          <span class="header-title">{{ t('dashboard.select_existing_dashboard') }}</span>
          <span class="header-count">{{ dashboardList.length }}</span>
        </div>

        <div v-if="dashboardList.length === 0" class="empty-list">
          <span class="empty-text">{{ t('dashboard.no_dashboard') }}</span>
        </div>

        <div v-else class="dashboard-items">
          <div v-for="item in dashboardList" :key="item.id" class="dashboard-item" :class="{ selected: selectedDashboard?.id === item.id }" @click="selectDashboard(item)">
            <div class="item-icon">
              <Icon name="icon_dashboard"><icon_dashboard class="svg-icon" /></Icon>
            </div>
            <div class="item-content">
              <span class="item-name">{{ item.name }}</span>
              <span class="item-time">{{ item.create_time ? new Date(item.create_time * 1000).toLocaleDateString() : '' }}</span>
            </div>
            <div v-if="selectedDashboard?.id === item.id" class="item-check">
              <svg viewBox="0 0 16 16" fill="currentColor"><path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z"/></svg>
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" @click="confirm">{{ t('common.confirm') }}</el-button>
    </template>
  </el-dialog>
</template>

<style lang="less" scoped>
.dialog-content {
  .create-section {
    margin-bottom: 20px;
    .create-btn {
      width: 100%; height: 44px; font-size: 14px; font-weight: 600; border-radius: 8px; margin-bottom: 12px;
      &:not(.ed-button--primary) { background: rgba(139,92,246,0.08); border-color: rgba(139,92,246,0.15); color: #cbd5e1;
        &:hover { background: rgba(139,92,246,0.12); border-color: rgba(139,92,246,0.25); }
      }
      &.ed-button--primary { background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%); border: none; box-shadow: 0 2px 8px rgba(139,92,246,0.3); }
    }
    .create-input {
      :deep(.ed-input__wrapper) { background: rgba(139,92,246,0.08); border: 1.5px solid rgba(139,92,246,0.2); border-radius: 8px;
        &:hover { border-color: rgba(139,92,246,0.35); }
        &.is-focus { border-color: #8b5cf6; box-shadow: 0 0 0 3px rgba(139,92,246,0.15); }
      }
      :deep(.ed-input__inner) { color: #e2e8f0; &::placeholder { color: #64748b; } }
    }
  }

  .dashboard-list {
    .list-header {
      display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; padding-bottom: 10px;
      border-bottom: 1px solid rgba(139,92,246,0.15);
      .header-title { font-size: 13px; font-weight: 600; color: #cbd5e1; }
      .header-count { font-size: 12px; color: #8b5cf6; background: rgba(139,92,246,0.15); padding: 2px 8px; border-radius: 6px; }
    }
    .empty-list {
      text-align: center; padding: 20px 16px; color: #64748b;
      .empty-text { font-size: 13px; }
    }
    .dashboard-items {
      max-height: 240px; overflow-y: auto;
      &::-webkit-scrollbar { width: 5px; }
      &::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.3); border-radius: 3px; }
      .dashboard-item {
        display: flex; align-items: center; gap: 10px; padding: 10px; border-radius: 8px;
        border: 1.5px solid transparent; cursor: pointer; transition: all 0.15s; margin-bottom: 6px;
        &:hover { background: rgba(139,92,246,0.08); border-color: rgba(139,92,246,0.2); }
        &.selected { background: rgba(139,92,246,0.15); border-color: rgba(139,92,246,0.4); }
        .item-icon {
          width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;
          background: rgba(139,92,246,0.15); border-radius: 8px; color: #a78bfa; font-size: 18px; flex-shrink: 0;
        }
        .item-content {
          flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0;
          .item-name { font-size: 13px; font-weight: 500; color: #e2e8f0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
          .item-time { font-size: 11px; color: #64748b; }
        }
        .item-check { width: 18px; height: 18px; color: #8b5cf6; flex-shrink: 0; svg { width: 100%; height: 100%; } }
      }
    }
  }
}
</style>

<style lang="less">
.add-chart-dialog {
  .ed-dialog__header {
    background: #1a1033; border-bottom: 1px solid rgba(139,92,246,0.2);
    .ed-dialog__title { font-size: 16px; font-weight: 600; color: #e2e8f0; }
  }
  .ed-dialog__body { background: #1a1033; padding: 20px; }
  .ed-dialog__footer {
    background: #1a1033; border-top: 1px solid rgba(139,92,246,0.2); padding: 14px 20px;
    .ed-button {
      height: 36px; padding: 0 18px; font-size: 13px; font-weight: 500; border-radius: 8px;
      &:not(.ed-button--primary) { background: rgba(139,92,246,0.08); border-color: rgba(139,92,246,0.15); color: #cbd5e1;
        &:hover { background: rgba(139,92,246,0.12); border-color: rgba(139,92,246,0.25); }
      }
      &.ed-button--primary { background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%); border: none; box-shadow: 0 2px 8px rgba(139,92,246,0.3); }
    }
  }
}
</style>
