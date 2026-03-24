<script lang="ts" setup>
import icon_done_outlined from '@/assets/svg/icon_done_outlined.svg'
import { computed, ref } from 'vue'
import icon_expand_down_filled from '@/assets/svg/icon_down_outlined.svg'
const props = defineProps({
  chartTypeList: {
    type: Array<any>,
    default: () => [],
  },
  chartType: {
    type: String,
    default: 'table',
  },
  title: {
    type: String,
    default: '',
  },
})
const currentIcon = computed(() => {
  if (props.chartType === 'table') {
    const [ele] = props.chartTypeList || []
    // chartTypeList 为空时 ele 为 undefined，访问 .icon 会 TypeError
    if (ele && ele.icon) {
      return ele.icon
    }
    return null
  }
  // find() 可能返回 undefined（chartType 不在列表中），需要安全访问
  const found = props.chartTypeList.find((ele) => ele.value === props.chartType)
  return found ? found.icon : null
})

const firstItem = () => {
  if (props.chartType === 'table') {
    const [ele] = props.chartTypeList || []
    handleDefaultChatChange(ele || {})
  }
}
const emits = defineEmits(['typeChange'])
const selectRef = ref()
const handleDefaultChatChange = (val: any) => {
  emits('typeChange', val.value)
  selectRef.value?.hide()
}
</script>

<template>
  <el-popover ref="selectRef" trigger="click" popper-class="chat-type_select" placement="bottom">
    <template #reference>
      <div
        class="chat-select_type"
        :class="chartType && chartType !== 'table' && 'active'"
        @click="firstItem"
      >
        <component :is="currentIcon" />
        <el-icon style="color: #646a73" class="expand" size="12">
          <icon_expand_down_filled></icon_expand_down_filled>
        </el-icon>
      </div>
    </template>
    <div class="popover">
      <div class="popover-content">
        <div v-if="!!title" class="title">{{ title }}</div>
        <div
          v-for="ele in chartTypeList"
          :key="ele.name"
          class="popover-item"
          :class="chartType === ele.value && 'isActive'"
          @click="handleDefaultChatChange(ele)"
        >
          <el-icon style="color: #646a73" size="16">
            <component :is="ele.icon" :class="chartType === ele.value && 'icon-primary'" />
          </el-icon>
          <div class="model-name">{{ ele.name }}</div>
          <el-icon size="16" class="done">
            <icon_done_outlined></icon_done_outlined>
          </el-icon>
        </div>
      </div>
    </div>
  </el-popover>
</template>

<style lang="less">
// 深色主题变量
@dark-bg-card: rgba(26, 18, 37, 0.98);
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.7);
@primary-400: #a78bfa;
@primary-500: #8b5cf6;

.chat-type_select.chat-type_select {
  padding: 8px 0;
  width: 150px !important;
  min-width: 150px !important;
  background: linear-gradient(165deg, @dark-bg-card 0%, rgba(18, 14, 28, 0.99) 100%) !important;
  border: 1px solid rgba(139, 92, 246, 0.25) !important;
  border-radius: 14px !important;
  box-shadow:
    0 12px 40px rgba(0, 0, 0, 0.5),
    0 0 0 1px rgba(139, 92, 246, 0.08) inset !important;
  backdrop-filter: blur(20px);
  position: relative;
  overflow: hidden;

  // 顶部高光
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(
      90deg,
      transparent 0%,
      rgba(139, 92, 246, 0.35) 50%,
      transparent 100%
    );
    pointer-events: none;
    z-index: 1;
  }

  .popover {
    .popover-content {
      padding: 0 8px;
      max-height: 300px;
      overflow-y: auto;

      .title {
        width: 100%;
        height: 32px;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        padding-left: 12px;
        color: @dark-text-muted;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
      }
    }
    .popover-item {
      height: 40px;
      display: flex;
      align-items: center;
      padding-left: 14px;
      padding-right: 12px;
      margin-bottom: 4px;
      position: relative;
      border-radius: 10px;
      cursor: pointer;
      color: @dark-text-secondary;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);

      &:last-child {
        margin-bottom: 0;
      }
      &:hover {
        background: linear-gradient(
          135deg,
          rgba(139, 92, 246, 0.18) 0%,
          rgba(168, 85, 247, 0.12) 100%
        );
        color: @dark-text;
        transform: translateX(2px);
      }

      .model-name {
        margin-left: 12px;
        font-weight: 500;
        font-size: 13px;
        line-height: 22px;
        max-width: 220px;
      }

      .done {
        margin-left: auto;
        display: none;
        color: @primary-400;
        filter: drop-shadow(0 0 4px rgba(167, 139, 250, 0.5));
      }

      &.isActive {
        color: @primary-400;
        background: rgba(139, 92, 246, 0.12);

        .done {
          display: block;
        }

        .icon-primary {
          color: @primary-400;
        }
      }
    }
  }
}
</style>

<style lang="less" scoped>
// 深色主题变量
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@primary-400: #a78bfa;

.chat-select_type {
  width: 40px;
  height: 24px;
  border-radius: 6px;
  padding-left: 4px;
  display: flex;
  align-items: center;
  cursor: pointer;
  color: @dark-text-secondary;
  transition: all 0.2s ease;

  .expand {
    margin-left: 4px;
    color: @dark-text-secondary !important;
  }

  &:hover {
    background: rgba(139, 92, 246, 0.15);
    color: @primary-400;

    .expand {
      color: @primary-400 !important;
    }
  }

  &.active {
    background: rgba(139, 92, 246, 0.2);
    color: @primary-400;

    .expand {
      color: @primary-400 !important;
    }
  }
}
</style>
