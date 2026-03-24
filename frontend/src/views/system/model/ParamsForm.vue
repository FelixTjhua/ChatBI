<script lang="ts" setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const paramsRef = ref()
const paramsForm = reactive({
  name: '',
  key: '',
  val: '',
  id: '',
})

const rules = {
  name: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + t('model.display_name'),
      trigger: 'blur',
    },
  ],
  key: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + t('model.parameters'),
      trigger: 'blur',
    },
  ],
  val: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + t('model.parameter_value'),
      trigger: 'blur',
    },
  ],
}

const initForm = (item: any) => {
  if (item) {
    Object.assign(paramsForm, { ...item })
  }
  if (!paramsForm.id) {
    paramsForm.id = `${+new Date()}`
  }
  paramsRef.value.clearValidate()
}

const emits = defineEmits(['submit'])

const submit = () => {
  paramsRef.value.validate((res: any) => {
    if (res) {
      emits('submit', paramsForm)
    }
  })
}

const close = () => {
  paramsForm.name = ''
  paramsForm.key = ''
  paramsForm.val = ''
  paramsForm.id = ''
}
defineExpose({
  initForm,
  submit,
  close,
})
</script>

<template>
  <div class="params-form">
    <el-form
      ref="paramsRef"
      :rules="rules"
      label-position="top"
      :model="paramsForm"
      style="width: 100%"
      @submit.prevent
    >
      <el-form-item prop="key" :label="$t('model.parameters')">
        <el-input
          v-model="paramsForm.key"
          clearable
          :placeholder="$t('datasource.please_enter') + $t('common.empty') + $t('model.parameters')"
        />
      </el-form-item>
      <el-form-item prop="name" :label="$t('model.display_name')">
        <el-input
          v-model="paramsForm.name"
          clearable
          :placeholder="
            $t('datasource.please_enter') + $t('common.empty') + $t('model.display_name')
          "
        />
      </el-form-item>
      <el-form-item prop="val" :label="$t('model.parameter_value')">
        <el-input
          v-model="paramsForm.val"
          clearable
          :placeholder="
            $t('datasource.please_enter') + $t('common.empty') + $t('model.parameter_value')
          "
        />
      </el-form-item>
    </el-form>
  </div>
</template>

<style lang="less" scoped>
// ChatBI 参数表单 - 深色主题设计
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

.params-form {
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

    .ed-input__inner {
      color: @dark-text !important;

      &::placeholder {
        color: @dark-text-muted !important;
      }
    }

    .ed-form-item__error {
      color: #f87171;
    }
  }

  .ed-input-number {
    width: 100%;

    :deep(.ed-input__wrapper) {
      background: rgba(139, 92, 246, 0.08) !important;
    }

    :deep(.ed-input-number__decrease),
    :deep(.ed-input-number__increase) {
      background: rgba(139, 92, 246, 0.1) !important;
      border-color: @dark-border !important;
      color: @dark-text-secondary !important;

      &:hover {
        color: @primary-400 !important;
      }
    }
  }
}
</style>
