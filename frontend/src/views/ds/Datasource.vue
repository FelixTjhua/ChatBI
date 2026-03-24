<script lang="ts" setup>
import { ref, computed, shallowRef, h } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus-secondary'
import icon_searchOutline_outlined from '@/assets/svg/icon_search-outline_outlined.svg'
import arrow_down from '@/assets/svg/arrow-down.svg'
import icon_add_outlined from '@/assets/svg/icon_add_outlined.svg'
import EmptyBackground from '@/components/EmptyBackground.vue'
import { useRouter } from 'vue-router'
import DataTable from './DataTable.vue'
import icon_done_outlined from '@/assets/svg/icon_done_outlined.svg'
import { datasourceApi } from '@/api/datasource'
import AddDrawer from '@/views/ds/AddDrawer.vue'
import Card from './Card.vue'
import { useEmitt } from '@/utils/useEmitt'
import DelMessageBox from './DelMessageBox.vue'
import { dsTypeWithImg } from './js/ds-type'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'
import { chatApi } from '@/api/chat'
const userStore = useUserStore()
interface Datasource {
  name: string
  num: string
  type_name: string
  type: string
  img: string
  description: string
  id?: string
}

const router = useRouter()
const { t } = useI18n()
const keywords = ref('')
const defaultDatasourceKeywords = ref('')
const addDrawerRef = ref()
const searchLoading = ref(false)

const datasourceList = shallowRef([] as Datasource[])
const defaultDatasourceList = shallowRef(dsTypeWithImg as (Datasource & { img: string })[])

const currentDefaultDatasource = ref('')
const datasourceListWithSearch = computed(() => {
  if (!keywords.value && !currentDatasourceType.value) return datasourceList.value
  return datasourceList.value.filter(
    (ele) =>
      ele.name.toLowerCase().includes(keywords.value.toLowerCase()) &&
      (!currentDatasourceType.value || ele.type === currentDatasourceType.value)
  )
})
const defaultDatasourceListWithSearch = computed(() => {
  if (!defaultDatasourceKeywords.value) return defaultDatasourceList.value
  return defaultDatasourceList.value.filter((ele) =>
    ele.name.toLowerCase().includes(defaultDatasourceKeywords.value.toLowerCase())
  )
})

const currentDatasourceType = ref('')

const handleDefaultDatasourceChange = (item: any) => {
  if (currentDatasourceType.value === item.type) {
    currentDefaultDatasource.value = ''
    currentDatasourceType.value = ''
  } else {
    currentDefaultDatasource.value = item.name
    currentDatasourceType.value = item.type
  }
}

const formatKeywords = (item: string) => {
  if (!defaultDatasourceKeywords.value) return item
  // 转义HTML特殊字符防止XSS
  const escapeHtml = (str: string) =>
    str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  const safeItem = escapeHtml(item)
  const safeKeyword = escapeHtml(defaultDatasourceKeywords.value)
  return safeItem.replaceAll(
    safeKeyword,
    `<span class="isSearch">${safeKeyword}</span>`
  )
}
const handleEditDatasource = (res: any) => {
  addDrawerRef.value.handleEditDatasource(res)
}

const handleQuestion = async (id: string) => {
  try {
    await chatApi.checkLLMModel()
  } catch (error: any) {
    let errorMsg = t('model.default_miss')
    let confirm_text = t('datasource.got_it')
    if (userStore.isAdmin) {
      errorMsg = t('model.default_miss_admin')
      confirm_text = t('model.to_config')
    }
    ElMessageBox.confirm(t('qa.ask_failed'), {
      confirmButtonType: 'primary',
      tip: errorMsg,
      showCancelButton: userStore.isAdmin,
      confirmButtonText: confirm_text,
      cancelButtonText: t('common.cancel'),
      customClass: 'confirm-no_icon',
      autofocus: false,
      showClose: false,
      callback: (val: string) => {
        if (userStore.isAdmin && val === 'confirm') {
          router.push('/system/model')
        }
      },
    })
    return
  }
  router.push({ path: '/chat/index', query: { start_chat: id } })
}

const handleAddDatasource = () => {
  addDrawerRef.value.handleAddDatasource()
}

const refreshData = () => {
  search()
}

const deleteHandler = (item: any) => {
  ElMessageBox.confirm('', {
    confirmButtonType: 'danger',
    tip: t('datasource.operate_with_caution'),
    confirmButtonText: t('dashboard.delete'),
    cancelButtonText: t('common.cancel'),
    customClass: 'confirm-no_icon',
    autofocus: false,
    showClose: false,
    message: h(DelMessageBox, { name: item.name, t }, ''),
  }).then(() => {
    datasourceApi.delete(item.id).then(() => {
      ElMessage({ type: 'success', message: t('dashboard.delete_success') })
      search()
    }).catch(() => {
      ElMessage({ type: 'error', message: t('common.delete_failed') })
    })
  }).catch(() => {})
}

const search = () => {
  searchLoading.value = true
  datasourceApi
    .list()
    .then((res: any) => { datasourceList.value = res })
    .catch(() => { ElMessage({ type: 'error', message: t('common.load_failed') }) })
    .finally(() => { searchLoading.value = false })
}
search()

const currentDataTable = ref()
const dataTableDetail = (ele: any) => { currentDataTable.value = ele }
const back = () => { currentDataTable.value = null }

useEmitt({ name: 'ds-index-click', callback: back })
</script>

<template>
  <div v-show="!currentDataTable" class="datasource-page no-padding">
    <!-- 顶部区域：标题 + 搜索 合为一体 -->
    <div class="top-bar">
      <!-- 第一行：标题 + 数量 -->
      <div class="top-row">
        <div class="title-group">
          <div class="chatbi-page-title">
            <span class="title-text">{{ $t('menu.Data Connections') }}</span>
          </div>
          <span v-if="datasourceListWithSearch.length > 0" class="count-tag">{{ datasourceListWithSearch.length }}</span>
        </div>
      </div>
      <!-- 第二行：搜索 + 类型筛选 + 新建按钮 -->
      <div class="filter-row">
        <div class="search-box">
          <el-icon class="search-ico"><icon_searchOutline_outlined class="svg-icon" /></el-icon>
          <el-input v-model="keywords" clearable class="search-input" :placeholder="$t('datasource.search')" />
        </div>
        <el-popover popper-class="ds-type-popover" placement="bottom-end">
          <template #reference>
            <el-button class="filter-btn" secondary>
              {{ currentDefaultDatasource || $t('datasource.all_types') }}
              <el-icon style="margin-left: 6px"><arrow_down /></el-icon>
            </el-button>
          </template>
          <div class="popover">
            <el-input v-model="defaultDatasourceKeywords" clearable style="width: 100%; margin-right: 12px" :placeholder="$t('datasource.search_by_name')">
              <template #prefix><el-icon><icon_searchOutline_outlined class="svg-icon" /></el-icon></template>
            </el-input>
            <div class="popover-content">
              <div v-for="ele in defaultDatasourceListWithSearch" :key="ele.name" class="popover-item" :class="currentDefaultDatasource === ele.name && 'isActive'" @click="handleDefaultDatasourceChange(ele)">
                <img :src="ele.img" width="24px" height="24px" />
                <div class="datasource-name" v-html="formatKeywords(ele.name)"></div>
                <el-icon size="16" class="done"><icon_done_outlined /></el-icon>
              </div>
              <div v-if="!defaultDatasourceListWithSearch.length" class="popover-item empty">{{ t('model.relevant_results_found') }}</div>
            </div>
          </div>
        </el-popover>
        <el-button class="add-btn" type="primary" @click="handleAddDatasource">
          <template #icon><icon_add_outlined /></template>
          {{ $t('datasource.new_data_source') }}
        </el-button>
      </div>
    </div>

    <!-- 搜索无结果 -->
    <EmptyBackground v-if="!!keywords && !datasourceListWithSearch.length" :description="$t('datasource.relevant_content_found')" class="ds-empty-search" img-type="tree" />

    <!-- 卡片列表 -->
    <div v-else-if="datasourceListWithSearch.length > 0" class="card-grid" v-loading="searchLoading">
      <el-row :gutter="20" class="w-full">
        <el-col v-for="ele in datasourceListWithSearch" :key="ele.id" :xs="24" :sm="12" :md="12" :lg="8" :xl="6" class="mb-20">
          <Card :id="ele.id" :key="ele.id" :name="ele.name" :type="ele.type" :type-name="ele.type_name" :num="ele.num" :description="ele.description" @question="handleQuestion" @edit="handleEditDatasource(ele)" @del="deleteHandler(ele)" @data-table-detail="dataTableDetail(ele)" />
        </el-col>
      </el-row>
    </div>

    <!-- 空状态 -->
    <template v-else-if="!keywords && !datasourceListWithSearch.length && !searchLoading">
      <div class="empty-state">
        <div class="empty-visual">
          <svg viewBox="0 0 180 180" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="90" cy="90" r="70" stroke="url(#g1)" stroke-width="2" opacity="0.25" />
            <circle cx="90" cy="90" r="50" stroke="url(#g1)" stroke-width="1.5" opacity="0.18" />
            <path d="M60 78h60M60 90h42M60 102h50" stroke="url(#g1)" stroke-width="2.5" stroke-linecap="round" opacity="0.45" />
            <circle cx="90" cy="90" r="22" stroke="url(#g1)" stroke-width="2" opacity="0.35" />
            <defs><linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#8b5cf6" /><stop offset="100%" style="stop-color:#a78bfa" /></linearGradient></defs>
          </svg>
        </div>
        <h3 class="empty-title">{{ $t('ds.no_datasource') }}</h3>
        <p class="empty-desc">{{ $t('ds.empty_description') }}</p>
        <el-button class="empty-btn" type="primary" @click="handleAddDatasource">
          <template #icon><icon_add_outlined /></template>
          {{ $t('datasource.new_data_source') }}
        </el-button>
      </div>
    </template>

    <AddDrawer ref="addDrawerRef" @search="search" />
  </div>
  <DataTable v-if="currentDataTable" :info="currentDataTable" @refresh="refreshData" @back="back" />
</template>

<style lang="less" scoped>
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@primary-700: #6d28d9;
@bg: #0f0a1a;
@bg2: #1a1225;
@border: rgba(139, 92, 246, 0.2);
@text: rgba(255, 255, 255, 0.95);
@text2: rgba(196, 181, 253, 0.8);
@text3: rgba(196, 181, 253, 0.5);

.datasource-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, @bg 0%, @bg2 100%);
  overflow: hidden;
  position: relative;

  &::before {
    content: '';
    position: absolute;
    top: -60px;
    right: -80px;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(139, 92, 246, 0.06) 0%, transparent 70%);
    pointer-events: none;
    z-index: 0;
  }

  > * { position: relative; z-index: 1; }
}

// ===== 顶部区域：标题 + 搜索合为一体 =====
.top-bar {
  flex-shrink: 0;
  padding: 20px 32px 16px;
  background: rgba(139, 92, 246, 0.025);
  border-bottom: 1px solid rgba(139, 92, 246, 0.1);
}

// 第一行：标题 + 数量 + 新建
.top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.title-group {
  display: flex;
  align-items: center;
  gap: 10px;

  .count-tag {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 24px;
    height: 22px;
    padding: 0 7px;
    font-size: 12px;
    font-weight: 700;
    color: @primary-400;
    background: rgba(139, 92, 246, 0.18);
    border: 1px solid rgba(139, 92, 246, 0.25);
    border-radius: 6px;
    line-height: 1;
  }
}

.add-btn {
  flex-shrink: 0;
  height: 34px;
  padding: 0 18px;
  font-size: 13px;
  font-weight: 600;
  background: linear-gradient(135deg, @primary-700 0%, @primary-600 50%, @primary-500 100%) !important;
  border: none !important;
  border-radius: 9px;
  box-shadow: 0 2px 10px rgba(139, 92, 246, 0.3);
  transition: all 0.25s ease;

  &:hover {
    box-shadow: 0 4px 18px rgba(139, 92, 246, 0.45);
    transform: translateY(-1px);
  }
  &:active { transform: translateY(0); }
}

// 第二行：搜索 + 筛选
.filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.search-box {
  flex: 1;
  max-width: 360px;
  display: flex;
  align-items: center;
  background: rgba(139, 92, 246, 0.06);
  border: 1px solid rgba(139, 92, 246, 0.15);
  border-radius: 9px;
  padding: 0 14px;
  height: 34px;
  transition: all 0.25s ease;

  &:focus-within {
    border-color: @primary-500;
    background: rgba(139, 92, 246, 0.1);
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.08);
  }

  .search-ico { color: @text3; font-size: 15px; margin-right: 8px; flex-shrink: 0; }

  .search-input {
    flex: 1;
    :deep(.ed-input__wrapper), :deep(.el-input__wrapper) { box-shadow: none !important; background: transparent !important; padding: 0 !important; border: none !important; height: 32px; }
    :deep(.ed-input__inner), :deep(.el-input__inner) { font-size: 13px; color: @text !important; height: 32px; &::placeholder { color: @text3 !important; } }
  }
}

.filter-btn {
  height: 34px;
  padding: 0 14px;
  font-size: 13px;
  background: rgba(139, 92, 246, 0.06) !important;
  border: 1px solid rgba(139, 92, 246, 0.15) !important;
  border-radius: 9px;
  color: @text2 !important;
  white-space: nowrap;
  transition: all 0.2s ease;
  &:hover { border-color: rgba(139, 92, 246, 0.3) !important; background: rgba(139, 92, 246, 0.12) !important; color: @primary-400 !important; }
}

// ===== 卡片网格 =====
.card-grid {
  flex: 1;
  overflow-y: auto;
  padding: 20px 32px 20px;
  animation: fadeUp 0.35s ease-out;

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .w-full { width: 100%; }
  .mb-20 { margin-bottom: 20px; }

  &::-webkit-scrollbar { width: 5px; }
  &::-webkit-scrollbar-track { background: rgba(139, 92, 246, 0.03); }
  &::-webkit-scrollbar-thumb {
    background: rgba(139, 92, 246, 0.25);
    border-radius: 3px;
    &:hover { background: rgba(139, 92, 246, 0.4); }
  }
}

// 搜索无结果
.ds-empty-search {
  padding: 80px 0 0;
  :deep(.ed-empty__description), :deep(.el-empty__description) { color: @text3; }
}

// 空状态
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  text-align: center;
  animation: fadeIn 0.5s ease-out;

  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

  .empty-visual {
    width: 150px;
    height: 150px;
    margin-bottom: 24px;
    animation: float 3s ease-in-out infinite;
    @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
    svg { width: 100%; height: 100%; filter: drop-shadow(0 4px 16px rgba(139, 92, 246, 0.2)); }
  }

  .empty-title { margin: 0 0 8px; font-size: 18px; font-weight: 600; color: @text; }
  .empty-desc { margin: 0 0 24px; font-size: 13px; color: @text3; line-height: 1.6; max-width: 400px; }

  .empty-btn {
    height: 38px;
    padding: 0 22px;
    font-size: 13px;
    font-weight: 600;
    background: linear-gradient(135deg, @primary-700 0%, @primary-600 50%, @primary-500 100%) !important;
    border: none !important;
    border-radius: 10px;
    box-shadow: 0 3px 14px rgba(139, 92, 246, 0.35);
    transition: all 0.25s ease;
    &:hover { box-shadow: 0 5px 22px rgba(139, 92, 246, 0.48); transform: translateY(-1px); }
  }
}

// ===== 响应式 =====
@media (max-width: 1024px) {
  .top-bar { padding: 18px 24px 14px; }
  .card-grid { padding: 18px 24px 16px; }
}

@media (max-width: 768px) {
  .top-bar { padding: 16px 18px 12px; }
  .top-row { flex-wrap: wrap; }
  .add-btn { height: 32px; padding: 0 14px; font-size: 12px; }
  .filter-row {
    flex-direction: column;
    gap: 8px;
    .search-box { max-width: 100%; width: 100%; }
    .filter-btn { width: 100%; }
  }
  .card-grid { padding: 14px 18px 12px; }
  .empty-state { padding: 30px 18px; .empty-visual { width: 120px; height: 120px; } }
}
</style>

<style lang="less">
@bg2: #1a1225;
@border: rgba(139, 92, 246, 0.2);
@text: rgba(255, 255, 255, 0.95);
@text2: rgba(196, 181, 253, 0.8);
@text3: rgba(196, 181, 253, 0.5);
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;

.ds-type-popover.ds-type-popover {
  padding: 8px;
  width: 320px !important;
  background: @bg2 !important;
  backdrop-filter: blur(16px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5), 0 0 0 1px @border;
  border: 1px solid @border !important;
  border-radius: 14px !important;

  .ed-input {
    margin-bottom: 8px;
    .ed-input__wrapper {
      background: rgba(139, 92, 246, 0.08) !important;
      border: 1px solid @border !important;
      border-radius: 10px;
      box-shadow: none !important;
      &:hover { border-color: rgba(139, 92, 246, 0.35) !important; }
      &:focus-within { border-color: @primary-500 !important; box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15) !important; }
    }
    .ed-input__inner { color: @text !important; &::placeholder { color: @text3 !important; } }
    .ed-input__prefix { color: @text3; }
  }

  .popover-content {
    padding: 4px;
    max-height: 300px;
    overflow-y: auto;
    &::-webkit-scrollbar { width: 5px; }
    &::-webkit-scrollbar-track { background: transparent; }
    &::-webkit-scrollbar-thumb { background: rgba(139, 92, 246, 0.3); border-radius: 3px; &:hover { background: rgba(139, 92, 246, 0.5); } }
  }

  .popover-item {
    height: 38px;
    display: flex;
    align-items: center;
    padding: 0 12px;
    margin-bottom: 3px;
    border-radius: 9px;
    cursor: pointer;
    color: @text2;
    transition: all 0.2s ease;

    &:not(.empty):hover { background: rgba(139, 92, 246, 0.15); color: @text; }
    &.empty { font-size: 14px; color: @text3; cursor: default; justify-content: center; }
    img { border-radius: 6px; padding: 3px; background: rgba(139, 92, 246, 0.1); }
    .datasource-name { margin-left: 12px; font-weight: 500; font-size: 14px; }
    .done { margin-left: auto; display: none; color: @primary-400; }
    .isSearch { color: @primary-400; font-weight: 600; }
    &.isActive { background: rgba(139, 92, 246, 0.2); color: @primary-400; .done { display: block; } }
  }
}

.confirm-no_icon {
  background: @bg2 !important;
  border: 1px solid @border !important;
  border-radius: 16px !important;
  padding: 24px;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.5);

  .ed-message-box__header, .el-message-box__header {
    padding-bottom: 16px;
    .ed-message-box__title, .el-message-box__title { color: @text !important; font-weight: 600; }
  }
  .ed-message-box__content, .el-message-box__content { color: @text2 !important; }
  .tip {
    margin-top: 16px;
    padding: 12px 16px;
    background: rgba(139, 92, 246, 0.1);
    border: 1px solid @border;
    border-radius: 10px;
    color: @text2;
    font-size: 13px;
    line-height: 1.5;
  }
  .ed-message-box__btns, .el-message-box__btns {
    padding-top: 20px;
    .ed-button--default, .el-button--default {
      background: rgba(139, 92, 246, 0.1) !important;
      border: 1px solid @border !important;
      color: @text2 !important;
      border-radius: 10px;
      &:hover { background: rgba(139, 92, 246, 0.2) !important; border-color: rgba(139, 92, 246, 0.35) !important; color: @text !important; }
    }
    .ed-button--primary, .el-button--primary {
      background: linear-gradient(135deg, #7c3aed 0%, #8b5cf6 100%) !important;
      border: none !important;
      border-radius: 10px;
      box-shadow: 0 4px 16px rgba(139, 92, 246, 0.35);
      &:hover { box-shadow: 0 6px 24px rgba(139, 92, 246, 0.45); }
    }
    .ed-button--danger, .el-button--danger {
      background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%) !important;
      border: none !important;
      border-radius: 10px;
      box-shadow: 0 4px 16px rgba(239, 68, 68, 0.35);
      &:hover { box-shadow: 0 6px 24px rgba(239, 68, 68, 0.45); }
    }
  }
}
</style>
