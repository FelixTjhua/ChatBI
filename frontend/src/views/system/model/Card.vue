<script lang="ts" setup>
import delIcon from '@/assets/svg/icon_delete.svg'
import icon_admin_outlined from '@/assets/svg/icon_admin_outlined.svg'
import edit from '@/assets/svg/icon_edit_outlined.svg'
import { get_supplier } from '@/entity/supplier'
import { computed, ref } from 'vue'
const props = withDefaults(
  defineProps<{
    name: string
    modelType: string
    baseModel: string
    id?: string
    isDefault?: boolean
    supplier?: number
  }>(),
  {
    name: '-',
    modelType: '-',
    baseModel: '-',
    id: '-',
    isDefault: false,
    supplier: 0,
  }
)
const errorMsg = ref('')
const current_supplier = computed(() => {
  if (!props.supplier) {
    return null
  }
  return get_supplier(props.supplier)
})
const showErrorMask = (msg?: string) => {
  if (!msg) {
    return
  }
  errorMsg.value = msg
  setTimeout(() => {
    errorMsg.value = ''
  }, 3000)
}
const emits = defineEmits(['edit', 'del', 'default'])

const handleDefault = () => {
  emits('default')
}

const handleDel = () => {
  emits('del', { id: props.id, name: props.name, default_model: props.isDefault })
}

const handleEdit = () => {
  emits('edit')
}

defineExpose({ showErrorMask })
</script>

<template>
  <div
    v-loading="!!errorMsg"
    class="card"
    :element-loading-text="errorMsg"
    element-loading-custom-class="model-card-loading"
  >
    <div class="name-icon">
      <img :src="current_supplier?.icon" width="32px" height="32px" />
      <span :title="name" class="name ellipsis">{{ name }}</span>
      <span v-if="isDefault" class="default">{{ $t('model.default_model') }}</span>
    </div>
    <div class="type-value">
      <span class="type">{{ $t('model.model_type') }}</span>
      <span class="value">
        {{ modelType.startsWith('modelType.') ? $t(modelType) : modelType }}</span
      >
    </div>
    <div class="type-value">
      <span class="type">{{ $t('model.basic_model') }}</span>
      <span class="value"> {{ baseModel }}</span>
    </div>
    <div class="methods">
      <el-tooltip
        v-if="isDefault"
        effect="dark"
        :content="$t('common.the_default_model')"
        placement="top"
      >
        <el-button secondary disabled>
          <el-icon style="margin-right: 4px" size="16">
            <icon_admin_outlined></icon_admin_outlined>
          </el-icon>
          {{ $t('common.as_default_model') }}
        </el-button>
      </el-tooltip>

      <el-button v-else secondary @click="handleDefault">
        <el-icon style="margin-right: 4px" size="16">
          <icon_admin_outlined></icon_admin_outlined>
        </el-icon>
        {{ $t('common.as_default_model') }}
      </el-button>
      <el-button secondary @click="handleEdit">
        <el-icon style="margin-right: 4px" size="16">
          <edit></edit>
        </el-icon>
        {{ $t('dashboard.edit') }}
      </el-button>
      <el-button secondary @click="handleDel">
        <el-icon style="margin-right: 4px" size="16">
          <delIcon></delIcon>
        </el-icon>
        {{ $t('dashboard.delete') }}
      </el-button>
    </div>
  </div>
</template>

<style lang="less" scoped>
// ChatBI 模型卡片 - 深色主题设计
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@dark-bg-card: rgba(26, 18, 37, 0.85);
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

.card {
  width: 100%;
  min-height: 180px;
  background: @dark-bg-card;
  backdrop-filter: blur(16px);
  border: 1.5px solid @dark-border;
  padding: 20px;
  border-radius: 16px;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;

  // 顶部渐变条
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, @primary-600 0%, @primary-500 50%, @primary-400 100%);
    opacity: 0.6;
    transition: all 0.3s ease;
  }

  &:hover {
    border-color: rgba(139, 92, 246, 0.4);
    box-shadow:
      0 12px 40px rgba(0, 0, 0, 0.4),
      0 0 0 1px rgba(139, 92, 246, 0.15),
      0 0 30px rgba(139, 92, 246, 0.1);
    transform: translateY(-4px);

    &::before {
      height: 4px;
      opacity: 1;
    }

    .methods {
      display: flex;
    }
  }

  .name-icon {
    display: flex;
    align-items: center;
    margin-bottom: 16px;
    gap: 12px;

    img {
      border-radius: 10px;
      padding: 6px;
      background: rgba(139, 92, 246, 0.15);
      border: 1px solid rgba(139, 92, 246, 0.2);
      flex-shrink: 0;
    }

    .name {
      font-weight: 600;
      font-size: 15px;
      line-height: 22px;
      flex: 1;
      min-width: 0;
      color: @dark-text;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .default {
      flex-shrink: 0;
      background: linear-gradient(
        135deg,
        rgba(139, 92, 246, 0.2) 0%,
        rgba(168, 85, 247, 0.15) 100%
      );
      padding: 4px 12px;
      border-radius: 8px;
      color: @primary-400;
      font-weight: 600;
      font-size: 11px;
      line-height: 16px;
      letter-spacing: 0.3px;
      border: 1px solid rgba(139, 92, 246, 0.25);
    }
  }

  .type-value {
    margin-top: 10px;
    display: flex;
    align-items: center;
    font-size: 13px;
    line-height: 20px;

    .type {
      color: @dark-text-muted;
      min-width: 65px;
      flex-shrink: 0;
    }

    .value {
      margin-left: 10px;
      color: @dark-text-secondary;
      font-weight: 500;
      background: rgba(139, 92, 246, 0.1);
      border: 1px solid rgba(139, 92, 246, 0.15);
      padding: 3px 10px;
      border-radius: 6px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .methods {
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px solid @dark-border;
    align-items: center;
    display: none;
    flex-wrap: wrap;
    gap: 8px;

    :deep(.ed-button) {
      border-radius: 8px;
      font-size: 12px;
      padding: 6px 12px;
      height: 32px;
      transition: all 0.25s ease;
      flex: 1;
      min-width: 0;

      &.is-secondary {
        background: rgba(139, 92, 246, 0.1) !important;
        border: 1px solid @dark-border !important;
        color: @dark-text-secondary !important;

        &:hover:not(.is-disabled) {
          background: rgba(139, 92, 246, 0.2) !important;
          border-color: rgba(139, 92, 246, 0.35) !important;
          color: @primary-400 !important;
        }

        &.is-disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      }

      .ed-icon {
        margin-right: 4px;
        color: inherit;
      }

      span {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }

  :deep(.model-card-loading) {
    border-radius: 16px;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    align-items: end;
    background-color: rgba(15, 10, 26, 0.95);

    .ed-loading-spinner {
      top: auto;
      margin: 12px 8px;
      display: flex;
      position: relative;
      justify-content: flex-end;
      align-items: center;
      width: calc(100% - 16px);
    }

    svg {
      display: none;
    }

    p {
      text-align: left;
      color: #f87171;
      font-size: 12px;
      line-height: 1.5;
    }
  }
}

// 响应式适配 - 平板
@media (max-width: 1200px) {
  .card {
    .methods {
      :deep(.ed-button) {
        font-size: 11px;
        padding: 5px 10px;
      }
    }
  }
}

// 响应式适配 - 手机
@media (max-width: 768px) {
  .card {
    padding: 16px;
    min-height: auto;
    border-radius: 14px;

    .name-icon {
      flex-wrap: wrap;

      .name {
        flex: 1;
        min-width: calc(100% - 50px);
      }

      .default {
        order: 3;
        width: 100%;
        text-align: center;
        margin-top: 8px;
      }
    }

    .methods {
      display: flex;

      :deep(.ed-button) {
        min-width: calc(50% - 4px);
      }
    }
  }
}

// 超小屏幕
@media (max-width: 480px) {
  .card {
    .methods {
      :deep(.ed-button) {
        min-width: 100%;
      }
    }
  }
}
</style>
