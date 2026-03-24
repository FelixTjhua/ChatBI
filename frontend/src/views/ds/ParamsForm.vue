<script lang="ts" setup>
import { nextTick, ref } from 'vue'
import DatasourceForm from './DatasourceForm.vue'
import icon_close_outlined from '@/assets/svg/operate/ope-close.svg'

const datasourceFormRef = ref()
const datasourceConfigVisible = ref(false)
const beforeClose = () => {
  datasourceConfigVisible.value = false
}

const emit = defineEmits(['refresh'])
const refresh = () => {
  emit('refresh')
}
const changeActiveStep = (val: any) => {
  if (val === 0) {
    datasourceConfigVisible.value = false
  }
}
const save = () => {
  datasourceFormRef.value.tableListSave()
}

const open = (item: any) => {
  datasourceConfigVisible.value = true
  nextTick(() => {
    datasourceFormRef.value.initForm(item, true)
  })
}

defineExpose({
  open,
})
</script>

<template>
  <el-drawer
    v-model="datasourceConfigVisible"
    :close-on-click-modal="false"
    size="calc(100% - 100px)"
    modal-class="datasource-drawer-fullscreen"
    direction="btt"
    :before-close="beforeClose"
    :show-close="false"
  >
    <template #header="{ close }">
      <span style="white-space: nowrap">{{ $t('ds.form.choose_tables') }}</span>
      <el-icon style="cursor: pointer" @click="close">
        <icon_close_outlined></icon_close_outlined>
      </el-icon>
    </template>
    <DatasourceForm
      ref="datasourceFormRef"
      :active-step="2"
      active-name=""
      active-type=""
      is-data-table
      @change-active-step="changeActiveStep"
      @refresh="refresh"
    ></DatasourceForm>
    <template #footer>
      <el-button secondary @click="beforeClose"> {{ $t('common.cancel') }} </el-button>
      <el-button type="primary" @click="save"> {{ $t('common.save') }} </el-button>
    </template>
  </el-drawer>
</template>

<style lang="less" scoped></style>

<style lang="less">
// ParamsForm drawer footer 深色主题
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text: rgba(255, 255, 255, 0.95);

.datasource-drawer-fullscreen {
  .ed-drawer__footer {
    border-top: 1px solid @dark-border !important;
    background: rgba(15, 10, 26, 0.9) !important;
    padding: 16px 24px !important;

    .ed-button.is-secondary,
    .ed-button--default {
      background: rgba(139, 92, 246, 0.1) !important;
      border: 1px solid @dark-border !important;
      color: @dark-text-secondary !important;
      border-radius: 10px !important;

      &:hover {
        background: rgba(139, 92, 246, 0.2) !important;
        color: @dark-text !important;
      }
    }

    .ed-button--primary {
      background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%) !important;
      border: none !important;
      border-radius: 10px !important;
      box-shadow: 0 4px 16px rgba(139, 92, 246, 0.35);

      &:hover {
        box-shadow: 0 6px 24px rgba(139, 92, 246, 0.45);
      }
    }
  }
}
</style>
