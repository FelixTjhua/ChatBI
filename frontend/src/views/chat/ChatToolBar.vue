<script setup lang="ts">
import { computed } from 'vue'
import { datetimeFormat } from '@/utils/utils.ts'
import type { ChatMessage } from '@/api/chat.ts'
import { useI18n } from 'vue-i18n'
import icon_delete from '@/assets/svg/icon_delete.svg'

const props = defineProps<{
  message: ChatMessage
}>()

const emits = defineEmits(['delete'])

const { t } = useI18n()

// 计算简短相对时间
const relativeTime = computed(() => {
  const createTime = props.message?.record?.create_time
  if (!createTime) return ''

  const now = new Date()
  const time = new Date(createTime)
  const diff = now.getTime() - time.getTime()

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  // 简短格式
  if (minutes < 1) return t('qa.just_now_short')
  if (minutes < 60) return `${minutes}${t('qa.min_short')}`
  if (hours < 24) return `${hours}${t('qa.hour_short')}`
  if (days < 7) return `${days}${t('qa.day_short')}`

  // 超过7天显示简短日期 MM-DD
  const month = String(time.getMonth() + 1).padStart(2, '0')
  const day = String(time.getDate()).padStart(2, '0')
  return `${month}-${day}`
})

// 完整时间用于tooltip
const fullTime = computed(() => {
  return datetimeFormat(props.message?.record?.create_time)
})

// 删除消息
const handleDelete = () => {
  emits('delete', props.message)
}

</script>

<template>
  <div class="tool-container">
    <div class="tool-left">
      <slot></slot>
    </div>
    <div class="tool-right">
      <el-tooltip effect="dark" :content="fullTime" placement="top" :show-after="300">
        <template #default>
          <div class="tool-time">
            <svg
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              class="time-icon"
            >
              <circle cx="8" cy="8" r="6.5" />
              <path d="M8 4.5v4l2.5 1.5" />
            </svg>
            <span class="time-text">{{ relativeTime }}</span>
          </div>
        </template>
      </el-tooltip>
      
      <!-- 删除按钮 -->
      <el-tooltip :content="t('dashboard.delete')" placement="top" :show-after="500">
        <template #default>
          <div class="delete-btn" @click="handleDelete">
            <el-icon :size="16">
              <icon_delete />
            </el-icon>
          </div>
        </template>
      </el-tooltip>
    </div>
  </div>
</template>

<style scoped lang="less">
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.7);
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@dark-border: rgba(139, 92, 246, 0.2);

.tool-container {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid @dark-border;
  position: relative;

  // 顶部渐变线
  &::before {
    content: '';
    position: absolute;
    top: -1px;
    left: 0;
    width: 60px;
    height: 1px;
    background: linear-gradient(90deg, @primary-400 0%, transparent 100%);
  }
}

.tool-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  position: relative;
  z-index: 5;
  pointer-events: auto;
}

.tool-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  overflow: hidden;

  // 工具按钮样式 - 更紧凑
  :deep(.el-button.tool-btn),
  :deep(.ed-button.tool-btn) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 32px;
    padding: 0 12px;
    margin: 0;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 500;
    color: @dark-text-secondary;
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid rgba(139, 92, 246, 0.15);
    white-space: nowrap;
    flex-shrink: 0;
    transition: all 0.2s ease;

    &:hover {
      background: rgba(139, 92, 246, 0.15);
      border-color: rgba(139, 92, 246, 0.3);
      color: @primary-400;
    }

    &:active {
      transform: scale(0.97);
    }

    .tool-btn-inner {
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }

    .btn-text {
      font-size: 12px;
    }
  }

  :deep(.divider) {
    width: 1px;
    height: 16px;
    background: @dark-border;
    flex-shrink: 0;
  }
}

.tool-time {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: @dark-text-muted;
  white-space: nowrap;
  padding: 5px 10px;
  border-radius: 6px;
  cursor: default;
  flex-shrink: 0;
  transition: all 0.2s ease;
  background: rgba(139, 92, 246, 0.04);

  .time-icon {
    width: 12px;
    height: 12px;
    opacity: 0.5;
    flex-shrink: 0;
  }

  .time-text {
    font-variant-numeric: tabular-nums;
    font-weight: 500;
  }

  &:hover {
    background: rgba(139, 92, 246, 0.1);
    color: @dark-text-secondary;

    .time-icon {
      opacity: 0.8;
    }
  }
}

// 删除按钮
.delete-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: rgba(139, 92, 246, 0.04);
  opacity: 0.7;
  flex-shrink: 0;
  pointer-events: auto;
  position: relative;
  z-index: 10;

  .el-icon,
  .ed-icon {
    color: rgba(248, 113, 113, 0.8);
    transition: all 0.2s ease;
    pointer-events: none;
  }

  &:hover {
    background: rgba(239, 68, 68, 0.15);
    opacity: 1;

    .el-icon,
    .ed-icon {
      color: rgb(248, 113, 113);
    }
  }

  &:active {
    transform: scale(0.95);
  }
}

// 响应式 - 平板
@media (max-width: 768px) {
  .tool-container {
    margin-top: 12px;
    padding-top: 12px;
    gap: 10px;
  }

  .tool-left {
    gap: 6px;

    :deep(.el-button.tool-btn),
    :deep(.ed-button.tool-btn) {
      height: 30px;
      padding: 0 10px;
      font-size: 11px;
      border-radius: 7px;

      .tool-btn-inner {
        gap: 4px;
      }

      .btn-text {
        font-size: 11px;
      }
    }

    :deep(.divider) {
      height: 14px;
    }
  }

  .tool-time {
    font-size: 10px;
    padding: 4px 8px;
    gap: 4px;

    .time-icon {
      width: 11px;
      height: 11px;
    }
  }

  .delete-btn {
    width: 26px;
    height: 26px;
  }
}

// 响应式 - 手机
@media (max-width: 480px) {
  .tool-container {
    margin-top: 10px;
    padding-top: 10px;
    gap: 8px;
  }

  .tool-left {
    gap: 5px;

    :deep(.el-button.tool-btn),
    :deep(.ed-button.tool-btn) {
      height: 28px;
      padding: 0 8px;
      border-radius: 6px;

      .el-icon,
      .ed-icon {
        font-size: 14px !important;
      }

      // 小屏幕隐藏文字，只显示图标
      .btn-text {
        display: none;
      }
    }

    :deep(.divider) {
      height: 12px;
    }
  }

  .tool-time {
    font-size: 10px;
    padding: 3px 6px;
    border-radius: 5px;

    .time-icon {
      width: 10px;
      height: 10px;
    }
  }

  .delete-btn {
    width: 26px;
    height: 26px;
    border-radius: 5px;
  }
}
</style>

