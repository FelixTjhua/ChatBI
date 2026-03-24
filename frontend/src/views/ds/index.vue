<template>
  <div v-loading="loading" class="ds-page">
    <!-- 页面头部区域 -->
    <div class="page-header-section">
      <div class="header-content">
        <div class="title-area">
          <div class="chatbi-page-title">
            <span class="title-text">{{ t('menu.Data Connections') }}</span>
          </div>
          <p class="page-subtitle">{{ t('ds.page_description') }}</p>
        </div>
        <el-button class="add-btn-primary" type="primary" :icon="IconOpeAdd" @click="editDs(undefined)">
          {{ t('ds.add') }}
        </el-button>
      </div>
    </div>

    <!-- 搜索和筛选栏 -->
    <div class="toolbar-section">
      <div class="search-container">
        <el-icon class="search-icon"><Search /></el-icon>
        <el-input
          v-model="searchValue"
          :placeholder="t('ds.Search Datasource')"
          class="search-input"
          clearable
          @change="searchHandle"
        />
      </div>
      <div class="toolbar-right">
        <div v-if="dsList.length > 0" class="stats-badge">
          <span class="badge-count">{{ dsList.length }}</span>
          <span class="badge-label">{{ t('ds.datasources') }}</span>
        </div>
        <div class="view-toggle">
          <button
            class="toggle-btn"
            :class="{ active: viewMode === 'card' }"
            @click="viewMode = 'card'"
            :title="t('ds.card_view')"
          >
            <el-icon><Grid /></el-icon>
          </button>
          <button
            class="toggle-btn"
            :class="{ active: viewMode === 'list' }"
            @click="viewMode = 'list'"
            :title="t('ds.list_view')"
          >
            <el-icon><List /></el-icon>
          </button>
        </div>
      </div>
    </div>

    <!-- 数据源卡片视图 -->
    <div v-if="dsList.length > 0 && viewMode === 'card'" class="ds-grid">
      <template v-for="ds in dsList" :key="ds.id">
        <DatasourceItemCard :ds="ds">
          <div class="card-actions">
            <el-tooltip :content="t('ds.view_tables')" placement="top">
              <button class="action-btn view-btn" @click="getTables(ds.id, ds.name)">
                <el-icon><List /></el-icon>
              </button>
            </el-tooltip>
            <el-tooltip :content="t('common.edit')" placement="top">
              <button class="action-btn edit-btn" @click="editDs(ds)">
                <Icon><IconOpeEdit /></Icon>
              </button>
            </el-tooltip>
            <el-tooltip :content="t('common.delete')" placement="top">
              <button class="action-btn delete-btn" @click="deleteDs(ds)">
                <Icon><IconOpeDelete /></Icon>
              </button>
            </el-tooltip>
          </div>
        </DatasourceItemCard>
      </template>
    </div>

    <!-- 数据源列表视图 -->
    <div v-if="dsList.length > 0 && viewMode === 'list'" class="ds-list-view">
      <el-table :data="dsList" style="width: 100%">
        <el-table-column prop="name" :label="t('ds.form.name')" min-width="180">
          <template #default="{ row }">
            <span class="list-ds-name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="type_name" :label="t('ds.type')" width="140">
          <template #default="{ row }">
            <span class="list-ds-type">{{ row.type_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" :label="t('ds.form.description')" min-width="200">
          <template #default="{ row }">
            <span class="list-ds-desc">{{ row.description || t('ds.no_description') }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="num" :label="t('ds.tables')" width="120" align="center">
          <template #default="{ row }">
            <span class="list-ds-count">{{ row.num || 0 }}</span>
            <span class="list-ds-unit">{{ row.type === 'pdf' ? t('ds.doc_chunks') : t('ds.tables') }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('ds.actions')" width="180" align="center">
          <template #default="{ row }">
            <el-button text size="small" @click="getTables(row.id, row.name)">
              {{ t('ds.view_tables') }}
            </el-button>
            <el-button text size="small" @click="editDs(row)">
              {{ t('common.edit') }}
            </el-button>
            <el-button text size="small" type="danger" @click="deleteDs(row)">
              {{ t('common.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-illustration">
        <svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="100" cy="100" r="80" stroke="url(#gradient1)" stroke-width="2" opacity="0.3" />
          <circle cx="100" cy="100" r="60" stroke="url(#gradient1)" stroke-width="2" opacity="0.2" />
          <path d="M70 85h60M70 100h45M70 115h50" stroke="url(#gradient1)" stroke-width="3" stroke-linecap="round" opacity="0.5" />
          <circle cx="100" cy="100" r="25" stroke="url(#gradient1)" stroke-width="2.5" opacity="0.4" />
          <defs>
            <linearGradient id="gradient1" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style="stop-color:#8b5cf6;stop-opacity:1" />
              <stop offset="100%" style="stop-color:#a78bfa;stop-opacity:1" />
            </linearGradient>
          </defs>
        </svg>
      </div>
      <h3 class="empty-title">{{ t('ds.no_datasource') }}</h3>
      <p class="empty-description">{{ t('ds.empty_description') }}</p>
      <el-button class="empty-action-btn" type="primary" :icon="IconOpeAdd" @click="editDs(undefined)">
        {{ t('ds.add_first') }}
      </el-button>
    </div>
  </div>
  <DsForm ref="dsForm" @refresh="refresh" />
</template>

<script lang="ts" setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import IconOpeAdd from '@/assets/svg/operate/ope-add.svg'
import IconOpeEdit from '@/assets/svg/operate/ope-edit.svg'
import IconOpeDelete from '@/assets/svg/operate/ope-delete.svg'
import { Search, List, Grid } from '@element-plus/icons-vue'
import DsForm from './form.vue'
import { datasourceApi } from '@/api/datasource'
import { ElMessageBox, ElMessage } from 'element-plus-secondary'
import { useRouter } from 'vue-router'
import DatasourceItemCard from '@/views/ds/DatasourceItemCard.vue'
// Icon组件在模板中使用但未导入，导致编辑/删除按钮图标不渲染
import { Icon } from '@/components/icon-custom'

const { t } = useI18n()
const searchValue = ref<string>('')
const dsForm = ref()
const dsList = ref<any>([]) // show ds list
const allDsList = ref<any>([]) // all ds list
const router = useRouter()
const loading = ref(false)
const viewMode = ref<'card' | 'list'>('card')

function searchHandle() {
  if (searchValue.value) {
    dsList.value = JSON.parse(JSON.stringify(allDsList.value)).filter((item: any) => {
      return item.name.toLowerCase().includes(searchValue.value.toLowerCase())
    })
  } else {
    dsList.value = JSON.parse(JSON.stringify(allDsList.value))
  }
}

const refresh = () => {
  list()
}

const list = () => {
  loading.value = true
  datasourceApi.list().then((res) => {
    allDsList.value = res
    dsList.value = JSON.parse(JSON.stringify(allDsList.value))
  }).catch(() => {
    ElMessage.error(t('common.load_failed'))
  }).finally(() => {
    loading.value = false
  })
}

const editDs = (item: any) => {
  dsForm.value.open(item)
}

const deleteDs = (item: any) => {
  // 删除确认弹窗应显示数据源名称，而非通用"删除数据源"文案
  ElMessageBox.confirm(t('datasource.data_source', { msg: item.name }), t('common.confirm'), {
    confirmButtonText: t('common.confirm'),
    cancelButtonText: t('common.cancel'),
    type: 'warning',
    showClose: false,
  })
    .then(() => {
      datasourceApi.delete(item.id).then(() => {
        ElMessage.success(t('common.delete_success'))
        refresh()
      }).catch(() => {
        ElMessage.error(t('common.delete_failed'))
      })
    })
    .catch(() => {})
}

const getTables = (id: number, name: string) => {
  router.push(`/dsTable/${id}/${name}`)
}

onMounted(() => {
  list()
})
</script>
<style lang="less" scoped>
// ChatBI 数据源页面 - 重新设计的深色主题
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@primary-700: #6d28d9;
@dark-bg: #0f0a1a;
@dark-bg-secondary: #1a1225;
@dark-bg-card: rgba(26, 18, 37, 0.85);
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

.ds-page {
  min-height: 100vh;
  background: linear-gradient(180deg, @dark-bg 0%, @dark-bg-secondary 100%);
  padding: 32px 40px;
  position: relative;
  
  // 背景装饰
  &::before {
    content: '';
    position: absolute;
    top: 0;
    right: 0;
    width: 600px;
    height: 600px;
    background: radial-gradient(circle, rgba(139, 92, 246, 0.08) 0%, transparent 70%);
    pointer-events: none;
    z-index: 0;
  }
  
  > * {
    position: relative;
    z-index: 1;
  }
}

// 页面头部区域
.page-header-section {
  margin-bottom: 36px;
  
  .header-content {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
  }
  
  .title-area {
    flex: 1;
  }
  
  .page-subtitle {
    margin: 0;
    font-size: 15px;
    color: @dark-text-muted;
    line-height: 1.6;
    max-width: 600px;
  }
  
  .add-btn-primary {
    height: 48px;
    padding: 0 28px;
    font-size: 15px;
    font-weight: 600;
    background: linear-gradient(135deg, @primary-700 0%, @primary-600 50%, @primary-500 100%) !important;
    border: none !important;
    border-radius: 14px;
    box-shadow: 
      0 4px 20px rgba(139, 92, 246, 0.4),
      0 0 0 1px rgba(139, 92, 246, 0.1) inset;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    
    &:hover {
      box-shadow: 
        0 8px 32px rgba(139, 92, 246, 0.5),
        0 0 0 1px rgba(139, 92, 246, 0.2) inset;
      transform: translateY(-2px);
    }
    
    &:active {
      transform: translateY(0);
    }
  }
}

// 搜索和筛选栏
.toolbar-section {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
  padding: 20px 24px;
  background: rgba(26, 18, 37, 0.6);
  backdrop-filter: blur(20px);
  border: 1px solid @dark-border;
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
  
  .search-container {
    flex: 1;
    max-width: 480px;
    display: flex;
    align-items: center;
    background: rgba(139, 92, 246, 0.08);
    border: 1.5px solid @dark-border;
    border-radius: 12px;
    padding: 0 18px;
    height: 48px;
    transition: all 0.3s ease;
    
    &:focus-within {
      border-color: @primary-500;
      background: rgba(139, 92, 246, 0.12);
      box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.12);
    }
    
    .search-icon {
      color: @dark-text-muted;
      font-size: 18px;
      margin-right: 12px;
      flex-shrink: 0;
    }
    
    .search-input {
      flex: 1;
      
      :deep(.ed-input__wrapper),
      :deep(.el-input__wrapper) {
        box-shadow: none !important;
        background: transparent !important;
        padding: 0 !important;
        border: none !important;
      }
      
      :deep(.ed-input__inner),
      :deep(.el-input__inner) {
        font-size: 15px;
        color: @dark-text !important;
        
        &::placeholder {
          color: @dark-text-muted !important;
        }
      }
    }
  }
  
  .stats-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(139, 92, 246, 0.1) 100%);
    border: 1.5px solid rgba(139, 92, 246, 0.3);
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(139, 92, 246, 0.15);
    
    .badge-count {
      font-size: 20px;
      font-weight: 700;
      color: @primary-400;
      line-height: 1;
    }
    
    .badge-label {
      font-size: 14px;
      color: @dark-text-secondary;
      font-weight: 500;
    }
  }

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .view-toggle {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px;
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid @dark-border;
    border-radius: 10px;

    .toggle-btn {
      width: 36px;
      height: 36px;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      color: @dark-text-muted;
      transition: all 0.2s ease;

      &:hover {
        color: @dark-text-secondary;
        background: rgba(139, 92, 246, 0.12);
      }

      &.active {
        color: #fff;
        background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%);
        box-shadow: 0 2px 8px rgba(139, 92, 246, 0.3);
      }
    }
  }
}

// 数据源列表视图
.ds-list-view {
  animation: fadeInUp 0.5s ease-out;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid @dark-border;

  :deep(.ed-table),
  :deep(.el-table) {
    background: @dark-bg-card !important;

    th {
      background: rgba(139, 92, 246, 0.1) !important;
      color: @dark-text-secondary !important;
      border-bottom: 1px solid @dark-border !important;
      font-weight: 600;
    }

    td {
      border-bottom: 1px solid rgba(139, 92, 246, 0.1) !important;
    }

    tr {
      background: transparent !important;

      &:hover > td {
        background: rgba(139, 92, 246, 0.08) !important;
      }
    }

    .cell {
      color: @dark-text-secondary;
    }

    &::before {
      background-color: @dark-border !important;
    }
  }

  .list-ds-name {
    font-weight: 600;
    color: @dark-text;
  }

  .list-ds-type {
    display: inline-flex;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 600;
    color: @primary-400;
    background: rgba(139, 92, 246, 0.15);
    border: 1px solid rgba(139, 92, 246, 0.25);
    border-radius: 6px;
    text-transform: uppercase;
  }

  .list-ds-desc {
    color: @dark-text-muted;
    font-size: 13px;
  }

  .list-ds-count {
    font-weight: 700;
    color: @primary-400;
  }

  .list-ds-unit {
    font-size: 11px;
    color: @dark-text-muted;
    margin-left: 4px;
  }

  :deep(.ed-button--text),
  :deep(.el-button--text) {
    color: @dark-text-secondary !important;

    &:hover {
      color: @primary-400 !important;
    }
  }

  :deep(.ed-button--danger.is-text),
  :deep(.el-button--danger.is-text) {
    color: #f87171 !important;

    &:hover {
      color: #fca5a5 !important;
    }
  }
}

.ds-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 24px;
  animation: fadeInUp 0.5s ease-out;
  
  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
}

// 卡片操作按钮
.card-actions {
  position: absolute;
  top: 18px;
  right: 18px;
  display: flex;
  gap: 8px;
  opacity: 0;
  transform: translateY(-6px);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 10;
  pointer-events: none;
  
  .action-btn {
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 10px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    font-size: 15px;
    pointer-events: auto;
    backdrop-filter: blur(12px);
    
    &.view-btn {
      background: rgba(139, 92, 246, 0.15);
      border: 1px solid rgba(139, 92, 246, 0.25);
      color: @dark-text-secondary;
      
      &:hover {
        background: rgba(139, 92, 246, 0.3);
        color: @primary-400;
        border-color: rgba(139, 92, 246, 0.4);
        transform: translateY(-2px) scale(1.05);
        box-shadow: 0 6px 16px rgba(139, 92, 246, 0.35);
      }
    }
    
    &.edit-btn {
      background: rgba(139, 92, 246, 0.2);
      border: 1px solid rgba(139, 92, 246, 0.3);
      color: @primary-400;
      
      &:hover {
        background: rgba(139, 92, 246, 0.35);
        color: @primary-400;
        border-color: rgba(139, 92, 246, 0.5);
        transform: translateY(-2px) scale(1.05);
        box-shadow: 0 6px 16px rgba(139, 92, 246, 0.4);
      }
    }
    
    &.delete-btn {
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.25);
      color: #f87171;
      
      &:hover {
        background: rgba(239, 68, 68, 0.3);
        color: #fca5a5;
        border-color: rgba(239, 68, 68, 0.4);
        transform: translateY(-2px) scale(1.05);
        box-shadow: 0 6px 16px rgba(239, 68, 68, 0.35);
      }
    }
    
    :deep(svg) {
      width: 15px;
      height: 15px;
    }
  }
}

// 卡片悬停时显示操作按钮
.ds-grid :deep(.ds-card):hover .card-actions {
  opacity: 1;
  transform: translateY(0);
}

// 空状态
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  text-align: center;
  animation: fadeIn 0.6s ease-out;
  
  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
  
  .empty-illustration {
    width: 200px;
    height: 200px;
    margin-bottom: 32px;
    animation: float 3s ease-in-out infinite;
    
    @keyframes float {
      0%, 100% {
        transform: translateY(0);
      }
      50% {
        transform: translateY(-10px);
      }
    }
    
    svg {
      width: 100%;
      height: 100%;
      filter: drop-shadow(0 4px 20px rgba(139, 92, 246, 0.3));
    }
  }
  
  .empty-title {
    margin: 0 0 12px 0;
    font-size: 22px;
    font-weight: 600;
    color: @dark-text;
    letter-spacing: -0.3px;
  }
  
  .empty-description {
    margin: 0 0 32px 0;
    font-size: 15px;
    color: @dark-text-muted;
    line-height: 1.6;
    max-width: 480px;
  }
  
  .empty-action-btn {
    height: 48px;
    padding: 0 32px;
    font-size: 15px;
    font-weight: 600;
    background: linear-gradient(135deg, @primary-700 0%, @primary-600 50%, @primary-500 100%) !important;
    border: none !important;
    border-radius: 14px;
    box-shadow: 
      0 4px 20px rgba(139, 92, 246, 0.4),
      0 0 0 1px rgba(139, 92, 246, 0.1) inset;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    
    &:hover {
      box-shadow: 
        0 8px 32px rgba(139, 92, 246, 0.5),
        0 0 0 1px rgba(139, 92, 246, 0.2) inset;
      transform: translateY(-2px);
    }
  }
}

// 响应式适配 - 平板
@media (max-width: 1024px) {
  .ds-page {
    padding: 24px 28px;
  }
  
  .page-header-section {
    margin-bottom: 28px;
    
    .page-subtitle {
      font-size: 14px;
    }
  }
  
  .ds-grid {
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 20px;
  }
}

// 响应式适配 - 手机
@media (max-width: 768px) {
  .ds-page {
    padding: 20px;
    
    &::before {
      width: 400px;
      height: 400px;
    }
  }
  
  .page-header-section {
    margin-bottom: 24px;
    
    .header-content {
      flex-direction: column;
      align-items: stretch;
    }
    
    .page-subtitle {
      font-size: 14px;
      margin-bottom: 16px;
    }
    
    .add-btn-primary {
      width: 100%;
      justify-content: center;
    }
  }
  
  .toolbar-section {
    flex-direction: column;
    padding: 16px;
    gap: 12px;
    
    .search-container {
      max-width: 100%;
      width: 100%;
    }
    
    .stats-badge {
      width: 100%;
      justify-content: center;
    }
  }
  
  .ds-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  
  .empty-state {
    padding: 60px 20px;
    
    .empty-illustration {
      width: 160px;
      height: 160px;
      margin-bottom: 24px;
    }
    
    .empty-title {
      font-size: 20px;
    }
    
    .empty-description {
      font-size: 14px;
    }
  }
}

// 超小屏幕
@media (max-width: 480px) {
  .ds-page {
    padding: 16px;
  }
  
  .toolbar-section {
    padding: 14px;
    
    .search-container {
      height: 44px;
      padding: 0 14px;
    }
  }
  
  .card-actions {
    .action-btn {
      width: 32px;
      height: 32px;
      
      :deep(svg) {
        width: 13px;
        height: 13px;
      }
    }
  }
}
</style>

