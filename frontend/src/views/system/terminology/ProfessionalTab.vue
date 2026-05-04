<script lang="ts" setup>
import { nextTick, onMounted, reactive, ref, unref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus-secondary'
import icon_export_outlined from '@/assets/svg/icon_export_outlined.svg'
import { professionalApi } from '@/api/professional'
import { formatTimestamp } from '@/utils/date'
import icon_add_outlined from '@/assets/svg/icon_add_outlined.svg'
import IconOpeEdit from '@/assets/svg/operate/ope-edit.svg'
import IconOpeDelete from '@/assets/svg/operate/ope-delete.svg'
import icon_searchOutline_outlined from '@/assets/svg/icon_search-outline_outlined.svg'
import EmptyBackground from '@/components/EmptyBackground.vue'
import { useI18n } from 'vue-i18n'
import { cloneDeep } from 'lodash-es'

interface Form {
  id?: string | null
  word: string | null
  other_words: string[]
  description: string | null
  create_time?: number | null
}

const { t } = useI18n()
const multipleSelectionAll = ref<any[]>([])
const keywords = ref('')
const oldKeywords = ref('')
const searchLoading = ref(false)

const selectable = () => true

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
const pageInfo = reactive({ currentPage: 1, pageSize: 10, total: 0 })
const tableMaxHeight = computed(() => window.innerHeight - 320)
const dialogTitle = ref('')
const updateLoading = ref(false)
const defaultForm = {
  id: null,
  word: null,
  description: null,
  other_words: [''],
  create_time: null,
}
const pageForm = ref<Form>(cloneDeep(defaultForm))

const cancelDelete = () => {
  handleToggleRowSelection(false)
  multipleSelectionAll.value = []
  checkAll.value = false
  isIndeterminate.value = false
}

const exportExcel = () => {
  ElMessageBox.confirm(t('professional.all_236_terms', { msg: pageInfo.total }), {
    confirmButtonType: 'primary',
    confirmButtonText: t('professional.export'),
    cancelButtonText: t('common.cancel'),
    customClass: 'confirm-no_icon',
    autofocus: false,
    showClose: false,
  }).then(() => {
    searchLoading.value = true
    professionalApi
      .export2Excel(keywords.value ? { word: keywords.value } : {})
      .then((res) => {
        const blob = new Blob([res], {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        const link = document.createElement('a')
        link.href = URL.createObjectURL(blob)
        link.download = `${t('professional.professional_terminology')}.xlsx`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
      })
      .catch(() => {
        ElMessage.error(t('common.save_failed'))
      })
      .finally(() => {
        searchLoading.value = false
      })
  }).catch(() => {})
}

const deleteBatch = () => {
  ElMessageBox.confirm(
    t('professional.selected_2_terms', { msg: multipleSelectionAll.value.length }),
    {
      confirmButtonType: 'danger',
      confirmButtonText: t('dashboard.delete'),
      cancelButtonText: t('common.cancel'),
      customClass: 'confirm-no_icon',
      autofocus: false,
      showClose: false,
    }
  ).then(() => {
    professionalApi.deleteEmbedded(multipleSelectionAll.value.map((ele) => ele.id)).then(() => {
      ElMessage({ type: 'success', message: t('dashboard.delete_success') })
      multipleSelectionAll.value = []
      search()
    }).catch(() => {
      ElMessage.error(t('common.save_failed'))
    })
  }).catch(() => {})
}

const deleteHandler = (row: any) => {
  ElMessageBox.confirm(t('professional.the_term_gmv', { msg: row.word }), {
    confirmButtonType: 'danger',
    confirmButtonText: t('dashboard.delete'),
    cancelButtonText: t('common.cancel'),
    customClass: 'confirm-no_icon',
    autofocus: false,
    showClose: false,
  }).then(() => {
    professionalApi.deleteEmbedded([row.id]).then(() => {
      multipleSelectionAll.value = multipleSelectionAll.value.filter((ele) => row.id !== ele.id)
      ElMessage({ type: 'success', message: t('dashboard.delete_success') })
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
  professionalApi
    .getList(
      pageInfo.currentPage,
      pageInfo.pageSize,
      keywords.value ? { word: keywords.value } : {}
    )
    .then((res) => {
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

const rules = computed(() => ({
  word: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + t('professional.term_name'),
    },
  ],
  description: [
    {
      required: true,
      message:
        t('datasource.please_enter') + t('common.empty') + t('professional.term_description'),
    },
  ],
}))

const saveHandler = () => {
  termFormRef.value.validate((res: any) => {
    if (res) {
      const arr = [...pageForm.value.other_words.filter((ele: any) => !!ele), pageForm.value.word]
      if (arr.length !== new Set(arr).size) {
        return ElMessage.error(t('professional.cannot_be_repeated'))
      }
      const obj = unref(pageForm)
      if (!obj.id) delete obj.id
      updateLoading.value = true
      professionalApi
        .updateEmbedded(obj)
        .then(() => {
          ElMessage({ type: 'success', message: t('common.save_success') })
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
  pageForm.value.id = null
  if (row) {
    pageForm.value = cloneDeep(row)
    if (!pageForm.value.other_words.length) {
      pageForm.value.other_words = ['']
    }
  }
  dialogTitle.value = row?.id
    ? t('professional.editing_terminology')
    : t('professional.create_new_term')
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

const deleteHandlerItem = (idx: number) => {
  pageForm.value.other_words = pageForm.value.other_words!.filter((_, index) => index !== idx)
}

const changeStatus = (id: any, val: any) => {
  professionalApi
    .enable(id, val + '')
    .then(() => {
      ElMessage({ message: t('common.save_success'), type: 'success' })
    })
    .catch(() => {
      ElMessage.error(t('common.save_failed'))
    })
    .finally(() => {
      search()
    })
}
</script>

<template>
  <div v-loading="searchLoading" class="tab-content" :class="{ 'has-selection': multipleSelectionAll?.length }">
    <div class="tab-toolbar">
      <el-input
        v-model="keywords"
        class="search-input"
        :placeholder="t('professional.search_term')"
        clearable
        @keyup.enter="search"
        @clear="search"
      >
        <template #prefix
          ><el-icon><icon_searchOutline_outlined /></el-icon
        ></template>
      </el-input>
      <el-button @click="exportExcel">
        <template #icon><icon_export_outlined /></template>{{ t('professional.export_all') }}
      </el-button>
      <el-button type="primary" @click="editHandler(null)">
        <template #icon><icon_add_outlined /></template>{{ t('professional.create_new_term') }}
      </el-button>
    </div>

    <div class="tab-table" :class="{ 'has-selection-bar': multipleSelectionAll.length }">
      <el-table
        ref="multipleTableRef"
        :data="fieldList"
        :max-height="tableMaxHeight"
        class="dark-table"
        style="width: 100%"
        table-layout="fixed"
        @row-click="handleRowClick"
        @selection-change="handleSelectionChange"
      >
        <el-table-column :selectable="selectable" type="selection" width="55" />
        <el-table-column
          prop="word"
          :label="t('professional.term_name')"
          width="200"
          show-overflow-tooltip
        />
        <el-table-column
          :label="t('professional.synonyms')"
          width="300"
          show-overflow-tooltip
        >
          <template #default="scope">
            <span v-if="scope.row.other_words?.filter((e: any) => !!e).length" style="color: rgba(139, 92, 246, 0.85)">
              {{ scope.row.other_words.join(', ') }}
            </span>
            <span v-else style="color: rgba(255, 255, 255, 0.3); font-style: italic">-</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="description"
          :label="t('professional.term_description')"
          min-width="400"
          show-overflow-tooltip
        />
        <template #empty>
          <EmptyBackground
            v-if="!oldKeywords && !fieldList.length"
            :description="t('professional.no_term')"
            img-type="noneWhite"
          />
          <EmptyBackground
            v-if="!!oldKeywords && !fieldList.length"
            :description="t('datasource.relevant_content_found')"
            img-type="tree"
          />
        </template>
      </el-table>
    </div>

    <div v-if="fieldList.length" class="tab-pagination">
      <el-pagination
        :current-page="pageInfo.currentPage"
        :page-size="10"
        :background="true"
        layout="total, prev, pager, next, jumper"
        :total="pageInfo.total"
        @current-change="handleCurrentChange"
      />
    </div>

    <div v-if="multipleSelectionAll.length" class="selection-bar">
      <el-checkbox
        v-model="checkAll"
        :indeterminate="isIndeterminate"
        @change="handleCheckAllChange"
        >{{ t('datasource.select_all') }}</el-checkbox
      >
      <el-button type="danger" size="small" @click="deleteBatch">{{
        t('dashboard.delete')
      }}</el-button>
      <span class="selected-text">{{
        t('user.selected_2_items', { msg: multipleSelectionAll.length })
      }}</span>
      <el-button text size="small" @click="cancelDelete">{{ t('common.cancel') }}</el-button>
    </div>
  </div>

  <el-drawer
    v-model="dialogFormVisible"
    :title="dialogTitle"
    destroy-on-close
    size="600px"
    :before-close="onFormClose"
  >
    <el-form
      ref="termFormRef"
      :model="pageForm"
      label-position="top"
      :rules="rules"
      @submit.prevent
    >
      <el-form-item prop="word" :label="t('professional.term_name')">
        <el-input
          v-model="pageForm.word"
          :placeholder="t('datasource.please_enter')"
          maxlength="50"
          clearable
        />
      </el-form-item>
      <el-form-item prop="description" :label="t('professional.term_description')">
        <el-input
          v-model="pageForm.description"
          :placeholder="t('datasource.please_enter')"
          :autosize="{ minRows: 3, maxRows: 10 }"
          type="textarea"
        />
      </el-form-item>
      <el-form-item :label="t('professional.synonyms')">
        <div style="width: 100%">
          <div
            v-for="(_, index) in pageForm.other_words"
            :key="index"
            style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px"
          >
            <el-input
              v-model="pageForm.other_words[index]"
              :placeholder="t('datasource.please_enter')"
              maxlength="100"
              clearable
              style="flex: 1"
            />
            <el-button text type="danger" @click="deleteHandlerItem(index)"
              ><el-icon><IconOpeDelete /></el-icon
            ></el-button>
          </div>
          <el-button text type="primary" @click="pageForm.other_words.push('')">
            <el-icon style="margin-right: 4px"><icon_add_outlined /></el-icon>{{ t('model.add') }}
          </el-button>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="onFormClose">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="updateLoading" @click="saveHandler">{{
        t('common.save')
      }}</el-button>
    </template>
  </el-drawer>

  <el-drawer
    v-model="rowInfoDialog"
    :title="t('professional.professional_term_details')"
    destroy-on-close
    size="600px"
    :before-close="onRowFormClose"
  >
    <el-descriptions :column="1" border>
      <el-descriptions-item :label="t('professional.business_term')">{{
        pageForm.word
      }}</el-descriptions-item>
      <el-descriptions-item :label="t('professional.synonyms')">{{
        pageForm.other_words?.join(',') || '-'
      }}</el-descriptions-item>
      <el-descriptions-item :label="t('professional.term_description')">{{
        pageForm.description
      }}</el-descriptions-item>
      <el-descriptions-item :label="t('dashboard.create_time')">{{
        pageForm.create_time ? formatTimestamp(pageForm.create_time, 'YYYY-MM-DD HH:mm:ss') : '-'
      }}</el-descriptions-item>
    </el-descriptions>
  </el-drawer>
</template>

<style lang="less" scoped>
@import './tab-common.less';

// 过渡动画
.fade-enter-active,
.fade-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>

<style lang="less">
/* 强制表格深色主题 - 非 scoped 样式确保穿透到 Element Plus Secondary */
.tab-table {
  .ed-table,
  .el-table {
    --ed-table-bg-color: transparent !important;
    --ed-table-tr-bg-color: transparent !important;
    --ed-fill-color-blank: transparent !important;
    --ed-bg-color: transparent !important;
    background-color: transparent !important;
    background: transparent !important;
  }

  .ed-table__inner-wrapper,
  .el-table__inner-wrapper {
    background-color: transparent !important;
    background: transparent !important;
  }

  .ed-table__header-wrapper,
  .el-table__header-wrapper {
    background-color: transparent !important;
    background: transparent !important;

    table {
      background-color: transparent !important;
      background: transparent !important;
    }
  }

  .ed-table__body-wrapper,
  .el-table__body-wrapper {
    background-color: transparent !important;
    background: transparent !important;
  }

  .ed-scrollbar,
  .el-scrollbar,
  .ed-scrollbar__wrap,
  .el-scrollbar__wrap,
  .ed-scrollbar__view,
  .el-scrollbar__view {
    background-color: transparent !important;
    background: transparent !important;
  }

  table {
    background-color: transparent !important;
    background: transparent !important;
  }

  tbody {
    background-color: transparent !important;
    background: transparent !important;
  }

  tr {
    background-color: transparent !important;
    background: transparent !important;
  }

  .ed-table__row,
  .el-table__row {
    background-color: transparent !important;
    background: transparent !important;
  }

  th.ed-table__cell,
  th.el-table__cell {
    background-color: rgba(139, 92, 246, 0.12) !important;
    background: rgba(139, 92, 246, 0.12) !important;
    color: rgba(196, 181, 253, 0.8) !important;
    border-bottom: 1px solid rgba(139, 92, 246, 0.2) !important;

    .cell {
      color: rgba(196, 181, 253, 0.8) !important;
    }
  }

  td.ed-table__cell,
  td.el-table__cell {
    background-color: transparent !important;
    background: transparent !important;
    color: rgba(255, 255, 255, 0.95) !important;
    border-bottom: 1px solid rgba(139, 92, 246, 0.1) !important;

    .cell {
      color: rgba(255, 255, 255, 0.95) !important;
    }
  }

  .ed-table__row:hover > td.ed-table__cell,
  .el-table__row:hover > td.el-table__cell,
  tr:hover > td.ed-table__cell,
  tr:hover > td.el-table__cell,
  tr.hover-row > td.ed-table__cell,
  tr.hover-row > td.el-table__cell {
    background-color: rgba(139, 92, 246, 0.1) !important;
    background: rgba(139, 92, 246, 0.1) !important;
  }

  .ed-table__empty-block,
  .el-table__empty-block {
    background-color: transparent !important;
    background: transparent !important;
  }
}

/* 强制 Descriptions 深色主题 - 非 scoped 样式 */
.el-drawer__body,
.ed-drawer__body {
  .el-descriptions,
  .ed-descriptions {
    background: transparent !important;
    
    &.is-bordered {
      background: linear-gradient(145deg, rgba(26, 18, 37, 0.5) 0%, rgba(20, 14, 32, 0.6) 100%) !important;
      border: 1px solid rgba(139, 92, 246, 0.2) !important;
      border-radius: 12px !important;
      overflow: hidden !important;
    }
    
    .el-descriptions__table,
    .ed-descriptions__table {
      background: transparent !important;
    }
    
    .el-descriptions__body,
    .ed-descriptions__body {
      background: transparent !important;
    }
    
    .el-descriptions__header,
    .ed-descriptions__header {
      background: transparent !important;
    }
    
    tbody {
      background: transparent !important;
    }
    
    tr {
      background: transparent !important;
    }
    
    .el-descriptions__label,
    .ed-descriptions__label {
      background: linear-gradient(90deg, rgba(139, 92, 246, 0.15) 0%, rgba(139, 92, 246, 0.08) 100%) !important;
      color: rgba(196, 181, 253, 0.8) !important;
      font-weight: 600 !important;
      border-right: 2px solid rgba(139, 92, 246, 0.35) !important;
      border-color: rgba(139, 92, 246, 0.12) !important;
      width: 140px !important;
      min-width: 140px !important;
      white-space: nowrap !important;
      overflow: hidden !important;
      text-overflow: ellipsis !important;
    }
    
    .el-descriptions__content,
    .ed-descriptions__content {
      background: rgba(26, 18, 37, 0.3) !important;
      color: rgba(255, 255, 255, 0.95) !important;
      border-color: rgba(139, 92, 246, 0.12) !important;
      white-space: pre-wrap !important;
      word-break: break-word !important;
    }
    
    .el-descriptions__cell,
    .ed-descriptions__cell {
      background: transparent !important;
      border-color: rgba(139, 92, 246, 0.12) !important;
    }
    
    .el-descriptions__row,
    .ed-descriptions__row {
      background: transparent !important;
      
      &:hover {
        .el-descriptions__label,
        .ed-descriptions__label {
          background: linear-gradient(90deg, rgba(139, 92, 246, 0.22) 0%, rgba(139, 92, 246, 0.12) 100%) !important;
          color: #a78bfa !important;
        }
        
        .el-descriptions__content,
        .ed-descriptions__content {
          background: rgba(26, 18, 37, 0.5) !important;
        }
      }
    }
  }
}
</style>
