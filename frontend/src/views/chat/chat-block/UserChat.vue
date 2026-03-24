<script setup lang="ts">
import type { ChatMessage } from '@/api/chat.ts'
import { ElMessage } from 'element-plus-secondary'
import { useI18n } from 'vue-i18n'
import { useClipboard } from '@vueuse/core'
import { ref } from 'vue'

const props = defineProps<{
  message?: ChatMessage
}>()
const { t } = useI18n()
const { copy } = useClipboard({ legacy: true })
const copied = ref(false)

function clickAnalysis() {
  // Reserved for future analysis feature
}
function clickPredict() {
  // Reserved for future predict feature
}

const copyCode = () => {
  const str = props.message?.content || ''
  copy(str as string)
    .then(function () {
      copied.value = true
      ElMessage.success({
        message: t('qa.copied'),
        duration: 1500,
        showClose: false,
      })
      setTimeout(() => {
        copied.value = false
      }, 2500)
    })
    .catch(function () {
      ElMessage.error({
        message: t('common.copy_failed'),
        duration: 2000,
      })
    })
}
</script>

<template>
  <div class="user-message-wrapper">
    <div class="user-message">
      <!-- 消息标签 -->
      <span
        v-if="message?.record?.analysis_record_id"
        class="message-tag analysis-tag"
        @click="clickAnalysis"
      >
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="2" y="2" width="12" height="12" rx="2" />
          <path d="M5 10V8M8 10V6M11 10V4" />
        </svg>
        {{ t('qa.data_analysis') }}
      </span>
      <span
        v-else-if="message?.record?.predict_record_id"
        class="message-tag predict-tag"
        @click="clickPredict"
      >
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M2 12l4-4 3 3 5-5" />
          <path d="M10 6h4v4" />
        </svg>
        {{ t('qa.data_predict') }}
      </span>

      <!-- 消息内容 -->
      <span class="message-content">{{ message?.content }}</span>
    </div>

    <!-- 复制按钮 -->
    <div class="message-actions">
      <el-tooltip
        :offset="8"
        effect="dark"
        :content="copied ? t('qa.copied') : t('datasource.copy')"
        placement="top"
      >
        <button class="action-btn" :class="{ copied: copied }" @click="copyCode">
          <svg
            v-if="!copied"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <rect x="9" y="9" width="13" height="13" rx="2" />
            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M20 6L9 17l-5-5" />
          </svg>
        </button>
      </el-tooltip>
    </div>
  </div>
</template>

<style scoped lang="less">
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@primary-700: #6d28d9;

.user-message-wrapper {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.user-message {
  display: inline-flex;
  flex-direction: column;
  gap: 10px;
  border-radius: 18px 18px 6px 18px;
  min-height: 42px;
  line-height: 1.65;
  font-size: 14px;
  padding: 14px 18px;
  color: #fff;
  background: linear-gradient(145deg, @primary-600 0%, @primary-500 50%, @primary-700 100%);
  position: relative;
  box-shadow:
    0 6px 24px rgba(124, 58, 237, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
  word-wrap: break-word;
  white-space: pre-wrap;
  max-width: 100%;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;

  // 顶部高光
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 50%;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.12) 0%, transparent 100%);
    pointer-events: none;
    border-radius: 18px 18px 0 0;
  }

  // 悬停效果
  &:hover {
    transform: translateY(-1px);
    box-shadow:
      0 8px 32px rgba(124, 58, 237, 0.4),
      inset 0 1px 0 rgba(255, 255, 255, 0.18);
  }

  .message-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: rgba(255, 255, 255, 0.98);
    white-space: nowrap;
    font-weight: 600;
    font-size: 11px;
    background: rgba(255, 255, 255, 0.2);
    padding: 5px 12px;
    border-radius: 6px;
    width: fit-content;
    cursor: pointer;
    transition: all 0.25s ease;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    backdrop-filter: blur(4px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    position: relative;
    z-index: 1;

    svg {
      width: 14px;
      height: 14px;
    }

    &:hover {
      background: rgba(255, 255, 255, 0.28);
      transform: translateY(-1px);
    }

    &.analysis-tag {
      background: rgba(34, 197, 94, 0.3);
      border-color: rgba(34, 197, 94, 0.2);

      &:hover {
        background: rgba(34, 197, 94, 0.4);
      }
    }

    &.predict-tag {
      background: rgba(59, 130, 246, 0.3);
      border-color: rgba(59, 130, 246, 0.2);

      &:hover {
        background: rgba(59, 130, 246, 0.4);
      }
    }
  }

  .message-content {
    width: 100%;
    position: relative;
    z-index: 1;
    font-weight: 400;
    letter-spacing: 0.2px;
  }
}

.message-actions {
  opacity: 0;
  transform: translateY(4px);
  transition: all 0.25s ease;

  .user-message-wrapper:hover & {
    opacity: 1;
    transform: translateY(0);
  }

  .action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border: 1px solid rgba(139, 92, 246, 0.15);
    background: rgba(139, 92, 246, 0.08);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.25s ease;

    svg {
      width: 16px;
      height: 16px;
      color: rgba(196, 181, 253, 0.85);
      transition: all 0.25s ease;
    }

    &:hover {
      background: rgba(139, 92, 246, 0.18);
      border-color: rgba(139, 92, 246, 0.3);
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(139, 92, 246, 0.15);

      svg {
        color: @primary-400;
      }
    }

    &:active {
      transform: translateY(0);
    }

    &.copied {
      background: rgba(34, 197, 94, 0.18);
      border-color: rgba(34, 197, 94, 0.3);

      svg {
        color: #4ade80;
      }
    }
  }
}

@media (max-width: 768px) {
  .user-message {
    padding: 12px 16px;
    font-size: 14px;
    border-radius: 16px 16px 5px 16px;

    .message-tag {
      font-size: 10px;
      padding: 4px 10px;

      svg {
        width: 12px;
        height: 12px;
      }
    }
  }

  .message-actions {
    opacity: 1;
    transform: translateY(0);

    .action-btn {
      width: 28px;
      height: 28px;
      border-radius: 6px;

      svg {
        width: 14px;
        height: 14px;
      }
    }
  }
}

@media (max-width: 480px) {
  .user-message {
    padding: 10px 14px;
    font-size: 13px;
    border-radius: 14px 14px 4px 14px;
  }

  .message-actions {
    .action-btn {
      width: 26px;
      height: 26px;
    }
  }
}
</style>
