<script lang="ts" setup>
import { ref, computed, shallowRef, reactive, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus-secondary'
import icon_searchOutline_outlined from '@/assets/svg/icon_search-outline_outlined.svg'
import icon_admin_outlined from '@/assets/svg/icon_admin_outlined.svg'
import icon_add_outlined from '@/assets/svg/icon_add_outlined.svg'
import EmptyBackground from '@/components/EmptyBackground.vue'
import icon_done_outlined from '@/assets/svg/icon_done_outlined.svg'
import icon_close_outlined from '@/assets/svg/operate/ope-close.svg'
import ModelList from './ModelList.vue'
import ModelListSide from './ModelListSide.vue'
import ModelForm from './ModelForm.vue'
import { modelApi } from '@/api/system'
import Card from './Card.vue'
import { getModelTypeName } from '@/entity/CommonEntity.ts'
import { useI18n } from 'vue-i18n'
import { get_supplier } from '@/entity/supplier'

interface Model {
  name: string
  model_type: string
  base_model: string
  id?: string
  default_model: boolean
  supplier: number
}

const { t } = useI18n()
const keywords = ref('')
const defaultModelKeywords = ref('')
const modelConfigvVisible = ref(false)
const searchLoading = ref(false)
const editModel = ref(false)
const activeStep = ref(0)
const activeName = ref('')
const activeNameI18nKey = ref('')
const activeType = ref('')
const modelFormRef = ref()
const cardRefs = ref<any[]>([])
const showCardError = ref(false) // if you don`t want card mask error, just change this to false
reactive({
  form: {
    id: '',
    name: '',
    model_type: 0,
    api_key: '',
    api_domain: '',
  },
  selectedIds: [],
})
const modelList = shallowRef([] as Model[])

const modelListWithSearch = computed(() => {
  if (!keywords.value) return modelList.value
  return modelList.value.filter((ele) =>
    ele.name.toLowerCase().includes(keywords.value.toLowerCase())
  )
})
const beforeClose = () => {
  modelConfigvVisible.value = false
}
const defaultModelListWithSearch = computed(() => {
  let tempModelList = modelList.value
  if (defaultModelKeywords.value) {
    tempModelList = tempModelList.filter((ele) =>
      ele.name.toLowerCase().includes(defaultModelKeywords.value.toLowerCase())
    )
  }
  return tempModelList.map((item: any) => {
    item['supplier_item'] = get_supplier(item.supplier)
    return item
  })
})

const modelCheckHandler = async (item: any) => {
  const response = await modelApi.check(item)
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let checkTimeout = false
  setTimeout(() => {
    checkTimeout = true
  }, 9000)
  let checkMsg = ''
  while (true) {
    if (checkTimeout) {
      break
    }
    const { done, value } = await reader.read()
    if (done) break
    const lines = decoder.decode(value).trim().split('\n')
    for (const line of lines) {
      const data = JSON.parse(line)
      if (data.error) {
        checkMsg += data.error
      } else if (data.content) {
        // Stream content received
      }
    }
  }
  if (!checkMsg) {
    return
  }
  // Model check failed
  if (!showCardError.value) {
    ElMessage.error(checkMsg)
    return
  }
  nextTick(() => {
    const index = modelListWithSearch.value.findIndex((el: any) => el.id === item.id)
    if (index > -1) {
      const currentRef = cardRefs.value[index]
      currentRef?.showErrorMask(checkMsg)
    }
  })
}
const duplicateName = async (item: any) => {
  const res = await modelApi.queryAll()
  const names = res.filter((ele: any) => ele.id !== item.id).map((ele: any) => ele.name)
  if (names.includes(item.name)) {
    ElMessage.error(t('common.duplicate_name'))
    return
  }
  const param = {
    ...item,
  }
  if (!item.id) {
    modelApi.add(param).then(() => {
      beforeClose()
      search()
      ElMessage({
        type: 'success',
        message: t('workspace.add_successfully'),
      })
      modelCheckHandler(item)
    }).catch(() => {
      ElMessage.error(t('common.save_failed'))
    })
    return
  }
  modelApi.edit(param).then(() => {
    beforeClose()
    search()
    ElMessage({
      type: 'success',
      message: t('common.save_success'),
    })
    modelCheckHandler(item)
  }).catch(() => {
    ElMessage.error(t('common.save_failed'))
  })
}

const handleDefaultModelChange = (item: any) => {
  const current_default_node = modelList.value.find((ele: Model) => ele.default_model)
  if (current_default_node?.id === item.id) {
    return
  }
  ElMessageBox.confirm(t('model.system_default_model', { msg: item.name }), {
    confirmButtonType: 'primary',
    tip: t('model.operate_with_caution'),
    confirmButtonText: t('datasource.confirm'),
    cancelButtonText: t('common.cancel'),
    customClass: 'confirm-no_icon',
    autofocus: false,
    showClose: false,
    callback: (val: string) => {
      if (val === 'confirm') {
        modelApi.setDefault(item.id).then(() => {
          ElMessage.success(t('model.set_successfully'))
          search()
        }).catch(() => {
          ElMessage.error(t('common.save_failed'))
        })
      }
    },
  })
}

const formatKeywords = (item: string) => {
  if (!defaultModelKeywords.value) return item
  // 转义HTML特殊字符防止XSS
  const escapeHtml = (str: string) =>
    str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  const safeItem = escapeHtml(item)
  const safeKeyword = escapeHtml(defaultModelKeywords.value)
  return safeItem.replaceAll(
    safeKeyword,
    `<span class="isSearch">${safeKeyword}</span>`
  )
}
const handleAddModel = () => {
  activeStep.value = 0
  editModel.value = false
  modelConfigvVisible.value = true
}
const handleEditModel = (row: any) => {
  activeStep.value = 1
  editModel.value = true
  activeType.value = row.supplier
  activeName.value = row.supplier_item.name
  activeNameI18nKey.value = row.supplier_item.i18nKey
  modelApi.query(row.id).then((res: any) => {
    modelConfigvVisible.value = true
    nextTick(() => {
      modelFormRef.value.initForm({ ...res })
    })
  }).catch(() => {
    ElMessage.error(t('common.load_failed'))
  })
}

const handleDefault = (row: any) => {
  if (row.default_model) return
  ElMessageBox.confirm(t('model.system_default_model', { msg: row.name }), {
    confirmButtonType: 'primary',
    tip: t('model.operate_with_caution'),
    confirmButtonText: t('datasource.confirm'),
    cancelButtonText: t('common.cancel'),
    customClass: 'confirm-no_icon',
    autofocus: false,
    showClose: false,
    callback: (val: string) => {
      if (val === 'confirm') {
        modelApi.setDefault(row.id).then(() => {
          ElMessage.success(t('model.set_successfully'))
          search()
        }).catch(() => {
          ElMessage.error(t('common.save_failed'))
        })
      }
    },
  })
}

const deleteHandler = (item: any) => {
  if (item.default_model) {
    ElMessageBox.confirm(t('model.del_default_tip', { msg: item.name }), {
      confirmButtonType: 'primary',
      tip: t('model.del_default_warn'),
      showConfirmButton: false,
      confirmButtonText: t('datasource.confirm'),
      cancelButtonText: t('datasource.got_it'),
      customClass: 'confirm-no_icon',
      autofocus: false,
      showClose: false,
      callback: (_val: string) => {
        // User acknowledged the message
      },
    })
    return
  }
  ElMessageBox.confirm(t('model.del_warn_tip', { msg: item.name }), {
    confirmButtonType: 'danger',
    confirmButtonText: t('dashboard.delete'),
    cancelButtonText: t('common.cancel'),
    customClass: 'confirm-no_icon',
    autofocus: false,
    showClose: false,
    callback: (value: string) => {
      if (value === 'confirm') {
        modelApi.delete(item.id).then(() => {
          ElMessage({
            type: 'success',
            message: t('dashboard.delete_success'),
          })
          search()
        }).catch(() => {
          ElMessage.error(t('common.delete_failed'))
        })
      }
    },
  })
}

const clickModel = (ele: any) => {
  activeStep.value = 1
  supplierChang(ele)
}

const supplierChang = (ele: any) => {
  activeName.value = ele.name
  activeNameI18nKey.value = ele.i18nKey
  nextTick(() => {
    modelFormRef.value.supplierChang({ ...ele })
  })
}

const cancel = () => {
  beforeClose()
}

const preStep = () => {
  activeStep.value = 0
}

const saveModel = () => {
  modelFormRef.value.submitModel()
}
const setCardRef = (el: any, index: number) => {
  if (el) {
    cardRefs.value[index] = el
  }
}
const search = () => {
  searchLoading.value = true
  modelApi
    .queryAll()
    .then((res: any) => {
      modelList.value = res
    })
    .catch(() => {
      ElMessage.error(t('common.load_failed'))
    })
    .finally(() => {
      searchLoading.value = false
    })
}
search()

const submit = (item: any) => {
  duplicateName(item)
}
</script>

<template>
  <div class="model-config no-padding">
    <!-- 页面标题 -->
    <div class="chatbi-page-title">
      <span class="title-text">{{ t('model.ai_model_configuration') }}</span>
    </div>
    
    <div class="model-methods">
      <div class="button-input">
        <el-input
          v-model="keywords"
          clearable
          style="width: 240px; margin-right: 12px"
          :placeholder="$t('datasource.search')"
        >
          <template #prefix>
            <el-icon>
              <icon_searchOutline_outlined class="svg-icon" />
            </el-icon>
          </template>
        </el-input>

        <el-popover popper-class="system-default_model" placement="bottom-end">
          <template #reference>
            <el-button secondary>
              <template #icon>
                <icon_admin_outlined></icon_admin_outlined>
              </template>
              {{ t('model.system_default_model_de') }}
            </el-button></template
          >
          <div class="popover">
            <el-input
              v-model="defaultModelKeywords"
              clearable
              style="width: 100%; margin-right: 12px"
              :placeholder="t('datasource.search_by_name')"
            >
              <template #prefix>
                <el-icon>
                  <icon_searchOutline_outlined class="svg-icon" />
                </el-icon>
              </template>
            </el-input>
            <div class="popover-content">
              <div
                v-for="ele in defaultModelListWithSearch"
                :key="ele.name"
                class="popover-item"
                :class="ele.default_model && 'isActive'"
                @click="handleDefaultModelChange(ele)"
              >
                <img :src="ele.supplier_item.icon" width="24px" height="24px" />
                <div class="model-name ellipsis" v-html="formatKeywords(ele.name)"></div>
                <el-icon size="16" class="done">
                  <icon_done_outlined></icon_done_outlined>
                </el-icon>
              </div>
              <div v-if="!defaultModelListWithSearch.length" class="popover-item empty">
                {{ t('model.relevant_results_found') }}
              </div>
            </div>
          </div>
        </el-popover>

        <el-button type="primary" @click="handleAddModel">
          <template #icon>
            <icon_add_outlined></icon_add_outlined>
          </template>
          {{ t('model.add_model') }}
        </el-button>
      </div>
    </div>
    <EmptyBackground
      v-if="!!keywords && !modelListWithSearch.length"
      :description="$t('datasource.relevant_content_found')"
      img-type="tree"
    />
    <div v-else class="card-content">
      <el-row :gutter="16" class="w-full">
        <el-col
          v-for="(ele, index) in modelListWithSearch"
          :key="ele.id"
          :xs="24"
          :sm="12"
          :md="12"
          :lg="8"
          :xl="6"
          class="mb-16"
        >
          <card
            :id="ele.id"
            :ref="(el: any) => setCardRef(el, index)"
            :key="ele.id"
            :name="ele.name"
            :supplier="ele.supplier"
            :model-type="getModelTypeName(ele['model_type'])"
            :base-model="ele['base_model']"
            :is-default="ele['default_model']"
            @edit="handleEditModel(ele)"
            @del="deleteHandler"
            @default="handleDefault(ele)"
          ></card>
        </el-col>
      </el-row>
    </div>
    <template v-if="!keywords && !modelListWithSearch.length && !searchLoading">
      <EmptyBackground
        class="datasource-yet"
        :description="$t('common.no_model_yet')"
        img-type="noneWhite"
      />

      <div style="text-align: center; margin-top: -10px">
        <el-button type="primary" @click="handleAddModel">
          <template #icon>
            <icon_add_outlined></icon_add_outlined>
          </template>
          {{ t('model.add_model') }}
        </el-button>
      </div>
    </template>
    <el-drawer
      v-model="modelConfigvVisible"
      :close-on-click-modal="false"
      size="calc(100% - 100px)"
      modal-class="model-drawer-fullscreen"
      direction="btt"
      destroy-on-close
      :before-close="beforeClose"
      :show-close="false"
    >
      <template #header="{ close }">
        <span style="white-space: nowrap">{{
          editModel
            ? $t('dashboard.edit') + $t('common.empty') + $t(activeNameI18nKey)
            : t('model.add_model')
        }}</span>
        <div v-if="!editModel" class="flex-center" style="width: 100%">
          <el-steps custom style="max-width: 500px; flex: 1" :active="activeStep" align-center>
            <el-step>
              <template #title> {{ t('model.select_supplier') }} </template>
            </el-step>
            <el-step>
              <template #title> {{ t('model.add_model') }} </template>
            </el-step>
          </el-steps>
        </div>
        <el-icon class="ed-dialog__headerbtn mrt" style="cursor: pointer" @click="close">
          <icon_close_outlined></icon_close_outlined>
        </el-icon>
      </template>
      <ModelList v-if="activeStep === 0" @click-model="clickModel"></ModelList>
      <ModelListSide
        v-if="activeStep === 1 && !editModel"
        :active-name="activeName"
        :active-type="activeType"
        @click-model="supplierChang"
      ></ModelListSide>
      <ModelForm
        v-if="activeStep === 1 && modelConfigvVisible"
        ref="modelFormRef"
        :active-name="activeName"
        :active-type="activeType"
        :edit-model="editModel"
        @submit="submit"
      ></ModelForm>
      <template v-if="activeStep !== 0" #footer>
        <el-button secondary @click="cancel"> {{ $t('common.cancel') }} </el-button>
        <el-button v-if="!editModel" secondary @click="preStep">
          {{ $t('ds.previous') }}
        </el-button>
        <el-button type="primary" @click="saveModel"> {{ $t('common.save') }} </el-button>
      </template>
    </el-drawer>
  </div>
</template>

<style lang="less" scoped>
// ChatBI 模型配置页面 - 深色主题设计
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

.model-config {
  height: 100%;
  padding: 20px 24px;
  background: linear-gradient(180deg, @dark-bg 0%, @dark-bg-secondary 100%);
  overflow: hidden;

  .datasource-yet {
    padding-bottom: 0;
    height: auto;
    padding-top: 120px;

    :deep(.ed-empty__description) {
      color: @dark-text-muted;
    }
  }

  .model-methods {
    display: flex;
    align-items: center;
    justify-content: flex-start;  // 改为左对齐
    margin-bottom: 20px;
    gap: 12px;  // 减少间距
    flex-shrink: 0;

    .button-input {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;

      :deep(.ed-input__wrapper),
      :deep(.el-input__wrapper) {
        background: rgba(139, 92, 246, 0.08) !important;
        backdrop-filter: blur(12px);
        border: 1.5px solid @dark-border !important;
        border-radius: 12px;
        box-shadow: none !important;
        transition: all 0.25s ease;

        &:hover {
          border-color: rgba(139, 92, 246, 0.35) !important;
        }

        &:focus-within,
        &.is-focus {
          border-color: @primary-500 !important;
          box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15) !important;
        }
      }

      :deep(.ed-input__inner),
      :deep(.el-input__inner) {
        color: @dark-text !important;

        &::placeholder {
          color: @dark-text-muted !important;
        }
      }

      :deep(.ed-button.is-secondary),
      :deep(.el-button.is-secondary),
      :deep(.ed-button--default),
      :deep(.el-button--default) {
        background: rgba(139, 92, 246, 0.1) !important;
        backdrop-filter: blur(12px);
        border: 1.5px solid @dark-border !important;
        border-radius: 12px;
        color: @dark-text-secondary !important;
        transition: all 0.25s ease;

        &:hover {
          border-color: rgba(139, 92, 246, 0.35) !important;
          background: rgba(139, 92, 246, 0.18) !important;
          color: @primary-400 !important;
        }
      }

      :deep(.ed-button--primary),
      :deep(.el-button--primary) {
        background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%) !important;
        border: none !important;
        border-radius: 12px;
        box-shadow: 0 4px 16px rgba(139, 92, 246, 0.35);
        transition: all 0.25s ease;

        &:hover {
          background: linear-gradient(135deg, @primary-500 0%, @primary-400 100%) !important;
          box-shadow: 0 6px 24px rgba(139, 92, 246, 0.45);
          transform: translateY(-2px);
        }
      }
    }
  }

  .card-content {
    max-height: calc(100% - 80px);
    overflow-y: auto;
    padding: 0 8px 20px 0;

    .w-full {
      width: 100%;
    }

    .mb-16 {
      margin-bottom: 20px;
    }

    // 深色滚动条
    &::-webkit-scrollbar {
      width: 6px;
    }

    &::-webkit-scrollbar-track {
      background: rgba(139, 92, 246, 0.05);
      border-radius: 3px;
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
  }
}

// 响应式适配 - 平板
@media (max-width: 1024px) {
  .model-config {
    padding: 16px;

    .model-methods {
      .button-input {
        :deep(.ed-input),
        :deep(.el-input) {
          flex: 1;
          min-width: 160px;
        }
      }
    }

    .card-content {
      padding: 0 4px 16px 0;
    }
  }
}

// 响应式适配 - 手机
@media (max-width: 768px) {
  .model-config {
    padding: 16px 12px;

    .model-methods {
      margin-bottom: 16px;
      justify-content: stretch;

      .button-input {
        width: 100%;
        gap: 10px;

        :deep(.ed-input),
        :deep(.el-input) {
          width: 100%;
          margin-right: 0 !important;
        }

        :deep(.ed-button),
        :deep(.el-button) {
          flex: 1;
        }
      }
    }

    .card-content {
      max-height: calc(100% - 100px);
      padding-right: 0;
    }
  }
}

// 超小屏幕
@media (max-width: 480px) {
  .model-config {
    .model-methods {
      .button-input {
        flex-direction: column;
        gap: 8px;

        :deep(.ed-input),
        :deep(.el-input) {
          width: 100%;
        }

        :deep(.ed-button),
        :deep(.el-button) {
          width: 100%;
        }
      }
    }
  }
}
</style>

<style lang="less">
// 深色主题变量
@dark-bg: #0f0a1a;
@dark-bg-secondary: #1a1225;
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;

// 确保模型配置页面标题使用统一的紫色渐变（由全局 page-titles.less 提供）

// 系统默认模型弹窗 - 深色主题
.system-default_model.system-default_model {
  padding: 8px;
  width: 340px !important;
  background: @dark-bg-secondary !important;
  backdrop-filter: blur(16px);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.5),
    0 0 0 1px @dark-border;
  border: 1px solid @dark-border !important;
  border-radius: 14px !important;

  .ed-input {
    margin-bottom: 8px;

    .ed-input__wrapper {
      background: rgba(139, 92, 246, 0.08) !important;
      border: 1px solid @dark-border !important;
      border-radius: 10px;
      box-shadow: none !important;

      &:hover {
        border-color: rgba(139, 92, 246, 0.35) !important;
      }

      &:focus-within {
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

    .ed-input__prefix {
      color: @dark-text-muted;
    }
  }

  .popover {
    .popover-content {
      padding: 4px;
      max-height: 320px;
      overflow-y: auto;

      // 深色滚动条
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

    .popover-item {
      height: 42px;
      display: flex;
      align-items: center;
      padding: 0 12px;
      margin-bottom: 4px;
      position: relative;
      border-radius: 10px;
      cursor: pointer;
      color: @dark-text-secondary;
      transition: all 0.2s ease;

      &:not(.empty):hover {
        background: rgba(139, 92, 246, 0.15);
        color: @dark-text;
      }

      &.empty {
        font-size: 14px;
        color: @dark-text-muted;
        cursor: default;
        justify-content: center;
      }

      img {
        border-radius: 8px;
        padding: 2px;
        background: rgba(139, 92, 246, 0.1);
        flex-shrink: 0;
      }

      .model-name {
        margin-left: 12px;
        font-size: 14px;
        font-weight: 500;
        flex: 1;
        min-width: 0;
        color: @dark-text-secondary;
      }

      .done {
        margin-left: auto;
        display: none;
        color: @primary-400;
        flex-shrink: 0;
      }

      .isSearch {
        color: @primary-400;
        font-weight: 600;
      }

      &.isActive {
        background: rgba(139, 92, 246, 0.2);
        color: @primary-400;

        .model-name {
          color: @primary-400;
          font-weight: 600;
        }

        .done {
          display: block;
        }
      }
    }
  }
}

// 模型抽屉 - 深色主题
.model-drawer-fullscreen {
  background: rgba(0, 0, 0, 0.6) !important;

  .ed-drawer {
    background: @dark-bg-secondary !important;
    border-top: 1px solid @dark-border !important;
    border-radius: 24px 24px 0 0 !important;
    box-shadow: 0 -8px 40px rgba(0, 0, 0, 0.5);
  }

  .ed-drawer__header {
    background: transparent !important;
    border-bottom: 1px solid @dark-border !important;
    padding: 20px 24px !important;

    span {
      color: @dark-text !important;
      font-weight: 600;
      font-size: 18px;
    }

    .ed-dialog__headerbtn,
    .mrt {
      color: @dark-text-secondary !important;

      &:hover {
        color: @primary-400 !important;
        transform: rotate(90deg);
      }
    }
  }

  .ed-drawer__body {
    padding: 0;
    background: @dark-bg-secondary !important;
  }

  .ed-drawer__footer {
    background: @dark-bg-secondary !important;
    border-top: 1px solid @dark-border !important;
    padding: 20px 24px !important;

    .ed-button--default,
    .ed-button.is-secondary {
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

    .ed-button--primary {
      background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%) !important;
      border: none !important;
      border-radius: 10px;
      box-shadow: 0 4px 16px rgba(139, 92, 246, 0.35);

      &:hover {
        box-shadow: 0 6px 24px rgba(139, 92, 246, 0.45);
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
          box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.2);
        }

        .ed-step__line {
          background-color: @primary-500 !important;
        }
      }

      &.is-wait {
        .ed-step__icon {
          background: rgba(139, 92, 246, 0.1) !important;
          border-color: @dark-border !important;
          color: @dark-text-muted !important;
        }

        .ed-step__line {
          background-color: @dark-border !important;
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

      &.is-wait {
        color: @dark-text-muted !important;
      }
    }
  }
}

// 确认对话框 - 深色主题
.confirm-no_icon {
  background: @dark-bg-secondary !important;
  border: 1px solid @dark-border !important;
  border-radius: 16px !important;
  padding: 24px;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.5);

  .ed-message-box__header,
  .el-message-box__header {
    padding-bottom: 16px;

    .ed-message-box__title,
    .el-message-box__title {
      color: @dark-text !important;
      font-weight: 600;
    }
  }

  .ed-message-box__content,
  .el-message-box__content {
    color: @dark-text-secondary !important;
  }

  .tip {
    margin-top: 16px;
    padding: 12px 16px;
    background: rgba(139, 92, 246, 0.1);
    border: 1px solid @dark-border;
    border-radius: 10px;
    color: @dark-text-secondary;
    font-size: 13px;
    line-height: 1.5;
  }

  .ed-message-box__btns,
  .el-message-box__btns {
    padding-top: 20px;

    .ed-button--default,
    .el-button--default {
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

    .ed-button--primary,
    .el-button--primary {
      background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%) !important;
      border: none !important;
      border-radius: 10px;
      box-shadow: 0 4px 16px rgba(139, 92, 246, 0.35);

      &:hover {
        box-shadow: 0 6px 24px rgba(139, 92, 246, 0.45);
      }
    }

    .ed-button--danger,
    .el-button--danger {
      background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%) !important;
      border: none !important;
      border-radius: 10px;
      box-shadow: 0 4px 16px rgba(239, 68, 68, 0.35);

      &:hover {
        box-shadow: 0 6px 24px rgba(239, 68, 68, 0.45);
      }
    }
  }
}
</style>
