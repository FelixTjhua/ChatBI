<script lang="ts" setup>
import { nextTick, onMounted, reactive, ref, unref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus-secondary'
import icon_export_outlined from '@/assets/svg/icon_export_outlined.svg'
import { promptApi } from '@/api/prompt'
import { formatTimestamp } from '@/utils/date'
import { datasourceApi } from '@/api/datasource'
import icon_add_outlined from '@/assets/svg/icon_add_outlined.svg'
import IconOpeEdit from '@/assets/svg/icon_edit_outlined.svg'
import icon_copy_outlined from '@/assets/embedded/icon_copy_outlined.svg'
import IconOpeDelete from '@/assets/svg/icon_delete.svg'
import icon_searchOutline_outlined from '@/assets/svg/icon_search-outline_outlined.svg'
import EmptyBackground from '@/components/EmptyBackground.vue'
import { useClipboard } from '@vueuse/core'
import { useI18n } from 'vue-i18n'
import { cloneDeep } from 'lodash-es'
import { QuestionFilled } from '@element-plus/icons-vue'

interface Form {
  id?: string | null
  type: string | null
  prompt: string | null
  specific_ds: boolean
  datasource_ids: number[]
  datasource_names: string[]
  name: string | null
}

const { t } = useI18n()
const { copy } = useClipboard({ legacy: true })
const multipleSelectionAll = ref<any[]>([])
const keywords = ref('')
const oldKeywords = ref('')
const searchLoading = ref(false)
const currentType = ref('GENERATE_SQL')

const options = ref<any[]>([])
const selectable = () => {
  return true
}
onMounted(() => {
  // 清空之前的选中状态
  multipleSelectionAll.value = []
  checkAll.value = false
  isIndeterminate.value = false
  search()
})

const dialogFormVisible = ref<boolean>(false)
const multipleTableRef = ref()
const isIndeterminate = ref(false)
const checkAll = ref(false)
const fieldList = ref<any>([])
const pageInfo = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0,
})
const tableMaxHeight = computed(() => window.innerHeight - 260)

const dialogTitle = ref('')
const updateLoading = ref(false)
const defaultForm = {
  id: null,
  type: null,
  prompt: null,
  datasource_ids: [],
  datasource_names: [],
  name: null,
  specific_ds: false,
}
const pageForm = ref<Form>(cloneDeep(defaultForm))
const copyCode = () => {
  copy(pageForm.value.prompt!)
    .then(function () {
      ElMessage.success(t('common.copy_successful'))
    })
    .catch(function () {
      ElMessage.error(t('common.copy_failed'))
    })
}
const cancelDelete = () => {
  handleToggleRowSelection(false)
  multipleSelectionAll.value = []
  checkAll.value = false
  isIndeterminate.value = false
}

const exportExcel = () => {
  let title = ''
  if (currentType.value === 'GENERATE_SQL') {
    title = t('prompt.ask_sql')
  }
  if (currentType.value === 'ANALYSIS') {
    title = t('prompt.data_analysis')
  }
  if (currentType.value === 'PREDICT_DATA') {
    title = t('prompt.data_prediction')
  }
  ElMessageBox.confirm(t('prompt.all_236_terms', { msg: pageInfo.total, type: title }), {
    confirmButtonType: 'primary',
    confirmButtonText: t('professional.export'),
    cancelButtonText: t('common.cancel'),
    customClass: 'confirm-no_icon',
    autofocus: false,
    showClose: false,
  }).then(() => {
    searchLoading.value = true
    promptApi
      .export2Excel(currentType.value, keywords.value ? { name: keywords.value } : {})
      .then((res) => {
        const blob = new Blob([res], {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        const link = document.createElement('a')
        link.href = URL.createObjectURL(blob)
        link.download = `${title}.xlsx`
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
        searchLoading.value = false
      })
  }).catch(() => {})
}
const deleteBatchUser = () => {
  ElMessageBox.confirm(
    t('prompt.selected_prompt_words', { msg: multipleSelectionAll.value.length }),
    {
      confirmButtonType: 'danger',
      confirmButtonText: t('dashboard.delete'),
      cancelButtonText: t('common.cancel'),
      customClass: 'confirm-no_icon',
      autofocus: false,
      showClose: false,
    }
  ).then(() => {
    // 传递 prompt_type 参数消歧
    promptApi.deleteEmbedded(multipleSelectionAll.value.map((ele) => ele.id), currentType.value).then(() => {
      ElMessage({
        type: 'success',
        message: t('dashboard.delete_success'),
      })
      multipleSelectionAll.value = []
      search()
    }).catch(() => {
      ElMessage.error(t('common.save_failed'))
    })
  }).catch(() => {})
}
const deleteHandler = (row: any) => {
  ElMessageBox.confirm(t('prompt.prompt_word_name_de', { msg: row.name }), {
    confirmButtonType: 'danger',
    confirmButtonText: t('dashboard.delete'),
    cancelButtonText: t('common.cancel'),
    customClass: 'confirm-no_icon',
    autofocus: false,
    showClose: false,
  }).then(() => {
    // 传递 prompt_type 参数消歧
    promptApi.deleteEmbedded([row.id], currentType.value).then(() => {
      multipleSelectionAll.value = multipleSelectionAll.value.filter((ele) => row.id !== ele.id)
      ElMessage({
        type: 'success',
        message: t('dashboard.delete_success'),
      })
      search()
    }).catch(() => {
      ElMessage.error(t('common.save_failed'))
    })
  }).catch(() => {})
}
const handleSelectionChange = (val: any[]) => {
  if (toggleRowLoading.value) return
  const arr = fieldList.value.filter(selectable)
  const ids = arr.map((ele: any) => ele.id)
  multipleSelectionAll.value = [
    ...multipleSelectionAll.value.filter((ele: any) => !ids.includes(ele.id)),
    ...val,
  ]
  isIndeterminate.value = !(val.length === 0 || val.length === arr.length)
  checkAll.value = val.length === arr.length
}
const handleCheckAllChange = (val: any) => {
  isIndeterminate.value = false
  handleSelectionChange(val ? fieldList.value.filter(selectable) : [])
  if (val) {
    handleToggleRowSelection()
  } else {
    multipleTableRef.value.clearSelection()
  }
}

const toggleRowLoading = ref(false)

const handleToggleRowSelection = (check: boolean = true) => {
  toggleRowLoading.value = true
  const arr = fieldList.value.filter(selectable)
  let i = 0
  const ids = multipleSelectionAll.value.map((ele: any) => ele.id)
  for (const key in arr) {
    if (ids.includes((arr[key] as any).id)) {
      i += 1
      multipleTableRef.value.toggleRowSelection(arr[key], check)
    }
  }
  toggleRowLoading.value = false
  checkAll.value = i === arr.length
  isIndeterminate.value = !(i === 0 || i === arr.length)
}

const search = () => {
  searchLoading.value = true
  oldKeywords.value = keywords.value
  promptApi
    .getList(
      pageInfo.currentPage,
      pageInfo.pageSize,
      currentType.value,
      keywords.value
        ? {
            name: keywords.value,
          }
        : {}
    )
    .then((res: any) => {
      toggleRowLoading.value = true
      fieldList.value = res.data
      pageInfo.total = res.total_count
      searchLoading.value = false
      // 只有当有之前选中的项目时才恢复选中状态
      if (multipleSelectionAll.value.length > 0) {
        nextTick(() => {
          handleToggleRowSelection()
        })
      } else {
        toggleRowLoading.value = false
      }
    })
    .catch(() => {
      ElMessage.error(t('common.load_failed'))
    })
    .finally(() => {
      searchLoading.value = false
    })
}

const termFormRef = ref()
const validatePass = (_: any, value: any, callback: any) => {
  if (pageForm.value.specific_ds && !value.length) {
    callback(new Error(t('datasource.Please_select') + t('common.empty') + t('ds.title')))
  } else {
    callback()
  }
}
const rules = {
  name: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + t('prompt.prompt_word_name'),
    },
  ],
  datasource_ids: [
    {
      validator: validatePass,
      trigger: 'blur',
    },
  ],
  prompt: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + t('prompt.replaced_with'),
    },
  ],
}

const list = () => {
  datasourceApi.list().then((res: any) => {
    options.value = res || []
  }).catch(() => {
    options.value = []
  })
}

const saveHandler = () => {
  termFormRef.value.validate((res: any) => {
    if (res) {
      const obj = unref(pageForm)
      if (!obj.id) {
        delete obj.id
      }
      updateLoading.value = true
      promptApi
        .updateEmbedded(obj)
        .then(() => {
          ElMessage({
            type: 'success',
            message: t('common.save_success'),
          })
          search()
          onFormClose()
        })
        .catch(() => {
          ElMessage.error(t('common.save_failed'))
        })
        .finally(() => {
          updateLoading.value = false
        })
    }
  })
}

const editHandler = (row: any) => {
  // 先重置表单，再根据 row 填充
  pageForm.value = cloneDeep(defaultForm)
  pageForm.value.type = unref(currentType)
  if (row) {
    const cloned = cloneDeep(row)
    // 保留当前 tab 的 type，防止 row 中 type 为 null 覆盖
    if (!cloned.type) {
      cloned.type = unref(currentType)
    }
    pageForm.value = cloned
  }
  list()
  dialogTitle.value = row?.id ? t('prompt.edit_prompt_word') : t('prompt.add_prompt_word')
  dialogFormVisible.value = true
}

const onFormClose = () => {
  pageForm.value = cloneDeep(defaultForm)
  dialogFormVisible.value = false
}

const handleCurrentChange = (val: number) => {
  pageInfo.currentPage = val
  search()
}
const rowInfoDialog = ref(false)

const handleRowClick = (row: any) => {
  pageForm.value = cloneDeep(row)
  rowInfoDialog.value = true
}

const onRowFormClose = () => {
  pageForm.value = cloneDeep(defaultForm)
  rowInfoDialog.value = false
}

const handleChange = () => {
  termFormRef.value.validateField('datasource_ids')
}

const typeChange = (val: any) => {
  currentType.value = val
  pageInfo.currentPage = 1
  search()
}
</script>

<template>
  <div class="prompt" :class="{ 'has-selection': multipleSelectionAll?.length }">
    <!-- 页面头部：左侧标题，右侧状态面板 -->
    <div class="page-header">
      <div class="header-left-content">
        <div class="chatbi-page-title">
          <span class="title-text">{{ $t('prompt.customize_prompt_words') }}</span>
        </div>
      </div>
    </div>

    <!-- 类型选择和操作栏 -->
    <div class="tool-left">
      <!-- 第一行：类型选择按钮 + 说明卡片 -->
      <div class="type-row">
        <div class="btn-select">
          <el-tooltip :content="$t('prompt.ask_sql_desc')" placement="bottom">
            <el-button
              :class="[currentType === 'GENERATE_SQL' && 'is-active']"
              text
              @click="typeChange('GENERATE_SQL')"
            >
              {{ $t('prompt.ask_sql') }}
            </el-button>
          </el-tooltip>
          <el-tooltip :content="$t('prompt.data_analysis_desc')" placement="bottom">
            <el-button
              :class="[currentType === 'ANALYSIS' && 'is-active']"
              text
              @click="typeChange('ANALYSIS')"
            >
              {{ $t('prompt.data_analysis') }}
            </el-button>
          </el-tooltip>
          <el-tooltip :content="$t('prompt.data_prediction_desc')" placement="bottom">
            <el-button
              :class="[currentType === 'PREDICT_DATA' && 'is-active']"
              text
              @click="typeChange('PREDICT_DATA')"
            >
              {{ $t('prompt.data_prediction') }}
            </el-button>
          </el-tooltip>
        </div>
      </div>
      
      <!-- 第二行：搜索框和操作按钮 -->
      <div class="action-row">
        <el-input
          v-model="keywords"
          class="search-input"
          :placeholder="$t('dashboard.search')"
          clearable
          @keyup.enter="search"
          @clear="search"
        >
          <template #prefix>
            <el-icon>
              <icon_searchOutline_outlined />
            </el-icon>
          </template>
        </el-input>
        <el-button secondary @click="exportExcel">
          <template #icon>
            <icon_export_outlined />
          </template>
          {{ $t('professional.export_all') }}
        </el-button>
        <el-button type="primary" @click="editHandler(null)">
          <template #icon>
            <icon_add_outlined></icon_add_outlined>
          </template>
          {{ $t('prompt.add_prompt_word') }}
        </el-button>
      </div>
    </div>
    <div
      v-if="!searchLoading"
      class="table-content"
      :class="{ 'has-selection-bar': multipleSelectionAll?.length }"
    >
      <div class="preview-or-schema">
        <el-table
          ref="multipleTableRef"
          :data="fieldList"
          :max-height="tableMaxHeight"
          style="width: 100%"
          @row-click="handleRowClick"
          @selection-change="handleSelectionChange"
        >
          <el-table-column :selectable="selectable" type="selection" width="55" />
          <el-table-column prop="name" :label="$t('prompt.prompt_word_name')" width="300">
          </el-table-column>
          <el-table-column prop="prompt" :label="$t('prompt.prompt_word_content')" min-width="600">
            <template #default="scope">
              <div class="field-comment_d">
                <span :title="scope.row.prompt" class="notes-in_table">{{ scope.row.prompt }}</span>
              </div>
            </template>
          </el-table-column>

          <template #empty>
            <EmptyBackground
              v-if="!!oldKeywords && !fieldList.length"
              :description="$t('datasource.relevant_content_found')"
              img-type="tree"
            />
            <template v-if="!oldKeywords && !fieldList.length">
              <div class="empty-state">
                <EmptyBackground
                  class="datasource-yet"
                  :description="$t('prompt.empty_tip')"
                  img-type="noneWhite"
                />
                <el-button type="primary" class="empty-action" @click="editHandler(null)">
                  <template #icon>
                    <icon_add_outlined></icon_add_outlined>
                  </template>
                  {{ $t('prompt.empty_action') }}
                </el-button>
              </div>
            </template>
          </template>
        </el-table>
      </div>
    </div>

    <div v-if="fieldList.length" class="pagination-container">
      <el-pagination
        :current-page="pageInfo.currentPage"
        :page-size="10"
        :background="true"
        layout="total, prev, pager, next, jumper"
        :total="pageInfo.total"
        @current-change="handleCurrentChange"
      />
    </div>
    <div v-if="multipleSelectionAll.length" class="bottom-select">
      <el-checkbox
        v-model="checkAll"
        :indeterminate="isIndeterminate"
        @change="handleCheckAllChange"
      >
        {{ $t('datasource.select_all') }}
      </el-checkbox>

      <button class="danger-button" @click="deleteBatchUser">{{ $t('dashboard.delete') }}</button>

      <span class="selected">{{
        $t('user.selected_2_items', { msg: multipleSelectionAll.length })
      }}</span>

      <el-button text @click="cancelDelete">
        {{ $t('common.cancel') }}
      </el-button>
    </div>
  </div>

  <el-drawer
    v-model="dialogFormVisible"
    :title="dialogTitle"
    destroy-on-close
    size="600px"
    :before-close="onFormClose"
    class="prompt-add_drawer"
  >
    <el-form
      ref="termFormRef"
      :model="pageForm"
      label-width="180px"
      label-position="top"
      :rules="rules"
      class="form-content_error"
      @submit.prevent
    >
      <el-form-item prop="name">
        <template #label>
          <div class="form-label-with-tip">
            <span>{{ t('prompt.prompt_word_name') }}</span>
            <el-tooltip :content="$t('prompt.prompt_word_name_tip')" placement="top">
              <el-icon class="tip-icon"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </template>
        <el-input
          v-model="pageForm.name"
          :placeholder="$t('prompt.prompt_word_name_tip')"
          autocomplete="off"
          maxlength="50"
          clearable
        />
      </el-form-item>
      <el-form-item prop="prompt">
        <template #label>
          <div class="form-label-with-tip">
            <span>{{ t('prompt.prompt_word_content') }}</span>
            <el-tooltip :content="$t('prompt.prompt_word_content_tip')" placement="top">
              <el-icon class="tip-icon"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </template>
        <el-input
          v-model="pageForm.prompt"
          :placeholder="$t('prompt.replaced_with')"
          :autosize="{ minRows: 3.636, maxRows: 11.09 }"
          type="textarea"
        />
        <div class="tips">
          {{ t('prompt.loss_exercise_caution') }}
        </div>
      </el-form-item>

      <el-form-item
        class="is-required"
        :class="!pageForm.specific_ds && 'no-error'"
        prop="datasource_ids"
      >
        <template #label>
          <div class="form-label-with-tip">
            <span>{{ t('training.effective_data_sources') }}</span>
            <el-tooltip :content="$t('training.effective_data_sources_tip')" placement="top">
              <el-icon class="tip-icon"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </template>
        <el-radio-group v-model="pageForm.specific_ds">
          <el-radio :value="false">{{ $t('training.all_data_sources') }}</el-radio>
          <el-radio :value="true">{{ $t('training.partial_data_sources') }}</el-radio>
        </el-radio-group>
        <el-select
          v-if="pageForm.specific_ds"
          v-model="pageForm.datasource_ids"
          multiple
          filterable
          :placeholder="$t('datasource.Please_select') + $t('common.empty') + $t('ds.title')"
          style="width: 100%; margin-top: 8px"
          @change="handleChange"
        >
          <el-option v-for="item in options" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
      </el-form-item>


    </el-form>
    <template #footer>
      <div v-loading="updateLoading" class="dialog-footer">
        <el-button secondary @click="onFormClose">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="saveHandler">
          {{ $t('common.save') }}
        </el-button>
      </div>
    </template>
  </el-drawer>
  <el-drawer
    v-model="rowInfoDialog"
    :title="$t('menu.Details')"
    destroy-on-close
    size="600px"
    :before-close="onRowFormClose"
    class="prompt-term_drawer"
  >
    <el-form label-width="180px" label-position="top" class="form-content_error" @submit.prevent>
      <el-form-item :label="t('prompt.prompt_word_name')">
        <div class="content">
          {{ pageForm.name }}
        </div>
      </el-form-item>
      <el-form-item :label="t('prompt.prompt_word_content')">
        <div style="white-space: pre-wrap" class="content">
          {{ pageForm.prompt }}
        </div>
        <div class="copy-icon">
          <el-tooltip :offset="12" effect="dark" :content="t('datasource.copy')" placement="top">
            <el-icon class="hover-icon_with_bg" style="cursor: pointer" size="16" @click="copyCode">
              <icon_copy_outlined></icon_copy_outlined>
            </el-icon>
          </el-tooltip>
        </div>
      </el-form-item>
      <el-form-item :label="t('ds.title')">
        <div class="content">
          {{
            pageForm.datasource_names.length && pageForm.specific_ds
              ? pageForm.datasource_names.join()
              : t('training.all_data_sources')
          }}
        </div>
      </el-form-item>

    </el-form>
  </el-drawer>
</template>

<style lang="less" scoped>
// ChatBI 提示词管理页面 - 深色主题设计
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@primary-700: #6d28d9;
@dark-bg: #0f0a1a;
@dark-bg-secondary: #1a1225;
@dark-bg-card: rgba(26, 18, 37, 0.9);
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

.prompt {
  height: 100%;
  position: relative;
  padding: 16px 20px 0;  // 减少顶部和左右 padding，从 20px 24px 改为 16px 20px
  background: linear-gradient(180deg, @dark-bg 0%, @dark-bg-secondary 100%);
  overflow: hidden;
  display: flex;
  flex-direction: column;

  // 当有选中项时，为底部操作栏预留空间
  &.has-selection {
    padding-bottom: 0;
  }

  // 页面头部区域 - 左侧标题，右侧状态面板
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
    margin-bottom: 18px;
    flex-shrink: 0;

    .header-left-content {
      display: flex;
      align-items: center;
      flex-shrink: 0;
    }
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 40px 0;

    .datasource-yet {
      padding-bottom: 0;
      height: auto;
      padding-top: 40px;
    }

    .empty-action {
      margin-top: 16px;
    }
  }

  .form-label-with-tip {
    display: flex;
    align-items: center;
    gap: 6px;

    .tip-icon {
      color: @dark-text-muted;
      cursor: help;
      font-size: 14px;
      transition: color 0.2s;

      &:hover {
        color: @primary-400;
      }
    }
  }

  .all-ds-tag {
    color: @dark-text-muted;
    font-size: 12px;
  }

  .datasource-yet {
    padding-bottom: 0;
    height: auto;
    padding-top: 160px;
  }

  :deep(.ed-table__cell),
  :deep(.el-table__cell) {
    cursor: pointer;
  }

  .tool-left {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 16px;
    align-items: flex-start;  // 左对齐
    flex-shrink: 0;  // 防止工具栏被压缩

    .type-row {
      display: flex;
      align-items: center;
      gap: 14px;
      width: 100%;
    }

    .btn-select {
      height: 40px;
      display: inline-flex !important;
      padding: 4px;
      align-items: center;
      justify-content: flex-start;
      background: linear-gradient(145deg, rgba(26, 18, 37, 0.9) 0%, rgba(20, 14, 32, 0.95) 100%);
      backdrop-filter: blur(12px);
      border: 1px solid @dark-border;
      border-radius: 12px;
      width: auto !important;  // 强制自动宽度
      max-width: fit-content !important;  // 最大宽度适应内容
      flex-shrink: 0;
      overflow: hidden;  // 防止出现白色滚动条
      
      // 确保 tooltip 不影响宽度
      :deep(.el-tooltip__trigger),
      :deep(.ed-tooltip__trigger) {
        display: inline-flex;
        flex-shrink: 0;
      }

      .is-active {
        background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%);
        color: #fff !important;
        font-weight: 600;
        border-radius: 8px;
        box-shadow: 0 4px 14px rgba(139, 92, 246, 0.35);
      }

      :deep(.ed-button:not(.is-active)),
      :deep(.el-button:not(.is-active)) {
        color: #e9d5ff; // 浅紫色，确保可见
      }

      :deep(.ed-button.is-text),
      :deep(.el-button.is-text) {
        height: 32px;
        padding: 0 14px;
        line-height: 30px;
        font-size: 13px;
        transition: all 0.25s ease;
        border-radius: 8px;

        &:hover:not(.is-active) {
          background: rgba(139, 92, 246, 0.15);
          color: @primary-400;
        }
      }

      :deep(.ed-button + .ed-button),
      :deep(.el-button + .el-button) {
        margin-left: 4px;
      }
    }

    .action-row {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: nowrap;  // 不换行，保持在一行
      width: auto !important;  // 强制自动宽度
      justify-content: flex-start !important;  // 强制左对齐

      .search-input {
        width: 240px;
        min-width: 180px;
        flex-shrink: 1;
        
        :deep(.ed-input__wrapper),
        :deep(.el-input__wrapper) {
          background: rgba(139, 92, 246, 0.08);
          border: 1.5px solid @dark-border;
          border-radius: 10px;
          transition: all 0.25s ease;
          height: 36px;
          box-shadow: none;

          &:hover {
            border-color: rgba(139, 92, 246, 0.35);
          }

          &.is-focus {
            border-color: @primary-500;
            box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15);
          }
        }

        :deep(.ed-input__inner),
        :deep(.el-input__inner) {
          color: @dark-text;

          &::placeholder {
            color: #c4b5fd;
          }
        }
      }

      :deep(.ed-button.is-secondary),
      :deep(.el-button.is-secondary),
      :deep(.ed-button--default),
      :deep(.el-button--default) {
        background: rgba(139, 92, 246, 0.2);
        border: 1px solid rgba(139, 92, 246, 0.4);
        border-radius: 10px;
        height: 36px;
        color: #ffffff !important;
        transition: all 0.25s ease;

        &:hover {
          border-color: rgba(139, 92, 246, 0.6);
          background: rgba(139, 92, 246, 0.3);
          color: @primary-400;
        }
      }

      :deep(.ed-button--primary),
      :deep(.el-button--primary) {
        height: 36px;
        border-radius: 10px;
        background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%);
        border: none;
        box-shadow: 0 4px 14px rgba(139, 92, 246, 0.35);

        &:hover {
          background: linear-gradient(135deg, @primary-500 0%, @primary-400 100%);
          box-shadow: 0 6px 20px rgba(139, 92, 246, 0.45);
          transform: translateY(-1px);
        }
      }
    }
  }

  .pagination-container {
    display: flex;
    justify-content: end;
    align-items: center;
    padding: 16px 0;
    flex-shrink: 0;  // 防止分页器被压缩

    :deep(.ed-pagination),
    :deep(.el-pagination) {
      .ed-pager li,
      .el-pager li {
        background: rgba(139, 92, 246, 0.08);
        color: @dark-text-secondary;
        border: 1px solid @dark-border;
        border-radius: 8px;

        &.is-active {
          background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%);
          color: #fff;
          border-color: transparent;
          box-shadow: 0 2px 8px rgba(139, 92, 246, 0.35);
        }

        &:hover:not(.is-active) {
          color: @primary-400;
          border-color: rgba(139, 92, 246, 0.35);
        }
      }

      .btn-prev,
      .btn-next {
        background: rgba(139, 92, 246, 0.08);
        border: 1px solid @dark-border;
        color: @dark-text-secondary;
        border-radius: 8px;

        &:hover {
          color: @primary-400;
          border-color: rgba(139, 92, 246, 0.35);
        }
      }

      .ed-pagination__total,
      .el-pagination__total,
      .ed-pagination__jump,
      .el-pagination__jump {
        color: #ffffff; // 白色，确保可见
      }

      .ed-pagination__sizes,
      .el-pagination__sizes {
        .ed-select .ed-select__wrapper,
        .el-select .el-input__wrapper {
          background: rgba(139, 92, 246, 0.15);
          border: 1px solid rgba(139, 92, 246, 0.4);
          border-radius: 8px;

          .ed-select__selected-item,
          .el-select__selected-item,
          .ed-input__inner,
          .el-input__inner {
            color: #ffffff !important;
          }
        }
      }

      .ed-pagination__editor,
      .el-pagination__editor {
        .ed-input__wrapper,
        .el-input__wrapper {
          background: rgba(139, 92, 246, 0.15);
          border: 1px solid rgba(139, 92, 246, 0.4);

          .ed-input__inner,
          .el-input__inner {
            color: #ffffff !important;
          }
        }
      }
    }
  }

  .table-content {
    flex: 1;  // 占据剩余空间
    overflow-y: auto;
    background: linear-gradient(145deg, rgba(26, 18, 37, 0.7) 0%, rgba(20, 14, 32, 0.8) 100%);
    backdrop-filter: blur(12px);
    border: 1.5px solid @dark-border;
    border-radius: 14px;
    position: relative;  // 为 absolute 定位提供上下文
    min-height: 200px;  // 最小高度
    margin-bottom: 0;  // 移除底部边距
    padding-bottom: 0;  // 默认无底部内边距
    
    // 当有选中项时，为底部操作栏预留空间
    &.has-selection-bar {
      padding-bottom: 70px;  // 60px操作栏高度 + 10px缓冲
    }

    &::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }

    &::-webkit-scrollbar-track {
      background: rgba(139, 92, 246, 0.05);
    }

    &::-webkit-scrollbar-thumb {
      background: linear-gradient(
        180deg,
        rgba(139, 92, 246, 0.35) 0%,
        rgba(168, 85, 247, 0.25) 100%
      );
      border-radius: 3px;

      &:hover {
        background: linear-gradient(
          180deg,
          rgba(139, 92, 246, 0.5) 0%,
          rgba(168, 85, 247, 0.4) 100%
        );
      }
    }

    .preview-or-schema {
      :deep(.ed-table),
      :deep(.el-table) {
        --ed-table-border-color: @dark-border;
        --el-table-border-color: @dark-border;
        --ed-table-bg-color: transparent;
        --el-table-bg-color: transparent;
        --ed-table-tr-bg-color: transparent;
        --el-table-tr-bg-color: transparent;
        --ed-table-header-bg-color: rgba(139, 92, 246, 0.08);
        --el-table-header-bg-color: rgba(139, 92, 246, 0.08);
        background: transparent !important;
        font-size: 13px;

        &::before {
          display: none;
        }

        th.ed-table__cell,
        th.el-table__cell {
          background: rgba(139, 92, 246, 0.08) !important;
          color: @dark-text-secondary !important;
          font-weight: 600;
          font-size: 12px;
          border-bottom: 1px solid @dark-border !important;
          padding: 12px 0;
        }

        td.ed-table__cell,
        td.el-table__cell {
          background: transparent !important;
          border-bottom: 1px solid rgba(139, 92, 246, 0.1) !important;
          padding: 12px 0;

          .cell {
            color: @dark-text !important;
          }
        }

        tr:hover > td {
          background: rgba(139, 92, 246, 0.08) !important;
        }

        .ed-table__row:last-child td,
        .el-table__row:last-child td {
          border-bottom: none !important;
        }

        .ed-checkbox,
        .el-checkbox {
          --el-checkbox-checked-bg-color: @primary-600;
          --el-checkbox-checked-border-color: @primary-600;
          --ed-checkbox-checked-bg-color: @primary-600;
          --ed-checkbox-checked-border-color: @primary-600;
        }
      }

      .field-comment_d {
        display: flex;
        align-items: center;
        min-height: 24px;
      }

      .notes-in_table {
        max-width: 100%;
        display: -webkit-box;
        max-height: 44px;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
        overflow: hidden;
        text-overflow: ellipsis;
        word-break: break-word;
        white-space: pre-wrap;
        color: @dark-text;
        font-size: 13px;
      }

      .ed-icon,
      .el-icon {
        color: #e9d5ff; // 浅紫色，确保可见
      }

      .user-status-container {
        display: flex;
        align-items: center;
        font-weight: 400;
        font-size: 13px;
        line-height: 20px;
        height: 24px;
        color: @dark-text;

        .ed-icon,
        .el-icon {
          margin-left: 8px;
        }
      }

      .field-comment {
        height: 24px;
        display: flex;
        align-items: center;
        gap: 8px;

        .ed-icon,
        .el-icon {
          position: relative;
          cursor: pointer;
          transition: all 0.25s ease;
          width: 28px;
          height: 28px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(139, 92, 246, 0.1);
          border-radius: 6px;
          border: 1px solid @dark-border;

          &:not(.not-allow):hover {
            color: @primary-400;
            background: rgba(139, 92, 246, 0.2);
            border-color: rgba(139, 92, 246, 0.35);
            transform: translateY(-1px);
          }

          &.not-allow {
            cursor: not-allowed;
            opacity: 0.5;
          }
        }

        .ed-icon + .ed-icon,
        .el-icon + .el-icon {
          margin-left: 0;
        }
      }

      .preview-num {
        margin: 12px 0;
        font-weight: 400;
        font-size: 13px;
        line-height: 20px;
        color: #e9d5ff; // 浅紫色，确保可见
      }
    }
  }

  .bottom-select {
    position: absolute;
    height: 60px;
    left: 0;
    right: 0;
    bottom: 0;  // 相对于 .table-content 的底部
    border-top: 1px solid @dark-border;
    display: flex;
    background: linear-gradient(145deg, rgba(26, 18, 37, 0.98) 0%, rgba(20, 14, 32, 0.99) 100%);
    backdrop-filter: blur(20px);
    align-items: center;
    padding: 0 24px;
    z-index: 100;
    gap: 16px;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.3);
    border-radius: 0 0 14px 14px;  // 匹配表格容器的圆角

    :deep(.ed-checkbox),
    :deep(.el-checkbox) {
      .ed-checkbox__inner,
      .el-checkbox__inner {
        background: rgba(139, 92, 246, 0.08);
        border-color: @dark-border;
      }

      &.is-checked {
        .ed-checkbox__inner,
        .el-checkbox__inner {
          background: @primary-600;
          border-color: @primary-600;
        }
      }
    }

    :deep(.ed-checkbox__label),
    :deep(.el-checkbox__label) {
      color: @dark-text-secondary;
      font-weight: 500;
    }

    .selected {
      color: @dark-text-muted;
      font-size: 13px;
      margin-left: auto;
    }

    .danger-button {
      border: 1px solid rgba(239, 68, 68, 0.3);
      color: #f87171;
      min-width: 80px;
      height: 36px;
      padding: 0 16px;
      cursor: pointer;
      background: rgba(239, 68, 68, 0.1);
      font-weight: 500;
      transition: all 0.25s ease;
      border-radius: 8px;
      font-size: 14px;

      &:hover {
        background: rgba(239, 68, 68, 0.2);
        border-color: rgba(239, 68, 68, 0.5);
      }
    }

    :deep(.el-button--text) {
      color: @dark-text-secondary;

      &:hover {
        color: @primary-400;
      }
    }

    .selected {
      font-weight: 400;
      font-size: 13px;
      line-height: 20px;
      color: #e9d5ff; // 浅紫色，确保可见
    }

    :deep(.ed-button.is-text),
    :deep(.el-button.is-text) {
      color: #e9d5ff; // 浅紫色，确保可见

      &:hover {
        color: @primary-400;
      }
    }
  }
}

// 响应式适配
@media (max-width: 1024px) {
  .prompt {
    padding: 14px 18px 0;  // 平板上也减少 padding

    .page-header {
      margin-bottom: 16px;
    }

    .tool-left {
      .btn-select {
        // 保持紧凑，不要占满宽度
        width: auto;
        justify-content: flex-start;
        overflow: hidden;
        border-radius: 10px;
      }

      .action-row {
        // 保持左对齐，不要占满宽度
        width: auto;
        justify-content: flex-start;
      }
    }

    .table-content {
      border-radius: 12px;
    }
  }
}

@media (max-width: 768px) {
  .prompt {
    padding: 12px 12px 0;

    .page-header {
      margin-bottom: 14px;
    }

    .tool-left {
      gap: 10px;
      
      .btn-select {
        // 小屏幕时可以占满宽度，但保持左对齐
        width: 100%;
        justify-content: flex-start;
      }
      
      .action-row {
        flex-direction: column;
        align-items: stretch;

        .search-input {
          width: 100% !important;
        }

        :deep(.ed-button),
        :deep(.el-button) {
          width: 100%;
        }
      }
    }
    
    .table-content {
      border-radius: 10px;
      
      &.has-selection-bar {
        padding-bottom: 60px;  // 50px操作栏高度 + 10px缓冲
      }
    }
    
    .pagination-container {
      padding: 12px 0;
    }

    .bottom-select {
      height: 50px;
      padding-left: 12px;
      gap: 10px;

      .danger-button {
        min-width: 60px;
        font-size: 12px;
      }
    }
  }
}


</style>
<style lang="less">
// ChatBI 提示词抽屉 - 深色主题设计
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@dark-bg-secondary: #1a1225;
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

// 提示词页面标题由全局 page-titles.less 提供统一样式

.prompt-term_drawer {
  .ed-drawer,
  .el-drawer {
    border-radius: 0;
    background: @dark-bg-secondary !important;
  }

  .ed-drawer__header,
  .el-drawer__header {
    padding: 22px 26px;
    border-bottom: 1px solid @dark-border;
    background: linear-gradient(90deg, rgba(139, 92, 246, 0.08) 0%, transparent 100%);

    .ed-drawer__title,
    .el-drawer__title {
      color: @dark-text;
      font-size: 16px;
      font-weight: 600;
    }
  }

  .ed-drawer__body,
  .el-drawer__body {
    padding: 26px;
    background: @dark-bg-secondary;
  }

  .ed-form-item--label-top .ed-form-item__label,
  .el-form-item--label-top .el-form-item__label {
    margin-bottom: 4px;
  }

  .ed-form-item__label,
  .el-form-item__label {
    color: #e9d5ff; // 浅紫色，确保可见
    font-size: 13px;
    font-weight: 500;
  }

  .content {
    width: 100%;
    line-height: 22px;
    word-break: break-all;
    color: @dark-text;
    font-size: 13px;
    padding: 12px 16px;
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid @dark-border;
    border-radius: 10px;
  }

  .copy-icon {
    position: absolute;
    right: 0;
    top: -27px;

    .hover-icon_with_bg {
      color: #e9d5ff; // 浅紫色，确保可见
      transition: all 0.25s ease;
      padding: 6px;
      background: rgba(139, 92, 246, 0.1);
      border-radius: 6px;

      &:hover {
        color: @primary-400;
        background: rgba(139, 92, 246, 0.2);
      }
    }
  }
}

.ed-drawer.prompt-add_drawer,
.el-drawer.prompt-add_drawer,
.ed-drawer.prompt-term_drawer,
.el-drawer.prompt-term_drawer {
  border-radius: 0;
  background: @dark-bg-secondary !important;

  .ed-drawer__header,
  .el-drawer__header {
    padding: 22px 26px;
    border-bottom: 1px solid @dark-border;
    background: linear-gradient(90deg, rgba(139, 92, 246, 0.08) 0%, transparent 100%);

    .ed-drawer__title,
    .el-drawer__title {
      color: @dark-text;
      font-size: 16px;
      font-weight: 600;
    }
  }

  .ed-drawer__body,
  .el-drawer__body {
    padding: 26px;
    background: @dark-bg-secondary;
  }

  .ed-drawer__footer,
  .el-drawer__footer {
    padding: 18px 26px;
    border-top: 1px solid @dark-border;
    background: rgba(26, 18, 37, 0.95);
  }

  .ed-form-item__label,
  .el-form-item__label {
    color: @dark-text-secondary;
    font-size: 13px;
    font-weight: 500;
  }

  .tips {
    font-weight: 400;
    font-size: 13px;
    line-height: 20px;
    color: #fbbf24;
    background: rgba(251, 191, 36, 0.1);
    padding: 10px 14px;
    margin-top: 10px;
    border: 1px solid rgba(251, 191, 36, 0.25);
    border-radius: 10px;
  }

  .no-error.no-error {
    .ed-form-item__error,
    .el-form-item__error {
      display: none;
    }
    margin-bottom: 16px;
  }

  .ed-textarea__inner,
  .el-textarea__inner {
    line-height: 22px;
    border-radius: 10px;
    background: rgba(139, 92, 246, 0.08) !important;
    border: 1.5px solid @dark-border !important;
    color: @dark-text !important;
    box-shadow: none !important;

    &::placeholder {
      color: #c4b5fd !important; // 浅紫色，确保可见
    }

    &:hover {
      border-color: rgba(139, 92, 246, 0.35) !important;
    }

    &:focus {
      border-color: @primary-500 !important;
      box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15) !important;
    }
  }

  .ed-input__wrapper,
  .el-input__wrapper {
    border-radius: 10px;
    background: rgba(139, 92, 246, 0.08) !important;
    border: 1.5px solid @dark-border !important;
    box-shadow: none !important;

    &:hover {
      border-color: rgba(139, 92, 246, 0.35) !important;
    }

    &.is-focus {
      border-color: @primary-500 !important;
      box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15) !important;
    }
  }

  .ed-input__inner,
  .el-input__inner {
    color: @dark-text !important;

    &::placeholder {
      color: #c4b5fd !important; // 浅紫色，确保可见
    }
  }

  .ed-select .ed-select__wrapper,
  .el-select .el-select__wrapper,
  .el-select .el-input__wrapper {
    border-radius: 10px;
    background: rgba(139, 92, 246, 0.08) !important;
    border: 1.5px solid @dark-border;
    box-shadow: none !important;

    &:hover {
      border-color: rgba(139, 92, 246, 0.35);
    }

    &.is-focus,
    &.is-focused {
      border-color: @primary-500 !important;
      box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15) !important;
    }
  }

  // Radio 深色主题
  .ed-radio-group,
  .el-radio-group {
    .ed-radio,
    .el-radio {
      color: @dark-text-secondary;

      .ed-radio__inner,
      .el-radio__inner {
        background: rgba(139, 92, 246, 0.08);
        border-color: @dark-border;
      }

      &.is-checked {
        .ed-radio__inner,
        .el-radio__inner {
          background: @primary-600;
          border-color: @primary-600;
        }

        .ed-radio__label,
        .el-radio__label {
          color: @primary-400;
        }
      }
    }
  }

  // 多选标签深色主题
  .ed-tag,
  .el-tag {
    background: rgba(139, 92, 246, 0.2);
    border-color: rgba(139, 92, 246, 0.3);
    color: @primary-400;

    .ed-tag__close,
    .el-tag__close {
      color: @primary-400;

      &:hover {
        background: rgba(139, 92, 246, 0.3);
        color: #fff;
      }
    }
  }

  // 按钮深色主题
  .ed-button--default,
  .el-button--default {
    background: rgba(139, 92, 246, 0.1);
    border-color: @dark-border;
    color: @dark-text-secondary;

    &:hover {
      background: rgba(139, 92, 246, 0.18);
      border-color: rgba(139, 92, 246, 0.35);
      color: @primary-400;
    }
  }

  .ed-button--primary,
  .el-button--primary {
    background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%);
    border: none;
    box-shadow: 0 4px 14px rgba(139, 92, 246, 0.35);

    &:hover {
      background: linear-gradient(135deg, @primary-500 0%, @primary-400 100%);
      box-shadow: 0 6px 20px rgba(139, 92, 246, 0.45);
    }
  }
}
</style>
