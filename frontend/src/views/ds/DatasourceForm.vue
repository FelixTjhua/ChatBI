<script lang="ts" setup>
import { ref, reactive, onMounted, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { datasourceApi } from '@/api/datasource'
import icon_upload_outlined from '@/assets/svg/icon_upload_outlined.svg'
import icon_searchOutline_outlined from '@/assets/svg/icon_search-outline_outlined.svg'
import { encrypted, decrypted } from './js/aes'
import { ElMessage, ElMessageBox } from 'element-plus-secondary'
import type { FormInstance, FormRules } from 'element-plus-secondary'
import icon_form_outlined from '@/assets/svg/icon_form_outlined.svg'
import FixedSizeList from 'element-plus-secondary/es/components/virtual-list/src/components/fixed-size-list.mjs'
import { debounce } from 'lodash-es'
import { Plus } from '@element-plus/icons-vue'
import { haveSchema, isFileType } from '@/views/ds/js/ds-type'
import { setSize } from '@/utils/utils'
import { useCache } from '@/utils/useCache'
import EmptyBackground from '@/components/EmptyBackground.vue'
import icon_fileExcel_colorful from '@/assets/datasource/icon_excel.svg?url'
import icon_filePdf_colorful from '@/assets/datasource/icon_pdf.svg?url'
import icon_fileCsv_colorful from '@/assets/datasource/icon_csv.svg?url'
import IconOpeDelete from '@/assets/svg/icon_delete.svg'

const props = withDefaults(
  defineProps<{
    activeName: string
    activeType: string
    activeStep: number
    isDataTable: boolean
  }>(),
  {
    activeName: '',
    activeType: '',
    activeStep: 0,
    isDataTable: false,
  }
)

const dsFormRef = ref<FormInstance>()
const emit = defineEmits(['refresh', 'changeActiveStep', 'close'])
const isCreate = ref(true)
const isEditTable = ref(false)
const checkList = ref<any>([])
const tableList = ref<any>([])
const excelUploadSuccess = ref(false)
const tableListLoading = ref(false)
const checkLoading = ref(false)
const { wsCache } = useCache()
const token = wsCache.get('user.token')
const uploadHeaders = ref<any>({ 'X-CHATBI-TOKEN': `Bearer ${token}` })
const dialogTitle = ref('')
const getUploadURL = computed(() => {
  if (form.value.type === 'pdf') {
    return import.meta.env.VITE_API_BASE_URL + '/datasource/uploadPdf'
  }
  return import.meta.env.VITE_API_BASE_URL + '/datasource/uploadExcel'
})

const getAcceptTypes = computed(() => {
  if (form.value.type === 'excel') {
    return '.xlsx,.xls'
  }
  if (form.value.type === 'csv') {
    return '.csv'
  }
  if (form.value.type === 'pdf') {
    return '.pdf'
  }
  return ''
})
const uploadHintText = computed(() => {
  if (form.value.type === 'excel') {
    return t('common.upload_hint_excel')
  }
  if (form.value.type === 'csv') {
    return t('common.upload_hint_csv')
  }
  if (form.value.type === 'pdf') {
    return t('common.upload_hint_pdf')
  }
  return t('common.not_exceed_50mb')
})
const saveLoading = ref<boolean>(false)
const uploadLoading = ref(false)
const pdfUploadResult = ref<any>(null)
const excelUploadResult = ref<any>(null)
const dbPreviewReady = ref(false)
const { t } = useI18n()
const schemaList = ref<any>([])

const rules = reactive<FormRules>({
  name: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + t('ds.form.name'),
      trigger: 'blur',
    },
    { min: 1, max: 50, message: t('ds.form.validate.name_length'), trigger: 'blur' },
  ],
  type: [
    {
      required: true,
      message: t('datasource.Please_select') + t('common.empty') + t('ds.type'),
      trigger: 'change',
    },
  ],
  host: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + t('ds.form.host'),
      trigger: 'blur',
    },
  ],
  port: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + t('ds.form.port'),
      trigger: 'blur',
    },
  ],
  database: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + t('ds.form.database'),
      trigger: 'blur',
    },
  ],
  sheets: [{
    required: true,
    message: t('user.upload_file'),
    trigger: 'change',
    // PDF不导入PG表，sheets为空数组是合法的
    // 只要文件已上传成功（filename非空），验证就通过
    validator: (_rule: any, value: any, callback: any) => {
      if (form.value.type === 'pdf') {
        // PDF只需要文件已上传（filename非空），不需要sheets
        if (form.value.filename) {
          callback()
        } else {
          callback(new Error(t('user.upload_file')))
        }
      } else {
        // Excel/CSV需要sheets非空
        if (value && value.length > 0) {
          callback()
        } else {
          callback(new Error(t('user.upload_file')))
        }
      }
    },
  }],
  dbSchema: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + 'Schema',
      trigger: 'blur',
    },
  ],
})

const dialogVisible = ref<boolean>(false)
const form = ref<any>({
  name: '',
  description: '',
  type: props.activeType,
  configuration: '',
  driver: '',
  host: '',
  port: 0,
  username: '',
  password: '',
  database: '',
  extraJdbc: '',
  dbSchema: '',
  filename: '',
  sheets: [],
  mode: 'service_name',
  timeout: 30,
})

const close = () => {
  dialogVisible.value = false
  isCreate.value = true
  emit('changeActiveStep', 0)
  emit('close')
  isEditTable.value = false
  checkList.value = []
  tableList.value = []
  excelUploadSuccess.value = false
  pdfUploadResult.value = null
  excelUploadResult.value = null
  dbPreviewReady.value = false
  saveLoading.value = false
}

const initForm = (item: any, editTable: boolean = false) => {
  isEditTable.value = false
  keywords.value = ''
  dsFormRef.value!.clearValidate()
  if (item) {
    dialogTitle.value = editTable ? t('ds.form.title.choose_tables') : t('ds.form.title.edit')
    isCreate.value = false
    form.value.id = item.id
    form.value.name = item.name
    form.value.description = item.description
    form.value.type = item.type
    form.value.configuration = item.configuration
    if (item.configuration) {
      const configuration = JSON.parse(decrypted(item.configuration))
      form.value.host = configuration.host
      form.value.port = configuration.port
      form.value.username = configuration.username
      form.value.password = configuration.password
      form.value.database = configuration.database
      form.value.extraJdbc = configuration.extraJdbc
      form.value.dbSchema = configuration.dbSchema
      form.value.filename = configuration.filename
      form.value.sheets = configuration.sheets
      form.value.mode = configuration.mode
      form.value.timeout = configuration.timeout ? configuration.timeout : 30
    }

    if (editTable) {
      dialogTitle.value = t('ds.form.choose_tables')
      emit('changeActiveStep', 2)
      isEditTable.value = true
      isCreate.value = false
      // request tables and check tables

      datasourceApi.tableList(item.id).then((res: any) => {
        checkList.value = res.map((ele: any) => {
          return ele.table_name
        })
        if (isFileType(item.type)) {
          tableList.value = form.value.sheets
          nextTick(() => {
            handleCheckedTablesChange([...checkList.value])
          })
        } else {
          tableListLoading.value = true
          const requestObj = buildConf()
          datasourceApi
            .getTablesByConf(requestObj)
            .then((table) => {
              tableList.value = table
              checkList.value = checkList.value.filter((ele: string) => {
                return table
                  .map((ele: any) => {
                    return ele.tableName
                  })
                  .includes(ele)
              })
              nextTick(() => {
                handleCheckedTablesChange([...checkList.value])
              })
            })
            .catch(() => {
              ElMessage.error(t('ds.form.connect.failed'))
            })
            .finally(() => {
              tableListLoading.value = false
            })
        }
      }).catch(() => {
        ElMessage.error(t('ds.form.connect.failed'))
      })
    }
  } else {
    dialogTitle.value = t('ds.form.title.add')
    isCreate.value = true
    isEditTable.value = false
    checkList.value = []
    tableList.value = []
    form.value = {
      name: '',
      description: '',
      type: props.activeType || 'pg',
      configuration: '',
      driver: '',
      host: '',
      port: 0,
      username: '',
      password: '',
      database: '',
      extraJdbc: '',
      dbSchema: '',
      filename: '',
      sheets: [],
      mode: 'service_name',
      timeout: 30,
    }
  }
  dialogVisible.value = true
}

const save = async (formEl: FormInstance | undefined) => {
  if (!formEl) return
  await formEl.validate(async (valid) => {
    if (valid) {
      const list = tableList.value
        .filter((ele: any) => {
          return checkTableList.value.includes(ele.tableName)
        })
        .map((ele: any) => {
          return { table_name: ele.tableName, table_comment: ele.tableComment }
        })

      if (checkTableList.value.length > 30) {
        try {
          const excessive = await ElMessageBox.confirm(t('common.excessive_tables_selected'), {
            tip: t('common.to_continue_saving', { msg: checkTableList.value.length }),
            confirmButtonText: t('common.save'),
            cancelButtonText: t('common.cancel'),
            confirmButtonType: 'primary',
            type: 'warning',
            customClass: 'confirm-with_icon',
            autofocus: false,
            showClose: false,
          })

          if (excessive !== 'confirm') return
        } catch {
          // 用户取消
          return
        }
      }
      saveLoading.value = true

      const requestObj = buildConf()
      if (form.value.id) {
        if (!isEditTable.value) {
          // only update datasource config info
          datasourceApi
            .update(requestObj)
            .then(() => {
              ElMessage.success(t('common.save_success'))
              close()
              emit('refresh')
            })
            .catch(() => {
              ElMessage.error(t('common.save_failed'))
            })
            .finally(() => {
              saveLoading.value = false
            })
        } else {
          // save table and field
          // PDF不导入PG表，跳过chooseTables API调用
          if (form.value.type === 'pdf') {
            // PDF编辑表时只需更新配置，不需要chooseTables
            datasourceApi
              .update(requestObj)
              .then(() => {
                ElMessage.success(t('common.save_success'))
                close()
                emit('refresh')
              })
              .catch(() => {
                ElMessage.error(t('common.save_failed'))
              })
              .finally(() => {
                saveLoading.value = false
              })
          } else {
            datasourceApi
              .chooseTables(form.value.id, list)
              .then(() => {
                ElMessage.success(t('common.save_success'))
                close()
                emit('refresh')
              })
              .catch(() => {
                ElMessage.error(t('common.save_failed'))
              })
              .finally(() => {
                saveLoading.value = false
              })
          }
        }
      } else {
        requestObj.tables = list
        datasourceApi
          .add(requestObj)
          .then(() => {
            ElMessage.success(t('common.save_success'))
            close()
            emit('refresh')
          })
          .catch(() => {
            ElMessage.error(t('common.save_failed'))
          })
          .finally(() => {
            saveLoading.value = false
          })
      }
    }
  })
}

const buildConf = () => {
  // 文件类型（Excel/CSV/PDF）只保存文件相关配置
  if (isFileType(form.value.type)) {
    const fileConf: any = {
      filename: form.value.filename,
      sheets: form.value.sheets,
    }
    // PDF数据源额外保存document_id
    if (form.value.type === 'pdf' && form.value.document_id) {
      fileConf.document_id = form.value.document_id
    }
    form.value.configuration = encrypted(
      JSON.stringify(fileConf)
    )
  } else {
    // 数据库类型保存完整的连接配置
    form.value.configuration = encrypted(
      JSON.stringify({
        host: form.value.host,
        port: form.value.port,
        username: form.value.username,
        password: form.value.password,
        database: form.value.database,
        extraJdbc: form.value.extraJdbc,
        dbSchema: form.value.dbSchema,
        mode: form.value.mode,
        timeout: form.value.timeout,
      })
    )
  }
  
  const obj = JSON.parse(JSON.stringify(form.value))
  delete obj.driver
  delete obj.host
  delete obj.port
  delete obj.username
  delete obj.password
  delete obj.database
  delete obj.extraJdbc
  delete obj.dbSchema
  delete obj.filename
  delete obj.sheets
  delete obj.mode
  delete obj.timeout
  return obj
}

const check = () => {
  const requestObj = buildConf()
  datasourceApi.check(requestObj).then((res: any) => {
    if (res) {
      ElMessage({
        message: t('ds.form.connect.success'),
        type: 'success',
        showClose: true,
      })
    } else {
      ElMessage({
        message: t('ds.form.connect.failed'),
        type: 'error',
        showClose: true,
      })
    }
  }).catch(() => {
    ElMessage({ message: t('ds.form.connect.failed'), type: 'error', showClose: true })
  })
}
const getSchema = () => {
  schemaList.value = []
  const requestObj = buildConf()
  datasourceApi.getSchema(requestObj).then((res: any) => {
    schemaList.value = (res || []).map((item: any) => ({ label: item, value: item }))
    if (schemaList.value.length > 0) {
      // 自动选中 public（如果存在），否则选第一个
      const publicSchema = schemaList.value.find((s: any) => s.value === 'public')
      if (publicSchema && !form.value.dbSchema) {
        form.value.dbSchema = 'public'
      }
      ElMessage.success(`获取到 ${schemaList.value.length} 个 Schema`)
    } else {
      ElMessage.warning('未获取到 Schema 列表')
    }
  }).catch(() => {
    ElMessage.error(t('ds.form.connect.failed'))
  })
}

onBeforeUnmount(() => (saveLoading.value = false))

const next = debounce(async (formEl: FormInstance | undefined) => {
  if (!formEl) return
  await formEl.validate((valid) => {
    if (valid) {
      if (isFileType(form.value.type)) {
        // next, show tables
        if (excelUploadSuccess.value) {
          // PDF不导入PG表，跳过chooseTables步骤直接保存
          if (form.value.type === 'pdf') {
            // PDF直接触发保存（跳过step 2的表选择）
            save(formEl)
            return
          }
          emit('changeActiveStep', props.activeStep + 1)
        }
      } else {
        if (checkLoading.value) return
        // check status if success do next
        const requestObj = buildConf()
        checkLoading.value = true
        datasourceApi
          .check(requestObj)
          .then((res: boolean) => {
            if (res) {
              emit('changeActiveStep', props.activeStep + 1)
              // request tables
              datasourceApi.getTablesByConf(requestObj).then((res: any) => {
                tableList.value = res
                dbPreviewReady.value = true
              }).catch(() => {
                ElMessage.error(t('ds.form.connect.failed'))
              })
            } else {
              ElMessage({
                message: t('ds.form.connect.failed'),
                type: 'error',
                showClose: true,
              })
            }
          })
          .catch(() => {
            ElMessage({ message: t('ds.form.connect.failed'), type: 'error', showClose: true })
          })
          .finally(() => {
            checkLoading.value = false
          })
      }
    }
  })
}, 300)

const preview = debounce(() => {
  emit('changeActiveStep', props.activeStep - 1)
}, 200)

const beforeUpload = (rawFile: any) => {
  setFile(rawFile)
  if (rawFile.size / 1024 / 1024 > 50) {
    ElMessage.error(t('ds.file_size_exceed'))
    return false
  }
  uploadLoading.value = true
  return true
}

const onSuccess = (response: any) => {
  form.value.filename = response.data.filename
  // PDF 响应可能没有 sheets 字段，使用空数组兜底
  form.value.sheets = response.data.sheets || []
  tableList.value = response.data.sheets || []
  excelUploadSuccess.value = true
  uploadLoading.value = false
  // PDF上传时保存document_id，用于文档预览
  if (response.data.document_id) {
    form.value.document_id = response.data.document_id
  }
  // PDF上传结果预览数据
  if (response.data.pdf_stats) {
    pdfUploadResult.value = {
      stats: response.data.pdf_stats,
      preview: response.data.pdf_preview || null,
      warnings: response.data.warnings || [],
    }
    // 展示PDF上传警告（扫描页、向量化不完整等）
    const warnings = response.data.warnings || []
    if (warnings.length > 0) {
      for (const w of warnings) {
        ElMessage.warning({ message: w, duration: 8000, showClose: true })
      }
    }
  }
  // Excel/CSV上传结果预览数据
  if (response.data.excel_preview) {
    excelUploadResult.value = response.data.excel_preview
  }
}

const onError = () => {
  uploadLoading.value = false
  ElMessage.error(t('ds.form.upload.failed'))
}

onMounted(() => {
  setTimeout(() => {
    dsFormRef.value!.clearValidate()
  }, 100)
})

const keywords = ref('')
const tableListWithSearch = computed(() => {
  if (!keywords.value) return tableList.value
  return tableList.value.filter((ele: any) =>
    ele.tableName.toLowerCase().includes(keywords.value.toLowerCase())
  )
})

watch(keywords, () => {
  const tableNameArr = tableListWithSearch.value.map((ele: any) => ele.tableName)
  checkList.value = checkTableList.value.filter((ele) => tableNameArr.includes(ele))
  const checkedCount = checkList.value.length
  checkAll.value = checkedCount === tableListWithSearch.value.length
  isIndeterminate.value = checkedCount > 0 && checkedCount < tableListWithSearch.value.length
})

watch(
  () => props.activeType,
  (val) => {
    form.value.type = val
  }
)
const fileSize = ref('-')
const clearFile = () => {
  fileSize.value = ''
  form.value.filename = ''
  form.value.sheets = []
  tableList.value = []
  pdfUploadResult.value = null
  excelUploadResult.value = null
}

const setFile = (file: any) => {
  fileSize.value = setSize(file.size)
}

const checkAll = ref(false)
const isIndeterminate = ref(false)
const checkTableList = ref([] as any[])

const handleCheckAllChange = (val: any) => {
  checkList.value = val
    ? [
        ...new Set([
          ...tableListWithSearch.value.map((ele: any) => ele.tableName),
          ...checkList.value,
        ]),
      ]
    : []
  isIndeterminate.value = false
  const tableNameArr = tableListWithSearch.value.map((ele: any) => ele.tableName)
  checkTableList.value = val
    ? [...new Set([...tableNameArr, ...checkTableList.value])]
    : checkTableList.value.filter((ele) => !tableNameArr.includes(ele))
}

const handleCheckedTablesChange = (value: any[]) => {
  const checkedCount = value.length
  checkAll.value = checkedCount === tableListWithSearch.value.length
  isIndeterminate.value = checkedCount > 0 && checkedCount < tableListWithSearch.value.length
  const tableNameArr = tableListWithSearch.value.map((ele: any) => ele.tableName)
  checkTableList.value = [
    ...new Set([...checkTableList.value.filter((ele) => !tableNameArr.includes(ele)), ...value]),
  ]
}

const tableListSave = () => {
  save(dsFormRef.value)
}

defineExpose({
  initForm,
  tableListSave,
})
</script>

<template>
  <div
    v-loading="uploadLoading || saveLoading || checkLoading"
    class="model-form"
    :class="(!isCreate || activeStep === 2) && 'edit-form'"
  >
    <div v-if="isCreate && activeStep !== 2" class="model-name">
      {{ activeName }}
      <span v-if="!isFileType(form.type)" style="margin-left: 8px; color: #8f959e; font-size: 12px">
        <span>{{ t('ds.form.support_version') }}:&nbsp;</span>
        <span v-if="form.type === 'mysql'">5.6+</span>
        <span v-else-if="form.type === 'pg'">9.6+</span>
        <span v-else-if="form.type === 'oracle'">12+</span>
      </span>
    </div>
    <div class="form-content">
      <el-form
        v-show="activeStep === 1"
        ref="dsFormRef"
        :model="form"
        label-position="top"
        label-width="auto"
        :rules="rules"
        @submit.prevent
      >
        <div v-if="isFileType(form.type)">
          <el-form-item prop="sheets" :label="t('ds.form.file')">
            <div v-if="form.filename" class="pdf-card">
              <img :src="form.type === 'pdf' ? icon_filePdf_colorful : form.type === 'csv' ? icon_fileCsv_colorful : icon_fileExcel_colorful" width="40px" height="40px" />
              <div class="file-name">
                <div class="name">{{ form.filename }}</div>
                <div class="size">{{ form.filename.split('.').pop()?.toUpperCase() }} - {{ fileSize }}</div>
              </div>
              <el-icon v-if="!form.id" class="action-btn" size="16" @click="clearFile">
                <IconOpeDelete></IconOpeDelete>
              </el-icon>
            </div>
            <el-upload
              v-if="form.filename && !form.id"
              class="upload-user"
              :accept="getAcceptTypes"
              :action="getUploadURL"
              :headers="uploadHeaders"
              :before-upload="beforeUpload"
              :on-error="onError"
              :on-success="onSuccess"
              :show-file-list="false"
              :file-list="form.sheets"
            >
              <el-button text style="line-height: 22px; height: 22px">
                {{ $t('common.re_upload') }}
              </el-button>
            </el-upload>
            <el-upload
              v-else-if="!form.id"
              class="upload-user"
              :accept="getAcceptTypes"
              :action="getUploadURL"
              :headers="uploadHeaders"
              :before-upload="beforeUpload"
              :on-success="onSuccess"
              :on-error="onError"
              :show-file-list="false"
              :file-list="form.sheets"
            >
              <el-button secondary>
                <el-icon size="16" style="margin-right: 4px">
                  <icon_upload_outlined></icon_upload_outlined>
                </el-icon>
                {{ t('user.upload_file') }}</el-button
              >
            </el-upload>
            <span v-if="!form.filename" class="not_exceed">{{ uploadHintText }}</span>
          </el-form-item>
          <!-- 上传成功后显示文件基本信息 -->
          <div v-if="excelUploadSuccess && form.filename" class="upload-file-info">
            <div class="file-info-title">📋 {{ t('ds_pdf.file_info') }}</div>
            <div class="file-info-grid">
              <div class="file-info-item">
                <span class="fi-label">{{ t('ds_pdf.filename') }}</span>
                <span class="fi-value">{{ form.filename }}</span>
              </div>
              <template v-if="form.type === 'pdf' && pdfUploadResult?.stats">
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.file_size') }}</span>
                  <span class="fi-value">{{ pdfUploadResult.stats.file_size ? (pdfUploadResult.stats.file_size / 1024 / 1024).toFixed(2) + ' MB' : fileSize }}</span>
                </div>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.total_pages') }}</span>
                  <span class="fi-value fi-hl">{{ pdfUploadResult.stats.total_pages }} {{ t('ds_pdf.pages_unit') }}</span>
                </div>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.processing_time') }}</span>
                  <span class="fi-value">{{ (pdfUploadResult.stats.processing_time || 0).toFixed(2) }}s</span>
                </div>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.section_paragraphs') }}</span>
                  <span class="fi-value">{{ pdfUploadResult.stats.total_sections }} {{ t('ds_pdf.count_unit') }}</span>
                </div>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.recognized_tables') }}</span>
                  <span class="fi-value">{{ pdfUploadResult.stats.total_tables || 0 }} {{ t('ds_pdf.count_unit') }}</span>
                </div>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.doc_chunks') }}</span>
                  <span class="fi-value fi-hl">{{ pdfUploadResult.stats.total_chunks || 0 }} {{ t('ds_pdf.count_unit') }}</span>
                </div>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.vectorized_chunks') }}</span>
                  <span class="fi-value fi-hl">{{ pdfUploadResult.stats.vectorized_count || 0 }} {{ t('ds_pdf.count_unit') }}</span>
                </div>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.table_chunk_count') }}</span>
                  <span class="fi-value">{{ pdfUploadResult.stats.table_chunks || 0 }} {{ t('ds_pdf.count_unit') }}</span>
                </div>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.raw_text_length') }}</span>
                  <span class="fi-value">{{ pdfUploadResult.stats.raw_text_length ? (pdfUploadResult.stats.raw_text_length / 1000).toFixed(1) + 'K ' + t('ds_pdf.chars_unit') : '-' }}</span>
                </div>
                <div v-if="pdfUploadResult.warnings?.length" class="pdf-warnings">
                  <div v-for="(w, i) in pdfUploadResult.warnings" :key="i" class="pdf-warning-item">
                    ⚠️ {{ w }}
                  </div>
                </div>
              </template>
              <template v-else-if="(form.type === 'excel' || form.type === 'csv') && excelUploadResult">
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.file_size') }}</span>
                  <span class="fi-value">{{ fileSize }}</span>
                </div>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.file_type') }}</span>
                  <span class="fi-value fi-hl">{{ form.type === 'csv' ? 'CSV' : 'Excel' }}</span>
                </div>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.sheet_count') }}</span>
                  <span class="fi-value">{{ excelUploadResult.sheet_count || 1 }}</span>
                </div>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.total_rows') }}</span>
                  <span class="fi-value fi-hl">{{ excelUploadResult.total_rows || 0 }} {{ t('ds_pdf.rows_unit') }}</span>
                </div>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.field_count') }}</span>
                  <span class="fi-value">{{ excelUploadResult.total_columns || 0 }} {{ t('ds_pdf.count_unit') }}</span>
                </div>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.tables_imported') }}</span>
                  <span class="fi-value fi-hl">{{ excelUploadResult.tables_created || excelUploadResult.sheet_count || 1 }} {{ t('ds_pdf.count_unit') }}</span>
                </div>
                <template v-if="excelUploadResult.cleaning_stats">
                  <div class="file-info-item">
                    <span class="fi-label">{{ t('ds_pdf.cleaned_rows') }}</span>
                    <span class="fi-value">{{ excelUploadResult.cleaning_stats.cleaned_rows || 0 }} {{ t('ds_pdf.rows_unit') }}</span>
                  </div>
                  <div class="file-info-item" v-if="excelUploadResult.cleaning_stats.dedup_removed > 0 || excelUploadResult.cleaning_stats.null_rows_removed > 0">
                    <span class="fi-label">{{ t('ds_pdf.rows_removed') }}</span>
                    <span class="fi-value">{{ (excelUploadResult.cleaning_stats.dedup_removed || 0) + (excelUploadResult.cleaning_stats.null_rows_removed || 0) }} {{ t('ds_pdf.rows_unit') }}</span>
                  </div>
                </template>
              </template>
              <template v-else>
                <div class="file-info-item">
                  <span class="fi-label">{{ t('ds_pdf.file_size') }}</span>
                  <span class="fi-value">{{ fileSize }}</span>
                </div>
              </template>
              <div class="file-info-item">
                <span class="fi-label">{{ t('ds_pdf.process_status') }}</span>
                <span class="fi-value fi-ok">✅ {{ form.type === 'pdf' ? t('ds_pdf.parse_complete') : t('ds_pdf.import_complete') }}</span>
              </div>
            </div>
            <div class="file-info-hint">{{ t('ds_pdf.save_hint') }}</div>
          </div>
        </div>
        <el-form-item :label="t('ds.form.name')" prop="name">
          <el-input
            v-model="form.name"
            clearable
            :placeholder="$t('datasource.please_enter') + $t('common.empty') + t('ds.form.name')"
          />
        </el-form-item>
        <el-form-item :label="t('ds.form.description')">
          <el-input
            v-model="form.description"
            :placeholder="
              $t('datasource.please_enter') + $t('common.empty') + t('ds.form.description')
            "
            :rows="2"
            show-word-limit
            maxlength="200"
            clearable
            type="textarea"
          />
        </el-form-item>
        <div v-if="!isFileType(form.type)" style="margin-top: 16px">
          <el-form-item
            :label="t('ds.form.host')"
            prop="host"
          >
            <el-input
              v-model="form.host"
              clearable
              :placeholder="
                $t('datasource.please_enter') +
                $t('common.empty') +
                t('ds.form.host')
              "
            />
          </el-form-item>
          <el-form-item :label="t('ds.form.port')" prop="port">
            <!--  Fix F3-2: 使用 el-input-number 确保 port 为数字类型，避免字符串传递给后端 -->
            <el-input-number
              v-model="form.port"
              :min="1"
              :max="65535"
              controls-position="right"
              :placeholder="$t('datasource.please_enter') + $t('common.empty') + t('ds.form.port')"
            />
          </el-form-item>
          <el-form-item :label="t('ds.form.username')">
            <el-input
              v-model="form.username"
              clearable
              :placeholder="
                $t('datasource.please_enter') + $t('common.empty') + t('ds.form.username')
              "
            />
          </el-form-item>
          <el-form-item :label="t('ds.form.password')">
            <el-input
              v-model="form.password"
              clearable
              :placeholder="
                $t('datasource.please_enter') + $t('common.empty') + t('ds.form.password')
              "
              type="password"
              show-password
            />
          </el-form-item>
          <el-form-item
            :label="t('ds.form.database')"
            prop="database"
          >
            <el-input
              v-model="form.database"
              clearable
              :placeholder="
                $t('datasource.please_enter') + $t('common.empty') + t('ds.form.database')
              "
            />
          </el-form-item>
          <el-form-item :label="t('ds.form.extra_jdbc')">
            <el-input
              v-model="form.extraJdbc"
              clearable
              :placeholder="
                $t('datasource.please_enter') + $t('common.empty') + t('ds.form.extra_jdbc')
              "
            />
          </el-form-item>
          <!--  Oracle 数据源需要选择连接模式（Service Name / SID） -->
          <el-form-item
            v-if="form.type === 'oracle'"
            :label="t('ds.form.connect_mode')"
            prop="mode"
            :rules="[{ required: true, message: t('ds.form.validate.mode_required'), trigger: 'change' }]"
          >
            <el-radio-group v-model="form.mode">
              <el-radio value="service_name">{{ t('ds.form.mode.service_name') || 'Service Name' }}</el-radio>
              <el-radio value="sid">{{ t('ds.form.mode.sid') || 'SID' }}</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="haveSchema.includes(form.type)" class="schema-label" prop="dbSchema">
            <template #label>
              <span class="name">Schema<i class="required" /></span>
              <el-button text size="small" @click="getSchema">
                <template #icon>
                  <Icon name="icon_add_outlined">
                    <Plus class="svg-icon" />
                  </Icon>
                </template>
                {{ t('datasource.get_schema') }}
              </el-button>
            </template>
            <el-select
              v-model="form.dbSchema"
              filterable
              teleported
              :placeholder="$t('datasource.please_enter') + $t('common.empty') + 'Schema'"
            >
              <el-option
                v-for="item in schemaList"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('ds.form.timeout')" prop="timeout">
            <el-input-number
              v-model="form.timeout"
              clearable
              :min="0"
              :max="300"
              controls-position="right"
            />
          </el-form-item>
        </div>
      </el-form>
      <div v-show="activeStep === 2" v-loading="tableListLoading" class="select-data_table">
        <!-- 数据库连接结果预览（流水线展示，仅数据库类型） -->
        <div class="title">
          {{ $t('ds.form.choose_tables') }} ({{ checkTableList.length }}/ {{ tableList.length }})
        </div>
        <el-input
          v-model="keywords"
          clearable
          style="width: 100%; margin-bottom: 16px"
          :placeholder="$t('datasource.search')"
        >
          <template #prefix>
            <el-icon>
              <icon_searchOutline_outlined class="svg-icon" />
            </el-icon>
          </template>
        </el-input>
        <div class="container">
          <div class="select-all">
            <el-checkbox
              v-model="checkAll"
              :indeterminate="isIndeterminate"
              @change="handleCheckAllChange"
            >
              {{ t('datasource.select_all') }}
            </el-checkbox>
          </div>
          <EmptyBackground
            v-if="!!keywords && !tableListWithSearch.length"
            :description="$t('datasource.relevant_content_found')"
            img-type="tree"
            style="width: 100%"
          />
          <el-checkbox-group
            v-else
            v-model="checkList"
            style="position: relative"
            @change="handleCheckedTablesChange"
          >
            <!-- 文件类型（Excel/CSV）sheet数量少，使用普通列表 -->
            <template v-if="isFileType(form.type)">
              <div
                v-for="item in tableListWithSearch"
                :key="item.tableName"
                class="list-item_primary"
                style="height: 32px"
              >
                <el-checkbox :label="item.tableName">
                  <el-icon size="16" style="margin-right: 8px">
                    <icon_form_outlined></icon_form_outlined>
                  </el-icon>
                  {{ item.tableName }}
                </el-checkbox>
              </div>
            </template>
            <!-- 数据库类型表数量多，使用虚拟滚动 -->
            <FixedSizeList
              v-else
              :item-size="32"
              :data="tableListWithSearch"
              :total="tableListWithSearch.length"
              :width="'100%'"
              :height="460"
              :scrollbar-always-on="true"
              class-name="ed-select-dropdown__list"
              layout="vertical"
            >
              <template #default="{ index, style }">
                <div class="list-item_primary" :style="style">
                  <el-checkbox :label="tableListWithSearch[index].tableName">
                    <el-icon size="16" style="margin-right: 8px">
                      <icon_form_outlined></icon_form_outlined>
                    </el-icon>
                    {{ tableListWithSearch[index].tableName }}</el-checkbox
                  >
                </div>
              </template>
            </FixedSizeList>
          </el-checkbox-group>
        </div>
      </div>
    </div>
    <div v-if="!isDataTable" class="draw-foot">
      <el-button secondary @click="close">{{ t('common.cancel') }}</el-button>
      <el-button v-show="!isFileType(form.type) && !isDataTable" secondary @click="check">
        {{ t('ds.check') }}
      </el-button>
      <el-button v-show="activeStep !== 0 && isCreate" secondary @click="preview">
        {{ t('ds.previous') }}
      </el-button>
      <el-button v-show="activeStep === 1 && isCreate" type="primary" @click="next(dsFormRef)">
        {{ t('common.next') }}
      </el-button>
      <el-button v-show="activeStep === 2 || !isCreate" type="primary" @click="save(dsFormRef)">
        {{ t('common.save') }}
      </el-button>
    </div>
  </div>
</template>

<style lang="less" scoped>
// ChatBI 数据源表单 - 深色主题设计
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

.model-form {
  width: 100%;
  position: absolute;
  right: 0;
  top: 56px;
  height: 100%;
  padding-bottom: 120px;
  overflow-y: auto;
  background: @dark-bg-secondary;

  // 深色滚动条
  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(139, 92, 246, 0.3);
    border-radius: 3px;

    &:hover {
      background: rgba(139, 92, 246, 0.5);
    }
  }

  .model-name {
    height: 56px;
    width: 100%;
    padding-left: 24px;
    border-bottom: 1px solid @dark-border;
    font-weight: 600;
    font-size: 16px;
    line-height: 24px;
    display: flex;
    align-items: center;
    color: @dark-text;
    background: rgba(139, 92, 246, 0.03);

    span {
      color: @dark-text-muted !important;
    }
  }

  .form-content {
    width: 800px;
    margin: 0 auto;
    padding-top: 24px;

    .upload-user {
      height: 32px;
      .ed-upload {
        width: 100% !important;
      }
    }

    .not_exceed {
      font-weight: 400;
      font-size: 14px;
      line-height: 22px;
      color: @dark-text-muted;
      display: inline-block;
      width: 100%;
    }

    .pdf-card {
      width: 100%;
      height: 64px;
      display: flex;
      align-items: center;
      padding: 0 16px 0 14px;
      background: @dark-bg-card;
      border: 1px solid @dark-border;
      border-radius: 12px;

      .file-name {
        margin-left: 12px;

        .name {
          font-weight: 500;
          font-size: 14px;
          line-height: 22px;
          color: @dark-text;
        }

        .size {
          font-weight: 400;
          font-size: 12px;
          line-height: 20px;
          color: @dark-text-muted;
        }
      }

      .action-btn {
        margin-left: auto;
      }

      .ed-icon {
        position: relative;
        cursor: pointer;
        color: @dark-text-muted;
        transition: all 0.2s ease;

        &::after {
          content: '';
          background-color: rgba(139, 92, 246, 0.15);
          position: absolute;
          border-radius: 6px;
          width: 28px;
          height: 28px;
          transform: translate(-50%, -50%);
          top: 50%;
          left: 50%;
          display: none;
        }

        &:hover {
          color: #f87171;

          &::after {
            display: block;
            background-color: rgba(248, 113, 113, 0.15);
          }
        }
      }
    }

    // 表单项深色主题
    :deep(.ed-form-item) {
      margin-bottom: 20px;

      &.is-error {
        margin-bottom: 44px;
      }

      .ed-form-item__label {
        color: @dark-text-secondary !important;
        font-weight: 500;
      }

      .ed-input__wrapper {
        background: rgba(139, 92, 246, 0.08) !important;
        border: 1px solid @dark-border !important;
        border-radius: 10px;
        box-shadow: none !important;

        &:hover {
          border-color: rgba(139, 92, 246, 0.35) !important;
        }

        &:focus-within,
        &.is-focus {
          border-color: @primary-500 !important;
          box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15) !important;
        }
      }

      .ed-input__inner {
        color: @dark-text !important;

        &::placeholder {
          color: @dark-text-muted !important;
        }
      }

      .ed-textarea__inner {
        background: rgba(139, 92, 246, 0.08) !important;
        border: 1px solid @dark-border !important;
        border-radius: 10px;
        color: @dark-text !important;

        &::placeholder {
          color: @dark-text-muted !important;
        }

        &:hover {
          border-color: rgba(139, 92, 246, 0.35) !important;
        }

        &:focus {
          border-color: @primary-500 !important;
          box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15) !important;
        }
      }

      .ed-input__count {
        color: @dark-text-muted !important;
        background: transparent !important;
        font-size: 12px;
        line-height: 1;
        right: 10px;
        bottom: 8px;
      }

      .ed-select {
        .ed-input__wrapper {
          background: rgba(139, 92, 246, 0.08) !important;
        }
      }

      .ed-input-number {
        .ed-input__wrapper {
          background: rgba(139, 92, 246, 0.08) !important;
        }

        .ed-input-number__decrease,
        .ed-input-number__increase {
          background: rgba(139, 92, 246, 0.1) !important;
          border-color: @dark-border !important;
          color: @dark-text-secondary !important;

          &:hover {
            color: @primary-400 !important;
          }
        }
      }

      .ed-radio-group {
        .ed-radio {
          color: @dark-text-secondary;

          .ed-radio__input {
            .ed-radio__inner {
              background: rgba(139, 92, 246, 0.08);
              border-color: @dark-border;

              &:hover {
                border-color: @primary-500;
              }
            }

            &.is-checked {
              .ed-radio__inner {
                background: @primary-500;
                border-color: @primary-500;
              }
            }
          }

          &.is-checked {
            .ed-radio__label {
              color: @primary-400;
            }
          }
        }
      }

      .ed-form-item__error {
        color: #f87171;
      }
    }

    // 按钮深色主题
    :deep(.ed-button) {
      &.is-secondary,
      &--default {
        background: rgba(139, 92, 246, 0.1) !important;
        border: 1px solid @dark-border !important;
        color: @dark-text-secondary !important;
        border-radius: 10px;

        &:hover {
          background: rgba(139, 92, 246, 0.2) !important;
          border-color: rgba(139, 92, 246, 0.35) !important;
          color: @dark-text !important;
        }
      }

      &--primary {
        background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%) !important;
        border: none !important;
        border-radius: 10px;
        box-shadow: 0 4px 16px rgba(139, 92, 246, 0.35);

        &:hover {
          box-shadow: 0 6px 24px rgba(139, 92, 246, 0.45);
        }
      }

      &.is-text {
        color: @primary-400 !important;

        &:hover {
          color: @primary-500 !important;
          background: rgba(139, 92, 246, 0.1) !important;
        }
      }
    }
  }

  :deep(.draw-foot) {
    position: sticky;
    bottom: 0;
    width: 100%;
    height: 72px;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    border-top: 1px solid @dark-border;
    padding-right: 24px;
    background: @dark-bg-secondary;
    z-index: 10;
    gap: 12px;
  }

  &.edit-form {
    width: 100%;

    :deep(.draw-foot) {
      width: 100%;
    }
  }

  .select-data_table {
    padding-bottom: 24px;

    .title {
      font-weight: 600;
      font-size: 16px;
      line-height: 24px;
      margin: 0 0 16px 0;
      color: @dark-text;
    }

    :deep(.ed-input__wrapper) {
      background: rgba(139, 92, 246, 0.08) !important;
      border: 1px solid @dark-border !important;
      border-radius: 10px;

      &:hover {
        border-color: rgba(139, 92, 246, 0.35) !important;
      }

      &:focus-within {
        border-color: @primary-500 !important;
        box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15) !important;
      }
    }

    :deep(.ed-input__inner) {
      color: @dark-text !important;

      &::placeholder {
        color: @dark-text-muted !important;
      }
    }

    .container {
      background: @dark-bg-card;
      border: 1px solid @dark-border;
      border-radius: 12px;
      overflow: hidden;

      .select-all {
        background: rgba(139, 92, 246, 0.08);
        height: 44px;
        padding-left: 16px;
        display: flex;
        align-items: center;
        border-bottom: 1px solid @dark-border;

        :deep(.ed-checkbox) {
          color: @dark-text-secondary;

          .ed-checkbox__input {
            .ed-checkbox__inner {
              background: rgba(139, 92, 246, 0.1);
              border-color: @dark-border;

              &:hover {
                border-color: @primary-500;
              }
            }

            &.is-checked,
            &.is-indeterminate {
              .ed-checkbox__inner {
                background: @primary-500;
                border-color: @primary-500;
              }
            }
          }
        }
      }

      :deep(.ed-checkbox__label) {
        display: inline-flex;
        align-items: center;
        color: @dark-text-secondary;
      }

      :deep(.ed-checkbox-group) {
        .list-item_primary {
          padding: 0 16px;
          display: flex;
          align-items: center;
          transition: background 0.2s ease;

          &:hover {
            background: rgba(139, 92, 246, 0.08);
          }

          .ed-checkbox {
            color: @dark-text-secondary;

            .ed-checkbox__input {
              .ed-checkbox__inner {
                background: rgba(139, 92, 246, 0.1);
                border-color: @dark-border;

                &:hover {
                  border-color: @primary-500;
                }
              }

              &.is-checked {
                .ed-checkbox__inner {
                  background: @primary-500;
                  border-color: @primary-500;
                }
              }
            }

            .ed-icon {
              color: @dark-text-muted;
            }
          }
        }
      }

      :deep(.ed-vl__window) {
        scrollbar-width: none;

        &::-webkit-scrollbar {
          width: 5px;
        }

        &::-webkit-scrollbar-track {
          background: transparent;
        }

        &::-webkit-scrollbar-thumb {
          background: rgba(139, 92, 246, 0.3);
          border-radius: 3px;

          &:hover {
            background: rgba(139, 92, 246, 0.5);
          }
        }
      }
    }
  }
}

.schema-label {
  ::v-deep(.ed-form-item__label) {
    display: flex !important;
    justify-content: space-between;
    padding-right: 0;

    &::after {
      display: none;
    }

    .name {
      color: @dark-text-secondary;

      .required::after {
        content: '*';
        color: #f87171;
        margin-left: 2px;
      }
    }
  }
}

// 响应式适配
@media (max-width: 900px) {
  .model-form {
    .form-content {
      width: 100%;
      padding: 24px 20px;
    }

    .select-data_table {
      .container {
        :deep(.ed-vl__window) {
          width: 100% !important;
        }
      }
    }
  }
}

.upload-file-info {
  margin-top: 12px;
  padding: 14px 16px;
  background: rgba(26, 18, 37, 0.85);
  border: 1px solid rgba(139, 92, 246, 0.15);
  border-radius: 10px;

  .file-info-title {
    font-size: 13px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.92);
    margin-bottom: 10px;
  }

  .file-info-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .file-info-item {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: 8px 12px;
    background: rgba(139, 92, 246, 0.04);
    border: 1px solid rgba(139, 92, 246, 0.08);
    border-radius: 6px;
  }

  .fi-label {
    font-size: 11px;
    color: rgba(196, 181, 253, 0.45);
  }

  .fi-value {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.92);
    word-break: break-all;

    &.fi-hl {
      color: #a78bfa;
      font-weight: 600;
    }

    &.fi-ok {
      color: #22c55e;
    }
  }

  .file-info-hint {
    margin-top: 10px;
    font-size: 11px;
    color: rgba(196, 181, 253, 0.4);
    text-align: center;
  }

  .pdf-warnings {
    grid-column: 1 / -1;
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 4px;
  }

  .pdf-warning-item {
    font-size: 12px;
    color: #fbbf24;
    background: rgba(251, 191, 36, 0.08);
    border: 1px solid rgba(251, 191, 36, 0.2);
    border-radius: 6px;
    padding: 8px 12px;
    line-height: 1.5;
  }
}
</style>
