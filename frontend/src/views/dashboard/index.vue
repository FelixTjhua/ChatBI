<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { dashboardApi } from '@/api/dashboard'
import { ElMessage, ElMessageBox } from 'element-plus-secondary'
import { getDsIcon, dsTypeWithImg } from '@/views/ds/js/ds-type'

const { t } = useI18n()
const router = useRouter()

const downloadLoading = ref<string | null>(null)
const myDashboards = ref<any[]>([])
const dashboardsLoading = ref(false)

const loadMyDashboards = async () => {
  dashboardsLoading.value = true
  try {
    const res = await dashboardApi.list_resource({ node_type: 'leaf' })
    const flat: any[] = []
    const traverse = (nodes: any[]) => {
      if (!nodes || !Array.isArray(nodes)) return
      nodes.forEach((n: any) => {
        if (n.node_type === 'leaf') flat.push(n)
        if (n.children?.length) traverse(n.children)
      })
    }
    const data = Array.isArray(res) ? res : (res?.data ? (Array.isArray(res.data) ? res.data : []) : [])
    traverse(data)
    myDashboards.value = flat
  } catch (e) {
    console.warn('Load dashboards failed:', e)
    myDashboards.value = []
  } finally {
    dashboardsLoading.value = false
  }
}

const openDashboard = (id: string) => {
  router.push({ path: '/canvas', query: { resourceId: id } })
}

const createNewDashboard = () => {
  router.push({ path: '/canvas' })
}

const deleteDashboard = async (id: string, name: string) => {
  try {
    await ElMessageBox.confirm(
      t('dashboard.confirm_delete', { name }),
      t('common.warning'),
      { confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel'), type: 'warning', showClose: false }
    )
    await dashboardApi.delete_resource({ id })
    ElMessage.success(t('common.delete_success'))
    loadMyDashboards()
  } catch { /* cancelled */ }
}

const downloadDashboard = async (id: string, name: string) => {
  downloadLoading.value = id
  try {
    const res = await dashboardApi.export_excel(id) as any
    const blob = new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${name || 'dashboard'}.xlsx`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(link.href)
    ElMessage.success(t('dashboard.download_success'))
  } catch {
    ElMessage.error(t('dashboard.download_no_data'))
  } finally {
    downloadLoading.value = null
  }
}

const getCardCount = (dashboard: any) => {
  try { return JSON.parse(dashboard.component_data || '[]').length } catch { return 0 }
}

/** 获取仪表板中所有卡片的数据源类型（去重） */
const getDsTypes = (dashboard: any): string[] => {
  try {
    const data = JSON.parse(dashboard.component_data || '[]')
    const types = new Set<string>()
    data.forEach((c: any) => {
      const dt = c.propValue?.dsType
      if (dt) types.add(dt)
    })
    return Array.from(types)
  } catch { return [] }
}

/** 获取数据源类型的 SVG 图标 URL（复用数据源模块的图标） */
const getDsTypeIcon = (dt: string): string => {
  return getDsIcon(dt) || ''
}

/** 获取数据源类型的显示名称 */
const dsTypeLabel = (dt: string): string => {
  const found = dsTypeWithImg.find((e) => e.type === dt)
  return found?.name || dt.toUpperCase()
}

const formatTimestamp = (ts: any) => {
  if (!ts) return ''
  const num = typeof ts === 'number' ? ts : parseInt(ts)
  if (isNaN(num) || num <= 0) return ''
  return new Date(num * 1000).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

onMounted(() => { loadMyDashboards() })
</script>

<template>
  <div class="dashboard-page">
    <div class="dashboard-content" v-loading="dashboardsLoading">
      <div class="page-header">
        <div class="header-left">
          <div class="chatbi-page-title">
            <span class="title-text">{{ t('dashboard.dashboard') }}</span>
          </div>
          <p class="page-subtitle">{{ t('dashboard.dashboard_desc') }}</p>
        </div>
        <el-button v-if="myDashboards.length > 0" type="primary" class="create-btn" @click="createNewDashboard">
          + {{ t('dashboard.new_dashboard') }}
        </el-button>
      </div>

      <!-- 空状态 -->
      <div v-if="!dashboardsLoading && myDashboards.length === 0" class="empty-state">
        <div class="empty-visual">
          <svg viewBox="0 0 120 120" fill="none" width="120" height="120">
            <rect x="10" y="10" width="100" height="100" rx="12" stroke="rgba(139,92,246,0.3)" stroke-width="2" stroke-dasharray="6 4"/>
            <rect x="20" y="25" width="35" height="25" rx="4" fill="rgba(139,92,246,0.15)" stroke="rgba(139,92,246,0.3)" stroke-width="1.5"/>
            <rect x="65" y="25" width="35" height="25" rx="4" fill="rgba(59,130,246,0.15)" stroke="rgba(59,130,246,0.3)" stroke-width="1.5"/>
            <rect x="20" y="60" width="35" height="25" rx="4" fill="rgba(16,185,129,0.15)" stroke="rgba(16,185,129,0.3)" stroke-width="1.5"/>
            <rect x="65" y="60" width="35" height="25" rx="4" fill="rgba(245,158,11,0.15)" stroke="rgba(245,158,11,0.3)" stroke-width="1.5"/>
            <line x1="25" y1="42" x2="50" y2="32" stroke="#8b5cf6" stroke-width="1.5" stroke-linecap="round"/>
            <line x1="30" y1="44" x2="45" y2="35" stroke="#8b5cf6" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="72" cy="37" r="8" fill="none" stroke="#3b82f6" stroke-width="1.5"/>
            <line cx="72" cy="37" x1="72" y1="37" x2="78" y2="33" stroke="#3b82f6" stroke-width="1.5"/>
            <line cx="72" cy="37" x1="72" y1="37" x2="72" y2="31" stroke="#3b82f6" stroke-width="1.5"/>
            <rect x="25" y="66" width="6" height="14" rx="1" fill="rgba(16,185,129,0.5)"/>
            <rect x="33" y="70" width="6" height="10" rx="1" fill="rgba(16,185,129,0.4)"/>
            <rect x="41" y="63" width="6" height="17" rx="1" fill="rgba(16,185,129,0.6)"/>
            <line x1="70" y1="78" x2="95" y2="65" stroke="#f59e0b" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="3 2"/>
            <line x1="70" y1="75" x2="95" y2="68" stroke="#f59e0b" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>
        <h3 class="empty-title">{{ t('dashboard.empty_guide') }}</h3>
        <p class="empty-desc">{{ t('dashboard.empty_guide_desc') }}</p>
        <div class="empty-steps">
          <div class="step"><span class="step-num">1</span><span>{{ t('dashboard.guide_step1') }}</span></div>
          <div class="step"><span class="step-num">2</span><span>{{ t('dashboard.guide_step2') }}</span></div>
          <div class="step"><span class="step-num">3</span><span>{{ t('dashboard.guide_step3') }}</span></div>
        </div>
        <el-button type="primary" class="empty-btn" @click="router.push('/chat')">{{ t('dashboard.go_to_chat') }}</el-button>
      </div>

      <!-- 仪表板网格 -->
      <div v-else-if="myDashboards.length > 0" class="dashboards-grid">
        <div v-for="db in myDashboards" :key="db.id" class="db-card" @click="openDashboard(db.id)">
          <div class="db-card__top">
            <span class="db-card__name">{{ db.name }}</span>
            <div class="db-card__actions">
              <el-button text size="small" class="db-card__del" @click.stop="deleteDashboard(db.id, db.name)">✕</el-button>
            </div>
          </div>
          <!-- 数据源类型预览 -->
          <div class="db-card__preview">
            <div v-if="getDsTypes(db).length > 0" class="db-card__ds-tags">
              <span v-for="dt in getDsTypes(db)" :key="dt" class="ds-tag">
                <img v-if="getDsTypeIcon(dt)" :src="getDsTypeIcon(dt)" class="ds-icon" />
                <span class="ds-label">{{ dsTypeLabel(dt) }}</span>
              </span>
            </div>
            <span v-else-if="getCardCount(db) === 0" class="db-card__empty-hint">{{ t('dashboard.no_charts_yet') }}</span>
          </div>
          <div class="db-card__bottom">
            <span class="db-card__count">{{ getCardCount(db) }} {{ t('dashboard.cards') }}</span>
            <span class="db-card__time">{{ formatTimestamp(db.update_time || db.create_time) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="less" scoped>
@primary: #8b5cf6;
@primary-border: rgba(139, 92, 246, 0.2);
@bg-dark: #0f0a1a;
@bg-card: rgba(26, 18, 37, 0.85);
@text-primary: #f1f5f9;
@text-secondary: #cbd5e1;
@text-muted: #94a3b8;

.dashboard-page {
  width: 100%; height: 100vh;
  background: linear-gradient(135deg, @bg-dark 0%, #1a0f2e 50%, @bg-dark 100%);
  overflow: hidden;
}

.dashboard-content {
  height: 100%; overflow-y: auto; padding: 32px;
  &::-webkit-scrollbar { width: 8px; }
  &::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.25); border-radius: 4px; }
}

.page-header {
  display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 28px;
  .header-left { flex: 1; }
  .page-subtitle { font-size: 14px; color: @text-secondary; margin: 6px 0 0; }
  .create-btn {
    flex-shrink: 0; margin-left: 16px; height: 38px; padding: 0 20px; font-size: 14px; font-weight: 600;
    background: linear-gradient(135deg, @primary 0%, #7c3aed 100%); border: none;
    box-shadow: 0 2px 8px rgba(139,92,246,0.3); border-radius: 8px;
    &:hover { box-shadow: 0 4px 12px rgba(139,92,246,0.4); transform: translateY(-1px); }
  }
}

// 空状态
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 60px 20px; min-height: 60vh;
  .empty-visual { margin-bottom: 28px; opacity: 0.9; }
  .empty-title { font-size: 20px; font-weight: 600; color: @text-primary; margin: 0 0 8px; }
  .empty-desc { font-size: 14px; color: @text-muted; margin: 0 0 28px; max-width: 420px; text-align: center; line-height: 1.6; }
  .empty-steps {
    display: flex; flex-direction: column; gap: 12px; margin-bottom: 28px;
    .step {
      display: flex; align-items: center; gap: 10px; font-size: 13px; color: @text-secondary;
      .step-num {
        width: 24px; height: 24px; border-radius: 50%; background: rgba(139,92,246,0.2);
        color: #a78bfa; font-size: 12px; font-weight: 700;
        display: flex; align-items: center; justify-content: center; flex-shrink: 0;
      }
    }
  }
  .empty-btn {
    height: 42px; padding: 0 32px; font-size: 15px; font-weight: 600; border-radius: 10px;
    background: linear-gradient(135deg, @primary 0%, #7c3aed 100%); border: none;
    box-shadow: 0 2px 12px rgba(139,92,246,0.35);
    &:hover { box-shadow: 0 6px 20px rgba(139,92,246,0.45); transform: translateY(-2px); }
  }
}

// 仪表板网格
.dashboards-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 18px;
}

.db-card {
  background: linear-gradient(145deg, @bg-card 0%, rgba(20,14,32,0.9) 100%);
  border: 1.5px solid @primary-border; border-radius: 14px; padding: 18px;
  cursor: pointer; transition: all 0.2s;
  &:hover { border-color: rgba(139,92,246,0.4); transform: translateY(-3px); box-shadow: 0 8px 28px rgba(139,92,246,0.15); }

  &__top {
    display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;
  }
  &__name {
    font-size: 16px; font-weight: 600; color: @text-primary;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;
  }
  &__actions { display: flex; align-items: center; gap: 2px; flex-shrink: 0; }
  &__dl { color: #a78bfa; font-size: 13px; padding: 2px 6px; &:hover { color: #c4b5fd; } }
  &__del { color: @text-muted; font-size: 14px; padding: 2px 6px; &:hover { color: #f87171; } }

  &__preview {
    display: flex; flex-direction: column; gap: 4px; min-height: 28px; margin-bottom: 14px;
  }
  &__ds-tags {
    display: flex; flex-wrap: wrap; gap: 8px;
    .ds-tag {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 4px 10px; border-radius: 6px;
      background: rgba(139,92,246,0.1); border: 1px solid rgba(139,92,246,0.15);
      font-size: 12px; color: #c4b5fd;
      .ds-icon { width: 18px; height: 18px; object-fit: contain; flex-shrink: 0; }
      .ds-label { font-size: 12px; }
    }
  }
  &__empty-hint { font-size: 12px; color: rgba(148,163,184,0.5); font-style: italic; }

  &__bottom {
    display: flex; align-items: center; justify-content: space-between;
    padding-top: 12px; border-top: 1px solid rgba(139,92,246,0.1);
  }
  &__count { font-size: 12px; color: @text-muted; }
  &__time { font-size: 11px; color: rgba(148,163,184,0.6); }
}
</style>
