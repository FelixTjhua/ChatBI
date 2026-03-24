<template>
  <el-dialog
    v-model="dialogVisible"
    :title="dialogTitle"
    width="600"
    :destroy-on-close="true"
    :close-on-click-modal="false"
    modal-class="add-datasource_dialog"
    @closed="close"
  >
    <template #header>
      <div style="display: flex">
        <div style="margin-right: 24px">{{ dialogTitle }}</div>
        <el-steps
          v-show="isCreate && !isFileType(form.type) || (isCreate && isFileType(form.type) && form.type !== 'pdf')"
          :active="active"
          align-center
          custom
          style="max-width: 400px; flex: 1"
        >
          <el-step :title="t('ds.form.base_info')" />
          <el-step :title="t('ds.form.choose_tables')" />
        </el-steps>
      </div>
    </template>

    <div v-show="active === 0" class="container">
      <el-form
        ref="dsFormRef"
        :model="form"
        label-position="top"
        label-width="auto"
        :rules="rules"
        @submit.prevent
      >
        <el-form-item :label="t('ds.form.name')" prop="name">
          <el-input v-model="form.name" clearable />
        </el-form-item>
        <el-form-item :label="t('ds.form.description')">
          <el-input v-model="form.description" clearable :rows="2" type="textarea" />
        </el-form-item>
        <el-form-item :label="t('ds.type')" prop="type">
          <el-select v-model="form.type" placeholder="Select Type" :disabled="!isCreate">
            <el-option
              v-for="item in dsType"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <!-- 文件类型：Excel/文档 -->
        <div v-if="isFileType(form.type)">
          <el-form-item :label="t('ds.form.file')">
            <!-- 文件卡片显示 -->
            <div v-if="form.filename" class="file-card">
              <div class="file-icon">
                <span v-if="form.type === 'pdf'" class="icon-text pdf">PDF</span>
                <span v-else-if="form.type === 'csv'" class="icon-text csv">CSV</span>
                <span v-else class="icon-text excel">XLS</span>
              </div>
              <div class="file-info">
                <div class="file-name">{{ form.filename }}</div>
                <div class="file-meta">{{ form.filename.split('.').pop().toUpperCase() }}</div>
              </div>
              <el-icon v-if="!form.id && isCreate" class="delete-icon" size="16" @click="clearFile">
                <Close />
              </el-icon>
            </div>
            
            <!-- 上传按钮 -->
            <el-upload
              v-if="!form.filename && isCreate"
              :disabled="!isCreate"
              :accept="getAcceptTypes()"
              :headers="headers"
              :action="getUploadURL"
              :before-upload="beforeUpload"
              :on-success="onSuccess"
              :on-error="onError"
              :show-file-list="false"
            >
              <el-button :disabled="!isCreate">
                <el-icon style="margin-right: 4px"><Upload /></el-icon>
                {{ t('ds.form.upload.button') }}
              </el-button>
            </el-upload>
            
            <!-- 重新上传按钮 -->
            <el-upload
              v-if="form.filename && !form.id && isCreate"
              :disabled="!isCreate"
              :accept="getAcceptTypes()"
              :headers="headers"
              :action="getUploadURL"
              :before-upload="beforeUpload"
              :on-success="onSuccess"
              :on-error="onError"
              :show-file-list="false"
            >
              <el-button text style="margin-top: 8px">{{ t('ds.form.upload.re_upload') }}</el-button>
            </el-upload>
            
            <div v-if="!form.filename" class="upload-tip">{{ getUploadTip() }}</div>
          </el-form-item>
        </div>
        
        <!-- 数据库类型：MySQL/PostgreSQL/Oracle等 -->
        <div v-else-if="!isFileType(form.type)">
          <el-form-item :label="t('ds.form.host')" prop="host">
            <el-input v-model="form.host" clearable />
          </el-form-item>
          <el-form-item :label="t('ds.form.port')" prop="port">
            <el-input-number v-model="form.port" :min="1" :max="65535" controls-position="right" />
          </el-form-item>
          <el-form-item :label="t('ds.form.username')">
            <el-input v-model="form.username" clearable />
          </el-form-item>
          <el-form-item :label="t('ds.form.password')">
            <el-input v-model="form.password" clearable type="password" show-password />
          </el-form-item>
          <el-form-item :label="t('ds.form.database')" prop="database">
            <el-input v-model="form.database" clearable />
          </el-form-item>
          <el-form-item
            v-if="form.type === 'oracle'"
            :label="t('ds.form.connect_mode')"
            prop="mode"
          >
            <el-radio-group v-model="form.mode">
              <el-radio value="service_name">{{ t('ds.form.mode.service_name') }}</el-radio>
              <el-radio value="sid">{{ t('ds.form.mode.sid') }}</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item :label="t('ds.form.extra_jdbc')">
            <el-input v-model="form.extraJdbc" clearable />
          </el-form-item>
          <el-form-item
            v-if="haveSchema.includes(form.type)"
            :label="t('ds.form.schema')"
            prop="dbSchema"
          >
            <el-input v-model="form.dbSchema" clearable />
            <el-button v-if="false" link type="primary" :icon="Plus">Get Schema</el-button>
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
          <span>
            <span>{{ t('ds.form.support_version') }}:&nbsp;</span>
            <span v-if="form.type === 'oracle'">12+</span>
            <span v-else-if="form.type === 'mysql'">5.6+</span>
            <span v-else-if="form.type === 'pg'">9.6+</span>
            <span v-else-if="form.type === 'clickhouse'">21.8+</span>
          </span>
        </div>
      </el-form>
    </div>
    <div v-show="active === 1" v-loading="tableListLoading" class="container">
      <el-checkbox-group v-model="checkList" style="position: relative">
        <FixedSizeList
          :item-size="40"
          :data="tableList"
          :total="tableList.length"
          :width="560"
          :height="400"
          :scrollbar-always-on="true"
          class-name="ed-select-dropdown__list"
          layout="vertical"
        >
          <template #default="{ index, style }">
            <div class="list-item_primary" :style="style">
              <el-checkbox :label="tableList[index].tableName">{{
                tableList[index].tableName
              }}</el-checkbox>
            </div>
          </template>
        </FixedSizeList>
      </el-checkbox-group>
      <span>{{ t('ds.form.selected', [checkList.length, tableList.length]) }}</span>
    </div>
    <div style="display: flex; justify-content: flex-end; margin-top: 20px">
      <el-button secondary @click="close">{{ t('common.cancel') }}</el-button>
      <el-button v-show="!isCreate && !isEditTable && !isFileType(form.type)" @click="check">
        {{ t('ds.check') }}
      </el-button>
      <el-button v-show="active === 0 && isCreate" type="primary" @click="next(dsFormRef)">
        {{ t('common.next') }}
      </el-button>
      <el-button v-show="active === 1 && isCreate" @click="preview">
        {{ t('ds.previous') }}
      </el-button>
      <el-button
        v-show="active === 1 || !isCreate"
        :loading="saveLoading"
        type="primary"
        @click="save(dsFormRef)"
      >
        {{ t('common.save') }}
      </el-button>
    </div>
  </el-dialog>
</template>
<script lang="ts" setup>
import { ref, reactive, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { datasourceApi } from '@/api/datasource'
import { encrypted, decrypted } from './js/aes'
import { ElMessage } from 'element-plus-secondary'
import type { FormInstance, FormRules } from 'element-plus-secondary'
import FixedSizeList from 'element-plus-secondary/es/components/virtual-list/src/components/fixed-size-list.mjs'
import { Plus, Close, Upload } from '@element-plus/icons-vue'
import { useCache } from '@/utils/useCache'
import { dsType, haveSchema, isFileType } from '@/views/ds/js/ds-type'

const { wsCache } = useCache()
const dsFormRef = ref<FormInstance>()
const emit = defineEmits(['refresh'])
const active = ref(0)
const isCreate = ref(true)
const isEditTable = ref(false)
const checkList = ref<any>([])
const tableList = ref<any>([])
const excelUploadSuccess = ref(false)
const tableListLoading = ref(false)
const token = wsCache.get('user.token')
const headers = ref<any>({ 'X-CHATBI-TOKEN': `Bearer ${token}` })
const dialogTitle = ref('')
const getUploadURL = computed(() => {
  if (form.value.type === 'pdf') {
    return import.meta.env.VITE_API_BASE_URL + '/datasource/uploadPdf'
  }
  return import.meta.env.VITE_API_BASE_URL + '/datasource/uploadExcel'
})
const saveLoading = ref<boolean>(false)

const { t } = useI18n()

const rules = computed<FormRules>(() => {
  // 文件类型（Excel/CSV/PDF）只需要名称和类型
  if (isFileType(form.value.type)) {
    return {
      name: [
        { required: true, message: t('ds.form.validate.name_required'), trigger: 'blur' },
        { min: 1, max: 50, message: t('ds.form.validate.name_length'), trigger: 'blur' },
      ],
      type: [{ required: true, message: t('ds.form.validate.type_required'), trigger: 'change' }],
    }
  }
  
  // 数据库类型需要完整的连接信息
  const baseRules: FormRules = {
    name: [
      { required: true, message: t('ds.form.validate.name_required'), trigger: 'blur' },
      { min: 1, max: 50, message: t('ds.form.validate.name_length'), trigger: 'blur' },
    ],
    type: [{ required: true, message: t('ds.form.validate.type_required'), trigger: 'change' }],
    host: [{ required: true, message: t('ds.form.validate.host_required'), trigger: 'blur' }],
    port: [{ required: true, message: t('ds.form.validate.port_required'), trigger: 'blur' }],
    database: [{ required: true, message: t('ds.form.validate.database_required'), trigger: 'blur' }],
  }
  
  if (form.value.type === 'oracle') {
    baseRules.mode = [{ required: true, message: t('ds.form.validate.mode_required'), trigger: 'change' }]
  }
  
  if (haveSchema.includes(form.value.type)) {
    baseRules.dbSchema = [{ required: true, message: t('ds.form.validate.schema_required'), trigger: 'blur' }]
  }
  
  return baseRules
})

const dialogVisible = ref<boolean>(false)
const form = ref<any>({
  name: '',
  description: '',
  type: 'pg',
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

const getAcceptTypes = () => {
  if (form.value.type === 'excel') {
    return '.xls, .xlsx'
  }
  if (form.value.type === 'csv') {
    return '.csv'
  }
  if (form.value.type === 'pdf') {
    return '.pdf'
  }
  return ''
}

const getUploadTip = () => {
  if (form.value.type === 'excel') {
    return t('ds.form.upload.tip_excel')
  }
  if (form.value.type === 'csv') {
    return t('ds.form.upload.tip_csv')
  }
  return ''
}

const close = () => {
  dialogVisible.value = false
  isCreate.value = true
  active.value = 0
  isEditTable.value = false
  checkList.value = []
  tableList.value = []
  excelUploadSuccess.value = false
  saveLoading.value = false
}

const open = (item: any, editTable: boolean = false) => {
  isEditTable.value = false
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
      active.value = 1
      isEditTable.value = true
      isCreate.value = false
      // request tables and check tables

      datasourceApi.tableList(item.id).then((res) => {
        checkList.value = res.map((ele: any) => {
          return ele.table_name
        })
        if (isFileType(item.type)) {
          tableList.value = form.value.sheets
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
            })
            .catch(() => {
              ElMessage.error(t('common.load_failed'))
            })
            .finally(() => {
              tableListLoading.value = false
            })
        }
      }).catch(() => {
        ElMessage.error(t('common.load_failed'))
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
      type: 'pg',
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
  await formEl.validate((valid) => {
    if (valid) {
      saveLoading.value = true
      const list = tableList.value
        .filter((ele: any) => {
          return checkList.value.includes(ele.tableName)
        })
        .map((ele: any) => {
          return { table_name: ele.tableName, table_comment: ele.tableComment }
        })

      const requestObj = buildConf()
      if (form.value.id) {
        if (!isEditTable.value) {
          // only update datasource config info
          datasourceApi.update(requestObj).then(() => {
            close()
            emit('refresh')
          }).catch(() => {
            saveLoading.value = false
            ElMessage.error(t('common.save_failed'))
          })
        } else {
          // save table and field
          // PDF不导入PG表，跳过chooseTables API调用
          if (form.value.type === 'pdf') {
            datasourceApi.update(requestObj).then(() => {
              close()
              emit('refresh')
            }).catch(() => {
              saveLoading.value = false
              ElMessage.error(t('common.save_failed'))
            })
          } else {
            datasourceApi.chooseTables(form.value.id, list).then(() => {
              close()
              emit('refresh')
            }).catch(() => {
              saveLoading.value = false
              ElMessage.error(t('common.save_failed'))
            })
          }
        }
      } else {
        requestObj.tables = list
        datasourceApi.add(requestObj).then(() => {
          close()
          emit('refresh')
        }).catch(() => {
          saveLoading.value = false
          ElMessage.error(t('common.save_failed'))
        })
      }
    }
  })
}

const buildConf = () => {
  // 对于文件类型（Excel/CSV/PDF），只保存文件相关配置
  if (isFileType(form.value.type)) {
    const fileConf: any = {
      filename: form.value.filename,
      sheets: form.value.sheets,
    }
    // PDF数据源额外保存document_id，用于文档分块预览
    if (form.value.type === 'pdf' && form.value.document_id) {
      fileConf.document_id = form.value.document_id
    }
    form.value.configuration = encrypted(
      JSON.stringify(fileConf)
    )
  } else {
    // 对于数据库类型，保存完整的连接配置
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
    ElMessage.error(t('ds.form.connect.failed'))
  })
}

const next = async (formEl: FormInstance | undefined) => {
  if (!formEl) return
  await formEl.validate((valid) => {
    if (valid) {
      if (isFileType(form.value.type)) {
        // next, show tables
        if (excelUploadSuccess.value) {
          // PDF不导入PG表，跳过chooseTables步骤直接保存
          if (form.value.type === 'pdf') {
            save(formEl)
            return
          }
          active.value++
        } else {
          ElMessage({
            message: t('ds.form.upload.please_upload'),
            type: 'warning',
            showClose: true,
          })
        }
      } else {
        // check status if success do next
        const requestObj = buildConf()
        datasourceApi.check(requestObj).then((res: boolean) => {
          if (res) {
            active.value++
            // request tables
            datasourceApi.getTablesByConf(requestObj).then((res) => {
              tableList.value = res
            }).catch(() => {
              ElMessage.error(t('common.load_failed'))
            })
          } else {
            ElMessage({
              message: t('ds.form.connect.failed'),
              type: 'error',
              showClose: true,
            })
          }
        }).catch(() => {
          ElMessage.error(t('ds.form.connect.failed'))
        })
      }
    }
  })
}

const preview = () => {
  active.value--
}

const beforeUpload = (rawFile: any) => {
  if (rawFile.size / 1024 / 1024 > 50) {
    ElMessage.error(t('ds.file_size_exceed'))
    return false
  }
  return true
}

const onSuccess = (response: any) => {
  form.value.filename = response.data.filename
  // PDF响应sheets为空数组，使用兜底避免undefined
  form.value.sheets = response.data.sheets || []
  tableList.value = response.data.sheets || []
  excelUploadSuccess.value = true
  // PDF上传时保存document_id和pdf_stats，用于文档预览
  if (response.data.document_id) {
    form.value.document_id = response.data.document_id
  }
  if (response.data.pdf_stats) {
    form.value.pdf_stats = response.data.pdf_stats
  }
}

const onError = () => {
  ElMessage.error(t('ds.form.upload.failed'))
}

const clearFile = () => {
  form.value.filename = ''
  form.value.sheets = []
  tableList.value = []
  excelUploadSuccess.value = false

}

defineExpose({ open })
</script>
<style lang="less">
// ChatBI 数据源表单对话框 - 深色主题设计
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@dark-bg: #0f0a1a;
@dark-bg-secondary: #1a1225;
@dark-bg-card: rgba(26, 18, 37, 0.95);
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

.add-datasource_dialog {
  .ed-dialog {
    background: @dark-bg-secondary !important;
    border: 1px solid @dark-border !important;
    border-radius: 20px !important;
    box-shadow: 0 16px 64px rgba(0, 0, 0, 0.5);
  }

  .ed-dialog__header {
    background: transparent !important;
    border-bottom: 1px solid @dark-border !important;
    padding: 20px 24px !important;

    > div {
      color: @dark-text !important;
      font-weight: 600;
      font-size: 16px;
    }

    .ed-dialog__headerbtn {
      color: @dark-text-secondary !important;

      &:hover {
        color: @primary-400 !important;
      }
    }
  }

  // 步骤条深色主题
  .ed-steps {
    .ed-step__head {
      &.is-finish {
        .ed-step__icon {
          background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%) !important;
          border-color: transparent !important;
          color: #fff !important;
        }

        .ed-step__line {
          background-color: @primary-500 !important;
        }
      }

      &.is-process {
        .ed-step__icon {
          background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%) !important;
          border-color: transparent !important;
          color: #fff !important;
        }
      }

      &.is-wait {
        .ed-step__icon {
          background: rgba(139, 92, 246, 0.1) !important;
          border-color: @dark-border !important;
          color: @dark-text-muted !important;
        }
      }
    }

    .ed-step__title {
      color: @dark-text-secondary !important;
      font-weight: 500;
      font-size: 13px;

      &.is-finish,
      &.is-process {
        color: @dark-text !important;
      }
    }
  }

  .ed-dialog__body {
    background: transparent !important;
    padding: 24px !important;
  }

  .container {
    max-height: 600px;
    overflow-y: auto;

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

    .ed-vl__window.ed-select-dropdown__list::-webkit-scrollbar {
      width: 0;
      height: 0;
    }
  }

  // 表单项深色主题
  .ed-form-item {
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

    .ed-select {
      width: 100%;

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

  // 复选框列表深色主题
  .ed-checkbox-group {
    .list-item_primary {
      padding: 0 12px;
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
      }
    }
  }

  // 上传组件深色主题
  .ed-upload {
    .ed-button {
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
  }

  .el-upload__tip {
    color: @dark-text-muted !important;
  }

  // 版本支持文字
  span {
    color: @dark-text-muted;
    font-size: 13px;
  }

  // 按钮深色主题
  .ed-button {
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
  }

  // 文件卡片样式
  .file-card {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid @dark-border;
    border-radius: 12px;
    margin-bottom: 8px;
    transition: all 0.2s ease;

    &:hover {
      background: rgba(139, 92, 246, 0.12);
      border-color: rgba(139, 92, 246, 0.35);
    }

    .file-icon {
      width: 48px;
      height: 48px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-right: 12px;
      flex-shrink: 0;

      .icon-text {
        font-size: 12px;
        font-weight: 700;
        color: white;

        &.excel {
          background: linear-gradient(135deg, #1d6f42 0%, #22c55e 100%);
          padding: 14px 8px;
          border-radius: 8px;
        }

        &.csv {
          background: linear-gradient(135deg, #0e7490 0%, #06b6d4 100%);
          padding: 14px 8px;
          border-radius: 8px;
        }

        &.doc {
          background: linear-gradient(135deg, #c62828 0%, #2b579a 100%);
          padding: 14px 8px;
          border-radius: 8px;
        }

        &.pdf {
          background: linear-gradient(135deg, #c62828 0%, #ef4444 100%);
          padding: 14px 8px;
          border-radius: 8px;
        }
      }
    }

    .file-info {
      flex: 1;
      min-width: 0;

      .file-name {
        font-size: 14px;
        font-weight: 500;
        color: @dark-text;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 4px;
      }

      .file-meta {
        font-size: 12px;
        color: @dark-text-muted;
      }
    }

    .delete-icon {
      color: @dark-text-muted;
      cursor: pointer;
      transition: all 0.2s ease;
      flex-shrink: 0;

      &:hover {
        color: #ef4444;
        transform: scale(1.1);
      }
    }
  }

  .upload-tip {
    font-size: 12px;
    color: @dark-text-muted;
    margin-top: 8px;
  }
}
</style>