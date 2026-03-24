<template>
  <div v-loading="loading" class="user-page">
    <!-- 顶部：标题 + 搜索 + 筛选 + 新建 -->
    <div class="top-bar">
      <div class="top-row">
        <div class="title-group">
          <div class="chatbi-page-title">
            <span class="title-text">{{ t('user.user_management') }}</span>
          </div>
        </div>
      </div>
      <div class="filter-row">
        <div class="search-box">
          <el-icon class="search-ico"><Search /></el-icon>
          <el-input
            v-model="searchKeyword"
            :placeholder="t('user.search_placeholder')"
            class="search-input"
            clearable
            @input="handleSearch"
            @clear="loadData"
          />
        </div>
        <el-select v-model="roleFilter" :placeholder="t('user.role')" class="mini-select" clearable @change="loadData">
          <el-option :label="t('user.administrator')" value="admin" />
          <el-option :label="t('user.ordinary_member')" value="member" />
        </el-select>
        <el-select v-model="statusFilter" :placeholder="t('user.status')" class="mini-select" clearable @change="loadData">
          <el-option :label="t('user.enabled')" :value="1" />
          <el-option :label="t('user.disabled')" :value="0" />
        </el-select>
        <el-button type="primary" class="add-btn" @click="handleAdd">
          <el-icon><Plus /></el-icon>
          <span>{{ t('user.add_user') }}</span>
        </el-button>
      </div>
    </div>

    <!-- 用户表格 -->
    <div v-if="tableData.length > 0" class="table-wrap">
      <el-table :data="tableData" :max-height="tableMaxHeight" class="user-table" stripe>
        <el-table-column type="index" label="#" width="50" align="center" />
        <el-table-column :label="t('user.user_info')" min-width="240">
          <template #default="{ row }">
            <div class="user-cell">
              <div class="avatar" :class="`c${row.id % 6}`">{{ getInitial(row.name) }}</div>
              <div class="info">
                <div class="uname">{{ row.name }}</div>
                <div class="uaccount">@{{ row.account }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('user.email')" prop="email" min-width="200">
          <template #default="{ row }">
            <span class="email-text">{{ row.email || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('user.role')" width="120" align="center">
          <template #default="{ row }">
            <span class="role-badge" :class="row.role === 'admin' ? 'admin' : 'member'">
              {{ getRoleText(row.role) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column :label="t('user.status')" width="110" align="center">
          <template #default="{ row }">
            <span class="status-dot" :class="row.status === 1 ? 'on' : 'off'">
              {{ row.status === 1 ? t('user.enabled') : t('user.disabled') }}
            </span>
          </template>
        </el-table-column>
        <el-table-column :label="t('user.create_time')" width="170">
          <template #default="{ row }">
            <span class="time-text">{{ formatTimestamp(row.create_time, 'YYYY-MM-DD HH:mm') }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('ds.actions')" width="180" align="center" fixed="right">
          <template #default="{ row }">
            <div class="act-row">
              <el-tooltip :content="t('common.edit')" placement="top">
                <button class="act-btn edit" @click="handleEdit(row)"><el-icon><Edit /></el-icon></button>
              </el-tooltip>
              <el-tooltip v-if="row.account !== 'admin'" :content="row.status ? t('user.disable') : t('user.enable')" placement="top">
                <button class="act-btn" :class="row.status ? 'warn' : 'ok'" @click="handleToggleStatus(row)">
                  <el-icon><component :is="row.status ? Lock : Unlock" /></el-icon>
                </button>
              </el-tooltip>
              <el-tooltip :content="t('common.reset_password')" placement="top">
                <button class="act-btn info" @click="handleResetPwd(row)"><el-icon><Key /></el-icon></button>
              </el-tooltip>
              <el-tooltip v-if="row.id !== currentUserId && row.account !== 'admin'" :content="t('common.delete')" placement="top">
                <button class="act-btn del" @click="handleDelete(row)"><el-icon><Delete /></el-icon></button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-icon">
        <svg viewBox="0 0 160 160" fill="none">
          <circle cx="80" cy="80" r="60" stroke="url(#ug)" stroke-width="1.5" opacity="0.22" />
          <circle cx="80" cy="68" r="20" stroke="url(#ug)" stroke-width="2" opacity="0.4" />
          <path d="M50 120 Q80 105 110 120" stroke="url(#ug)" stroke-width="2" stroke-linecap="round" opacity="0.4" />
          <defs><linearGradient id="ug" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#8b5cf6" /><stop offset="100%" style="stop-color:#a78bfa" /></linearGradient></defs>
        </svg>
      </div>
      <h3>{{ t('user.no_users') }}</h3>
      <p>{{ t('user.empty_description') }}</p>
      <el-button type="primary" class="add-btn" @click="handleAdd">
        <el-icon><Plus /></el-icon>
        {{ t('user.add_first_user') }}
      </el-button>
    </div>

    <!-- 分页 -->
    <div v-if="total > 0" class="pager">
      <el-pagination
        :current-page="page"
        :page-size="10"
        :total="total"
        layout="total, prev, pager, next, jumper"
        background
        @current-change="(val: number) => { page = val; loadData() }"
      />
    </div>

    <!-- 新增/编辑用户抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :title="isEdit ? t('user.edit_user') : t('user.add_user')"
      size="480px"
      :close-on-click-modal="false"
      class="user-drawer"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-position="top" class="user-form">
        <el-form-item :label="t('user.account')" prop="account">
          <el-input v-model="formData.account" :disabled="isEdit" :placeholder="t('user.enter_account')" />
        </el-form-item>
        <el-form-item :label="t('user.name')" prop="name">
          <el-input v-model="formData.name" :placeholder="t('user.enter_name')" />
        </el-form-item>
        <el-form-item :label="t('user.email')" prop="email">
          <el-input v-model="formData.email" :placeholder="t('user.enter_email')" />
        </el-form-item>
        <el-form-item :label="t('user.role')" prop="role">
          <el-select v-model="formData.role" :placeholder="t('user.select_role')" class="w-full">
            <el-option :label="t('user.administrator')" value="admin" />
            <el-option :label="t('user.ordinary_member')" value="member" />
          </el-select>
        </el-form-item>
        <div v-if="!isEdit && defaultPwd" class="pwd-hint">
          <el-icon><InfoFilled /></el-icon>
          <span>{{ t('user.default_password_tip', { pwd: defaultPwd }) }}</span>
        </div>
      </el-form>
      <template #footer>
        <div class="drawer-footer">
          <el-button @click="drawerVisible = false">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">{{ t('common.save') }}</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus-secondary'
import { Search, Plus, Edit, Delete, Lock, Unlock, Key, InfoFilled } from '@element-plus/icons-vue'
import { userApi } from '@/api/auth'
import { formatTimestamp } from '@/utils/date'
import { useUserStore } from '@/stores/user'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const userStore = useUserStore()
const currentUserId = computed(() => userStore.getUid)

// 列表状态
const loading = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const tableMaxHeight = computed(() => window.innerHeight - 280)
const searchKeyword = ref('')
const roleFilter = ref('')
const statusFilter = ref<number | string>('')

// 抽屉状态
const drawerVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const formRef = ref()
const defaultPwd = ref('')

const formData = reactive({
  id: '',
  account: '',
  name: '',
  email: '',
  role: 'member',
})

const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const formRules = computed(() => ({
  account: [
    { required: true, message: t('user.account_required'), trigger: 'blur' },
    { min: 2, max: 100, message: t('user.account_length'), trigger: 'blur' },
  ],
  name: [
    { required: true, message: t('user.name_required'), trigger: 'blur' },
    { min: 1, max: 100, message: t('user.name_length'), trigger: 'blur' },
  ],
  email: [
    { required: true, message: t('user.email_required'), trigger: 'blur' },
    { pattern: emailRegex, message: t('user.email_format_error'), trigger: 'blur' },
  ],
  role: [
    { required: true, message: t('user.role_required'), trigger: 'change' },
  ],
}))

let searchTimer: ReturnType<typeof setTimeout> | null = null
const handleSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    loadData()
  }, 300)
}

const loadData = async () => {
  loading.value = true
  try {
    const params: any = {}
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (statusFilter.value !== '' && statusFilter.value !== null) params.status = statusFilter.value
    if (roleFilter.value) params.role = [roleFilter.value]
    const res: any = await userApi.pager(page.value, pageSize.value, params)
    tableData.value = res?.items || res?.records || []
    total.value = res?.total || 0
  } catch (e) {
    ElMessage.error(t('common.load_failed'))
  } finally {
    loading.value = false
  }
}

const getInitial = (name: string) => {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}

const getRoleText = (role: string) => {
  if (role === 'admin') return t('user.administrator')
  return t('user.ordinary_member')
}

const handleAdd = async () => {
  isEdit.value = false
  Object.assign(formData, { id: '', account: '', name: '', email: '', role: 'member' })
  try {
    const res: any = await userApi.getDefaultPwd()
    defaultPwd.value = res || ''
  } catch { defaultPwd.value = '' }
  drawerVisible.value = true
}

const handleEdit = (row: any) => {
  isEdit.value = true
  Object.assign(formData, {
    id: row.id,
    account: row.account,
    name: row.name,
    email: row.email || '',
    role: row.role || 'member',
  })
  drawerVisible.value = true
}

const handleSave = async () => {
  if (!formRef.value) return
  await formRef.value.validate()
  saving.value = true
  try {
    if (isEdit.value) {
      await userApi.edit({ ...formData })
      ElMessage.success(t('common.update_success'))
    } else {
      await userApi.add({ ...formData })
      ElMessage.success(t('common.save_success'))
    }
    drawerVisible.value = false
    loadData()
  } catch (e: any) {
    ElMessage.error(t('common.save_failed'))
  } finally {
    saving.value = false
  }
}

const handleToggleStatus = (row: any) => {
  const newStatus = row.status === 1 ? 0 : 1
  const actionText = newStatus === 1 ? t('user.enable') : t('user.disable')
  ElMessageBox.confirm(
    t('user.change_status_confirm', { status: actionText, name: row.name }),
    {
      confirmButtonType: newStatus === 0 ? 'danger' : 'primary',
      confirmButtonText: t('common.confirm2'),
      cancelButtonText: t('common.cancel'),
      customClass: 'confirm-no_icon',
      autofocus: false,
      showClose: false,
    }
  ).then(async () => {
    try {
      await userApi.changeStatus(row.id, newStatus)
      ElMessage.success(t('common.success'))
      loadData()
    } catch {
      ElMessage.error(t('common.save_failed'))
    }
  }).catch(() => {})
}

const handleResetPwd = (row: any) => {
  ElMessageBox.confirm(
    t('user.reset_password_confirm', { name: row.name }),
    {
      confirmButtonType: 'primary',
      confirmButtonText: t('common.confirm2'),
      cancelButtonText: t('common.cancel'),
      customClass: 'confirm-no_icon',
      autofocus: false,
      showClose: false,
    }
  ).then(async () => {
    try {
      await userApi.resetPwd(row.id)
      ElMessage.success(t('common.password_reset_successful'))
    } catch {
      ElMessage.error(t('common.save_failed'))
    }
  }).catch(() => {})
}

const handleDelete = (row: any) => {
  ElMessageBox.confirm(
    t('user.del_user', { msg: row.name }),
    {
      confirmButtonType: 'danger',
      confirmButtonText: t('common.delete'),
      cancelButtonText: t('common.cancel'),
      customClass: 'confirm-no_icon',
      autofocus: false,
      showClose: false,
    }
  ).then(async () => {
    try {
      await userApi.delete(row.id)
      ElMessage.success(t('common.delete_success'))
      loadData()
    } catch {
      ElMessage.error(t('common.save_failed'))
    }
  }).catch(() => {})
}

const resetForm = () => {
  formRef.value?.resetFields()
  Object.assign(formData, { id: '', account: '', name: '', email: '', role: 'member' })
}

onMounted(() => { loadData() })
</script>

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

.user-page {
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

// ===== 顶部区域 =====
.top-bar {
  flex-shrink: 0;
  padding: 20px 32px 16px;
  background: rgba(139, 92, 246, 0.025);
  border-bottom: 1px solid rgba(139, 92, 246, 0.1);
}

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

.filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.search-box {
  flex: 1;
  max-width: 320px;
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
    :deep(.ed-input__wrapper), :deep(.el-input__wrapper) {
      box-shadow: none !important; background: transparent !important;
      padding: 0 !important; border: none !important; height: 32px;
    }
    :deep(.ed-input__inner), :deep(.el-input__inner) {
      font-size: 13px; color: @text !important; height: 32px;
      &::placeholder { color: @text3 !important; }
    }
  }
}

.mini-select {
  width: 120px;
  :deep(.ed-input__wrapper), :deep(.el-input__wrapper) {
    height: 34px !important;
    background: rgba(139, 92, 246, 0.06) !important;
    border: 1px solid rgba(139, 92, 246, 0.15) !important;
    border-radius: 9px !important;
    box-shadow: none !important;
    &:hover { border-color: rgba(139, 92, 246, 0.3) !important; }
    &.is-focus { border-color: @primary-500 !important; }
  }
  :deep(.ed-input__inner), :deep(.el-input__inner) {
    font-size: 13px; color: @text2 !important;
    &::placeholder { color: @text3 !important; }
  }
  :deep(.ed-input__suffix), :deep(.el-input__suffix) { color: @text3; }
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
  &:hover { box-shadow: 0 4px 18px rgba(139, 92, 246, 0.45); transform: translateY(-1px); }
  &:active { transform: translateY(0); }
}

// ===== 表格区域 =====
.table-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 16px 32px 0;
  animation: fadeUp 0.3s ease-out;

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  &::-webkit-scrollbar { width: 5px; }
  &::-webkit-scrollbar-track { background: rgba(139, 92, 246, 0.03); }
  &::-webkit-scrollbar-thumb {
    background: rgba(139, 92, 246, 0.25); border-radius: 3px;
    &:hover { background: rgba(139, 92, 246, 0.4); }
  }
}

.user-table {
  :deep(.ed-table__header), :deep(.el-table__header) {
    th { background: rgba(139, 92, 246, 0.06) !important; color: @text2 !important; font-weight: 600; font-size: 13px; border-bottom: 1px solid @border !important; }
    th.el-table__cell, th.ed-table__cell { background: rgba(139, 92, 246, 0.06) !important; }
  }
  :deep(.ed-table__body), :deep(.el-table__body) {
    td { border-bottom: 1px solid rgba(139, 92, 246, 0.06) !important; color: @text2; font-size: 13px; }
  }
  :deep(.ed-table__row), :deep(.el-table__row) {
    background: transparent !important;
    &:hover > td { background: rgba(139, 92, 246, 0.06) !important; }
    &.ed-table__row--striped > td, &.el-table__row--striped > td { background: rgba(139, 92, 246, 0.03) !important; }
  }
  :deep(.ed-table__empty-block), :deep(.el-table__empty-block) { background: transparent !important; }
  :deep(.ed-table__inner-wrapper), :deep(.el-table__inner-wrapper) { background: transparent !important; }
  :deep(&::before), :deep(.ed-table__border-left-patch) { display: none; }
  background: transparent !important;
  :deep(.ed-table__fixed-right-patch), :deep(.el-table__fixed-right-patch) { background: transparent !important; }
  :deep(.ed-table__cell.is-right), :deep(.el-table__cell.is-right) { background: transparent !important; }
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 12px;

  .avatar {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 700;
    color: #fff;
    flex-shrink: 0;

    &.c0 { background: linear-gradient(135deg, #8b5cf6, #a78bfa); }
    &.c1 { background: linear-gradient(135deg, #6366f1, #818cf8); }
    &.c2 { background: linear-gradient(135deg, #ec4899, #f472b6); }
    &.c3 { background: linear-gradient(135deg, #14b8a6, #2dd4bf); }
    &.c4 { background: linear-gradient(135deg, #f59e0b, #fbbf24); }
    &.c5 { background: linear-gradient(135deg, #3b82f6, #60a5fa); }
  }

  .info {
    .uname { font-size: 13px; font-weight: 600; color: @text; line-height: 1.3; }
    .uaccount { font-size: 12px; color: @text3; line-height: 1.3; margin-top: 2px; }
  }
}

.email-text { color: @text2; font-size: 13px; }
.time-text { color: @text3; font-size: 12px; }

.role-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;

  &.admin {
    color: @primary-400;
    background: rgba(139, 92, 246, 0.15);
    border: 1px solid rgba(139, 92, 246, 0.25);
  }
  &.member {
    color: @text3;
    background: rgba(139, 92, 246, 0.06);
    border: 1px solid rgba(139, 92, 246, 0.1);
  }
}

.status-dot {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;

  &::before {
    content: '';
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  &.on { color: #34d399; &::before { background: #34d399; box-shadow: 0 0 6px rgba(52, 211, 153, 0.5); } }
  &.off { color: #f87171; &::before { background: #f87171; box-shadow: 0 0 6px rgba(248, 113, 113, 0.4); } }
}

.act-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.act-btn {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: rgba(139, 92, 246, 0.06);
  color: @text3;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 15px;

  &:hover { background: rgba(139, 92, 246, 0.15); color: @primary-400; border-color: rgba(139, 92, 246, 0.2); }
  &.edit:hover { color: @primary-400; }
  &.warn:hover { color: #fbbf24; background: rgba(251, 191, 36, 0.12); border-color: rgba(251, 191, 36, 0.2); }
  &.ok:hover { color: #34d399; background: rgba(52, 211, 153, 0.12); border-color: rgba(52, 211, 153, 0.2); }
  &.info:hover { color: #60a5fa; background: rgba(96, 165, 250, 0.12); border-color: rgba(96, 165, 250, 0.2); }
  &.del:hover { color: #f87171; background: rgba(248, 113, 113, 0.12); border-color: rgba(248, 113, 113, 0.2); }
}

// ===== 空状态 =====
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

  .empty-icon {
    width: 140px;
    height: 140px;
    margin-bottom: 24px;
    animation: float 3s ease-in-out infinite;
    @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
    svg { width: 100%; height: 100%; filter: drop-shadow(0 4px 16px rgba(139, 92, 246, 0.2)); }
  }

  h3 { margin: 0 0 8px; font-size: 18px; font-weight: 600; color: @text; }
  p { margin: 0 0 24px; font-size: 13px; color: @text3; line-height: 1.6; max-width: 400px; }
}

// ===== 分页 =====
.pager {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  padding: 12px 32px 16px;

  :deep(.ed-pagination), :deep(.el-pagination) {
    .ed-pagination__total, .el-pagination__total { color: @text3; font-size: 13px; }
    .ed-pager li, .el-pager li {
      background: rgba(139, 92, 246, 0.06) !important;
      color: @text2 !important;
      border-radius: 6px;
      &.is-active { background: @primary-600 !important; color: #fff !important; }
      &:hover:not(.is-active) { background: rgba(139, 92, 246, 0.15) !important; color: @primary-400 !important; }
    }
    .btn-prev, .btn-next {
      background: rgba(139, 92, 246, 0.06) !important;
      color: @text3 !important;
      border-radius: 6px;
      &:hover { background: rgba(139, 92, 246, 0.15) !important; color: @primary-400 !important; }
      &:disabled { opacity: 0.3; }
    }
    .ed-pagination__sizes, .el-pagination__sizes {
      .ed-input__wrapper, .el-input__wrapper {
        background: rgba(139, 92, 246, 0.06) !important;
        border: 1px solid rgba(139, 92, 246, 0.15) !important;
        box-shadow: none !important;
        border-radius: 6px;
      }
      .ed-input__inner, .el-input__inner { color: @text2 !important; font-size: 13px; }
    }
  }
}

// ===== 抽屉 =====
.w-full { width: 100%; }

.pwd-hint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(139, 92, 246, 0.08);
  border: 1px solid rgba(139, 92, 246, 0.15);
  border-radius: 10px;
  color: @text2;
  font-size: 13px;
  line-height: 1.5;
  margin-top: 8px;

  .el-icon { color: @primary-400; margin-top: 2px; flex-shrink: 0; }
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

// ===== 响应式 =====
@media (max-width: 768px) {
  .top-bar { padding: 16px 18px 12px; }
  .filter-row { flex-wrap: wrap; .search-box { max-width: 100%; width: 100%; } }
  .table-wrap { padding: 12px 18px 0; }
  .pager { padding: 10px 18px 12px; }
}
</style>

<style lang="less">
// 用户管理 - 抽屉全局样式（dark theme）
@bg2-user: #1a1225;
@border-user: rgba(139, 92, 246, 0.2);
@text-user: rgba(255, 255, 255, 0.95);
@text2-user: rgba(196, 181, 253, 0.8);
@text3-user: rgba(196, 181, 253, 0.5);
@primary-500-user: #8b5cf6;
@primary-600-user: #7c3aed;

.user-drawer {
  &.ed-drawer, &.el-drawer {
    background: @bg2-user !important;
    border-left: 1px solid @border-user !important;
  }

  .ed-drawer__header, .el-drawer__header {
    color: @text-user !important;
    border-bottom: 1px solid @border-user;
    padding: 16px 24px;
    margin-bottom: 0;

    .ed-drawer__title, .el-drawer__title { color: @text-user !important; font-weight: 600; font-size: 16px; }
    .ed-drawer__close-btn, .el-drawer__close-btn { color: @text3-user; &:hover { color: @text-user; } }
  }

  .ed-drawer__body, .el-drawer__body { padding: 24px; }

  .ed-drawer__footer, .el-drawer__footer {
    padding: 16px 24px;
    border-top: 1px solid @border-user;
  }

  .user-form {
    .ed-form-item__label, .el-form-item__label { color: @text2-user !important; font-size: 13px; font-weight: 500; }

    .ed-input__wrapper, .el-input__wrapper {
      background: rgba(139, 92, 246, 0.06) !important;
      border: 1px solid @border-user !important;
      border-radius: 9px;
      box-shadow: none !important;
      &:hover { border-color: rgba(139, 92, 246, 0.35) !important; }
      &.is-focus, &:focus-within { border-color: @primary-500-user !important; box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1) !important; }
    }
    .ed-input__inner, .el-input__inner { color: @text-user !important; &::placeholder { color: @text3-user !important; } }
    .ed-input.is-disabled .ed-input__wrapper, .el-input.is-disabled .el-input__wrapper { opacity: 0.5; }

    .ed-select .ed-input__wrapper, .el-select .el-input__wrapper {
      background: rgba(139, 92, 246, 0.06) !important;
      border: 1px solid @border-user !important;
      border-radius: 9px;
      box-shadow: none !important;
    }
  }

  .ed-button--default, .el-button--default {
    background: rgba(139, 92, 246, 0.1) !important;
    border: 1px solid @border-user !important;
    color: @text2-user !important;
    border-radius: 9px;
    &:hover { background: rgba(139, 92, 246, 0.2) !important; color: @text-user !important; }
  }
  .ed-button--primary, .el-button--primary {
    background: linear-gradient(135deg, @primary-600-user 0%, @primary-500-user 100%) !important;
    border: none !important;
    border-radius: 9px;
    box-shadow: 0 2px 10px rgba(139, 92, 246, 0.3);
    &:hover { box-shadow: 0 4px 16px rgba(139, 92, 246, 0.45); }
  }
}
</style>
