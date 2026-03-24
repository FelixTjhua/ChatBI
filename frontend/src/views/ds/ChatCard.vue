<script lang="ts" setup>
import icon_form_outlined from '@/assets/svg/icon_form_outlined.svg'
import { computed } from 'vue'
import { getDsIcon } from './js/ds-type'

const props = withDefaults(
  defineProps<{
    name: string
    type: string
    typeName: string
    num: string
    isSelected?: boolean
    description?: string
    id?: string
  }>(),
  {
    name: '-',
    type: '-',
    description: '-',
    id: '-',
    typeName: '-',
    isSelected: false,
  }
)

const emits = defineEmits(['selectDs'])
const icon = computed(() => {
  return getDsIcon(props.type)
})

const SelectDs = () => {
  emits('selectDs')
}
</script>

<template>
  <div class="card" :class="isSelected && 'is-selected'" @click="SelectDs">
    <div class="name-icon">
      <img :src="icon" width="32px" height="32px" />
      <div class="info">
        <div :title="name" class="name ellipsis">{{ name }}</div>
        <div class="type">{{ typeName }}</div>
      </div>
    </div>
    <div :title="description" class="type-value">
      {{ description }}
    </div>

    <div class="bottom-info">
      <div class="form-rate">
        <el-icon class="form-icon" size="16">
          <icon_form_outlined></icon_form_outlined>
        </el-icon>
        {{ num }} {{ type === 'pdf' ? $t('ds.doc_chunks') : $t('ds.tables') }}
      </div>
      <div click.stop class="methods"></div>
    </div>
  </div>
</template>

<style lang="less" scoped>
// 深色主题变量
@dark-bg-card: rgba(26, 18, 37, 0.9);
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);
@primary-400: #a78bfa;
@primary-500: #8b5cf6;

.card {
  width: 100%;
  border: 1px solid @dark-border;
  padding: 18px;
  border-radius: 14px;
  cursor: pointer;
  background: @dark-bg-card;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);

  &:hover {
    border-color: rgba(139, 92, 246, 0.4);
    box-shadow: 0 8px 32px rgba(139, 92, 246, 0.15);
    transform: translateY(-2px);
  }

  .name-icon {
    display: flex;
    align-items: center;
    margin-bottom: 14px;

    img {
      border-radius: 8px;
      background: rgba(139, 92, 246, 0.1);
      padding: 4px;
    }

    .info {
      margin-left: 14px;

      .name {
        font-weight: 600;
        font-size: 15px;
        line-height: 24px;
        max-width: 250px;
        color: @dark-text;
      }

      .type {
        font-weight: 400;
        font-size: 12px;
        line-height: 20px;
        color: @dark-text-muted;
      }
    }
  }

  .type-value {
    font-weight: 400;
    font-size: 13px;
    line-height: 1.6;
    color: @dark-text-secondary;
    height: 44px;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
    word-break: break-word;
    width: 100%;
  }

  .bottom-info {
    margin-top: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 28px;

    .ed-button {
      height: 28px;
      min-width: 78px;
    }

    .form-rate {
      display: flex;
      align-items: center;
      color: @dark-text-muted;
      font-weight: 400;
      font-size: 13px;
      line-height: 22px;

      .form-icon {
        margin-right: 8px;
        color: @primary-400;
      }
    }

    .methods {
      align-items: center;
      display: none;

      .more {
        position: relative;
        cursor: pointer;

        &::after {
          content: '';
          background-color: rgba(139, 92, 246, 0.15);
          position: absolute;
          border-radius: 6px;
          width: 24px;
          height: 24px;
          transform: translate(-50%, -50%);
          top: 50%;
          left: 50%;
          display: none;
        }

        &:hover {
          &::after {
            display: block;
          }
        }
      }
    }
  }

  &.is-selected {
    border: 2px solid @primary-500;
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.15) 0%, rgba(168, 85, 247, 0.1) 100%);
    box-shadow: 0 0 20px rgba(139, 92, 246, 0.2);

    .name-icon .info .name {
      color: #fff;
    }
  }
}
</style>
