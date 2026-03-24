<script lang="ts" setup>
import { ref, nextTick } from 'vue'
import { datasourceApi } from '@/api/datasource'
import { useI18n } from 'vue-i18n'
import icon_close_outlined from '@/assets/svg/operate/ope-close.svg'
import DatasourceList from './DatasourceList.vue'
import DatasourceForm from './DatasourceForm.vue'

const { t } = useI18n()
const datasourceConfigVisible = ref(false)
const activeStep = ref(0)
const currentType = ref('')
const editDatasource = ref(false)
const activeName = ref('')
const activeType = ref('')
const datasourceFormRef = ref()

const beforeClose = () => {
  datasourceConfigVisible.value = false
  activeStep.value = 0
  datasourceApi.cancelRequests()
}
const clickDatasource = (ele: any) => {
  activeStep.value = 1
  activeName.value = ele.name
  activeType.value = ele.type
}

const emits = defineEmits(['search'])

const refresh = () => {
  activeName.value = ''
  activeStep.value = 0
  activeType.value = ''
  datasourceConfigVisible.value = false
  emits('search')
}

const handleEditDatasource = (res: any) => {
  activeStep.value = 1
  datasourceConfigVisible.value = true
  editDatasource.value = true
  currentType.value = res.type_name
  nextTick(() => {
    datasourceFormRef.value.initForm(res)
  })
}

const handleAddDatasource = () => {
  editDatasource.value = false
  datasourceConfigVisible.value = true
}

const changeActiveStep = (val: number) => {
  activeStep.value = val > 2 ? 2 : val
}

defineExpose({
  handleEditDatasource,
  handleAddDatasource,
})
</script>

<template>
  <el-drawer
    v-model="datasourceConfigVisible"
    :close-on-click-modal="false"
    destroy-on-close
    size="calc(100% - 100px)"
    modal-class="datasource-drawer-fullscreen"
    direction="btt"
    :before-close="beforeClose"
    :show-close="false"
  >
    <template #header="{ close }">
      <span style="white-space: nowrap">{{
        editDatasource
          ? t('datasource.mysql_data_source', { msg: currentType })
          : $t('datasource.new_data_source')
      }}</span>
      <div v-if="!editDatasource" class="flex-center" style="width: 100%">
        <el-steps custom style="max-width: 800px; flex: 1" :active="activeStep" align-center>
          <el-step>
            <template #title> {{ $t('qa.select_datasource') }} </template>
          </el-step>
          <el-step>
            <template #title> {{ $t('datasource.configuration_information') }} </template>
          </el-step>
          <el-step>
            <template #title> {{ $t('ds.form.choose_tables') }} </template>
          </el-step>
        </el-steps>
      </div>
      <el-icon class="ed-dialog__headerbtn mrt" style="cursor: pointer" @click="close">
        <icon_close_outlined></icon_close_outlined>
      </el-icon>
    </template>
    <DatasourceList v-if="activeStep === 0" @click-datasource="clickDatasource"></DatasourceList>
    <DatasourceForm
      v-if="[1, 2].includes(activeStep)"
      ref="datasourceFormRef"
      :is-data-table="false"
      :active-step="activeStep"
      :active-name="activeName"
      :active-type="activeType"
      @refresh="refresh"
      @close="beforeClose"
      @change-active-step="changeActiveStep"
    ></DatasourceForm>
  </el-drawer>
</template>

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

// 数据源抽屉 - 深色主题
.datasource-drawer-fullscreen {
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

    .ed-dialog__headerbtn {
      color: @dark-text-secondary !important;

      &:hover {
        color: @primary-400 !important;
      }
    }
  }

  .ed-drawer__body {
    padding: 0;
    background: @dark-bg-secondary !important;
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

      &.is-finish,
      &.is-process {
        color: @dark-text !important;
      }

      &.is-wait {
        color: @dark-text-muted !important;
      }
    }
  }

  // 关闭按钮
  .mrt {
    color: @dark-text-secondary !important;
    transition: all 0.2s ease;

    &:hover {
      color: @primary-400 !important;
      transform: rotate(90deg);
    }
  }
}
</style>
