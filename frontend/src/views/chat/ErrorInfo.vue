<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { detectErrorType, getErrorIcon, type ErrorType } from '@/utils/errorDetection'

const props = defineProps<{
  error?: string
}>()

const { t } = useI18n()

const isCompletePage = true

const showBlock = computed(() => {
  return props.error && props.error?.trim().length > 0
})

// 使用统一的错误类型检测
const detectedErrorType = computed<ErrorType>(() => {
  return detectErrorType(props.error)
})

// 解析 API 额度不足错误的详细信息
const quotaErrorInfo = computed(() => {
  if (detectedErrorType.value !== 'quota') return null

  const errorStr = props.error || ''
  const remainMatch =
    errorStr.match(/剩余额度[：:]\s*[¥￥]?([\d.]+)/i) ||
    errorStr.match(/余额[：:]\s*[¥￥]?([\d.]+)/i) ||
    errorStr.match(/balance[：:]\s*[¥￥$]?([\d.]+)/i)
  const needMatch =
    errorStr.match(/需要预扣费额度[：:]\s*[¥￥]?([\d.]+)/i) ||
    errorStr.match(/预扣费额度[：:]\s*[¥￥]?([\d.]+)/i) ||
    errorStr.match(/需要[：:]\s*[¥￥]?([\d.]+)/i)

  return {
    isQuotaError: true,
    remaining: remainMatch ? parseFloat(remainMatch[1]).toFixed(2) : null,
    needed: needMatch ? parseFloat(needMatch[1]).toFixed(2) : null,
  }
})

// 获取错误图标
const errorIcon = computed(() => {
  // 优先使用后端返回的错误类型
  const backendType = errorMessage.value.type
  if (backendType === 'db-connection-err') return '🔌'
  if (backendType === 'exec-sql-err') return '📝'
  // 使用统一的错误图标
  return getErrorIcon(detectedErrorType.value)
})

const errorMessage = computed(() => {
  const obj = {
    message: props.error,
    showMore: false,
    traceback: '',
    type: undefined as string | undefined,
    friendlyMessage: '' as string,
  }

  // 根据检测到的错误类型设置友好消息
  switch (detectedErrorType.value) {
    case 'quota':
      obj.traceback = props.error || ''
      obj.showMore = true
      obj.type = 'api-quota-err'
      return obj
    case 'timeout':
      obj.friendlyMessage = t('qa.error_suggestion_timeout')
      obj.traceback = props.error || ''
      obj.showMore = true
      obj.type = 'timeout-err'
      return obj
    case 'network':
      obj.friendlyMessage = t('qa.error_network')
      obj.traceback = props.error || ''
      obj.showMore = true
      obj.type = 'network-err'
      return obj
    case 'api':
      obj.friendlyMessage = t('qa.error_suggestion_model')
      obj.traceback = props.error || ''
      obj.showMore = true
      obj.type = 'api-err'
      return obj
    case 'db':
      obj.friendlyMessage = t('chat.ds_is_invalid')
      obj.traceback = props.error || ''
      obj.showMore = true
      obj.type = 'db-connection-err'
      return obj
    case 'sql':
      obj.friendlyMessage = t('chat.exec-sql-err')
      obj.traceback = props.error || ''
      obj.showMore = true
      obj.type = 'exec-sql-err'
      return obj
    case 'parse':
      obj.friendlyMessage = t('qa.error_parse')
      obj.traceback = props.error || ''
      obj.showMore = true
      obj.type = 'parse-err'
      return obj
    case 'datasource':
      obj.friendlyMessage = t('qa.error_datasource')
      obj.traceback = props.error || ''
      obj.showMore = true
      obj.type = 'datasource-err'
      return obj
    case 'model':
      obj.friendlyMessage = t('qa.error_model')
      obj.traceback = props.error || ''
      obj.showMore = true
      obj.type = 'model-err'
      return obj
  }

  // 尝试解析 JSON 格式的错误
  if (showBlock.value && props.error?.trim().startsWith('{') && props.error?.trim().endsWith('}')) {
    try {
      const json = JSON.parse(props.error?.trim())
      obj.message = json['message']
      obj.traceback = json['traceback']
      obj.type = json['type']
      if (obj.traceback?.trim().length > 0) obj.showMore = true
    } catch (e) {}
  }

  // 检查是否包含 Traceback
  if (!obj.showMore && props.error?.includes('Traceback')) {
    obj.traceback = props.error
    obj.showMore = true
    obj.friendlyMessage = t('chat.error')
  }

  // 如果没有友好消息，设置默认消息
  if (!obj.friendlyMessage && !obj.message) {
    obj.friendlyMessage = t('qa.error_unknown')
  }

  return obj
})

const errorSuggestion = computed(() => {
  const errorType = errorMessage.value.type

  if (errorType === 'api-quota-err') return ''
  if (errorType === 'api-err') return t('qa.error_suggestion_model')
  if (errorType === 'timeout-err') return t('qa.error_suggestion_timeout')
  if (errorType === 'network-err') return t('qa.error_suggestion_network')
  if (errorType === 'db-connection-err') return t('qa.error_suggestion_db')
  if (errorType === 'exec-sql-err') return t('qa.error_suggestion_sql')
  if (errorType === 'parse-err') return t('qa.error_suggestion_parse')
  if (errorType === 'datasource-err') return t('qa.error_suggestion_datasource')
  if (errorType === 'model-err') return t('qa.error_suggestion_model')

  // 默认建议
  return t('qa.error_suggestion_default')
})

const show = ref(false)

// 格式化 traceback，确保正确显示
const formatTraceback = (traceback: string | undefined): string => {
  if (!traceback) return ''

  let result = traceback

  // 如果是 JSON 格式，尝试解析并格式化
  if (result.trim().startsWith('{') && result.trim().endsWith('}')) {
    try {
      const json = JSON.parse(result)
      // 如果有 traceback 字段，使用它
      if (json.traceback) {
        result = json.traceback
      } else if (json.message) {
        result = json.message
      } else {
        // 格式化整个 JSON
        result = JSON.stringify(json, null, 2)
      }
    } catch (e) {
      // 解析失败，保持原样
    }
  }

  // 移除 HTML 标签，防止乱码
  result = result.replace(/<[^>]*>/g, '')

  // 使用 DOMParser 安全解码 HTML 实体，替代 textarea.innerHTML
  // textarea.innerHTML 在接收未充分过滤的错误消息时存在 XSS 风险
  try {
    const doc = new DOMParser().parseFromString(result, 'text/html')
    result = doc.body.textContent || result
  } catch {
    // DOMParser 失败时保持原样
  }

  // 处理转义字符
  result = result
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '  ')
    .replace(/\\r/g, '')
    .replace(/\\\\/g, '\\')
    .replace(/\\"/g, '"')

  return result.trim()
}
</script>

<template>
  <div v-if="showBlock" class="error-info-container">
    <!-- API 额度不足 -->
    <div v-if="quotaErrorInfo" class="quota-card">
      <div class="quota-header">
        <span class="quota-icon">⚠️</span>
        <span class="quota-title">{{ t('qa.api_quota_title') }}</span>
      </div>
      <div class="quota-message">{{ t('qa.quota_message') }}</div>
      <div class="quota-tip">💬 {{ t('qa.quota_tip') }}</div>
    </div>

    <!-- 友好提示（数据源范围外的查询） -->
    <div v-else-if="errorMessage.type === 'friendly-hint'" class="friendly-hint-block">
      <div class="hint-body">
        <div class="hint-header">
          <span class="hint-icon">💡</span>
          <div class="hint-message">{{ errorMessage.message || errorMessage.friendlyMessage }}</div>
        </div>
      </div>
    </div>

    <!-- 其他错误 -->
    <div v-else class="error-block" :class="errorMessage.type">
      <div class="error-body">
        <div class="error-header">
          <span class="error-icon">{{ errorIcon }}</span>
          <div v-if="errorMessage.friendlyMessage" class="error-message">
            {{ errorMessage.friendlyMessage }}
          </div>
          <div
            v-else-if="!errorMessage.showMore && !errorMessage.type"
            v-dompurify-html="errorMessage.message"
            class="error-message"
          ></div>
          <div v-else class="error-message">
            <template v-if="errorMessage.type === 'db-connection-err'">{{
              t('chat.ds_is_invalid')
            }}</template>
            <template v-else-if="errorMessage.type === 'exec-sql-err'">{{
              t('chat.exec-sql-err')
            }}</template>
            <template v-else>{{ t('chat.error') }}</template>
          </div>
        </div>
        <button v-if="errorMessage.showMore" class="detail-btn" @click="show = true">
          {{ t('chat.show_error_detail') }}
        </button>
      </div>
      <div v-if="errorSuggestion" class="error-suggestion">💬 {{ errorSuggestion }}</div>
    </div>

    <el-drawer
      v-model="show"
      :size="!isCompletePage ? '100%' : '600px'"
      :title="t('chat.error')"
      direction="rtl"
      body-class="chart-sql-error-body"
    >
      <el-main>
        <div class="error-traceback">{{ formatTraceback(errorMessage.traceback) }}</div>
      </el-main>
    </el-drawer>
  </div>
</template>

<style lang="less">
.chart-sql-error-body {
  padding: 0;
  background: #1a1225;
}
</style>

<style scoped lang="less">
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);
@error-color: #f87171;
@warning-color: #fbbf24;
@primary-400: #a78bfa;
@hint-color: #60a5fa;

.error-info-container {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.friendly-hint-block {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  background: linear-gradient(145deg, rgba(96, 165, 250, 0.10) 0%, rgba(59, 130, 246, 0.06) 100%);
  border: 1.5px solid rgba(96, 165, 250, 0.25);
  border-radius: 14px;
  padding: 16px 18px;
  animation: fadeIn 0.35s cubic-bezier(0.4, 0, 0.2, 1);

  .hint-body {
    .hint-header {
      display: flex;
      align-items: flex-start;
      gap: 10px;

      .hint-icon {
        font-size: 18px;
        flex-shrink: 0;
        margin-top: 1px;
      }

      .hint-message {
        color: @dark-text-secondary;
        font-size: 13.5px;
        line-height: 1.6;
        word-break: break-word;
      }
    }
  }
}

.quota-card {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  background: linear-gradient(145deg, rgba(251, 191, 36, 0.14) 0%, rgba(245, 158, 11, 0.08) 100%);
  border: 1.5px solid rgba(251, 191, 36, 0.28);
  border-radius: 14px;
  padding: 18px;
  animation: fadeIn 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(251, 191, 36, 0.1);

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
      rgba(251, 191, 36, 0.4) 50%,
      transparent 100%
    );
  }

  .quota-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;

    .quota-icon {
      font-size: 20px;
      filter: drop-shadow(0 2px 4px rgba(251, 191, 36, 0.3));
      animation: pulse 2s ease-in-out infinite;
    }

    .quota-title {
      font-size: 15px;
      font-weight: 700;
      color: rgba(253, 224, 71, 0.98);
      letter-spacing: 0.3px;
    }
  }

  .quota-message {
    font-size: 13px;
    color: @dark-text-secondary;
    line-height: 1.65;
    margin-bottom: 16px;
    word-wrap: break-word;
    overflow-wrap: break-word;
  }
  .quota-tip {
    padding: 14px 18px;
    background: linear-gradient(145deg, rgba(251, 191, 36, 0.12) 0%, rgba(245, 158, 11, 0.08) 100%);
    border-radius: 10px;
    font-size: 13px;
    color: @dark-text-secondary;
    line-height: 1.55;
    word-wrap: break-word;
    overflow-wrap: break-word;
    border: 1px solid rgba(251, 191, 36, 0.15);
  }
}

.error-block {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  background: linear-gradient(145deg, rgba(248, 113, 113, 0.1) 0%, rgba(239, 68, 68, 0.06) 100%);
  border: 1.5px solid rgba(248, 113, 113, 0.22);
  border-radius: 14px;
  padding: 16px 18px;
  animation: fadeIn 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(248, 113, 113, 0.08);

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
      rgba(248, 113, 113, 0.35) 50%,
      transparent 100%
    );
  }

  .error-body {
    .error-header {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 14px;

      .error-icon {
        font-size: 18px;
        flex-shrink: 0;
        line-height: 1.5;
        filter: drop-shadow(0 2px 4px rgba(248, 113, 113, 0.3));
      }
    }

    .error-message {
      font-size: 14px;
      line-height: 1.65;
      color: rgba(255, 200, 200, 0.92);
      white-space: pre-wrap;
      word-wrap: break-word;
      overflow-wrap: break-word;
      flex: 1;
      font-weight: 500;
    }
    .detail-btn {
      padding: 10px 16px;
      background: linear-gradient(
        145deg,
        rgba(248, 113, 113, 0.12) 0%,
        rgba(239, 68, 68, 0.08) 100%
      );
      border: 1px solid rgba(248, 113, 113, 0.22);
      border-radius: 10px;
      color: @error-color;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      &:hover {
        background: linear-gradient(
          145deg,
          rgba(248, 113, 113, 0.18) 0%,
          rgba(239, 68, 68, 0.12) 100%
        );
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(248, 113, 113, 0.15);
      }
      &:active {
        transform: translateY(0);
      }
    }
  }
  .error-suggestion {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid rgba(248, 113, 113, 0.18);
    font-size: 13px;
    color: @dark-text-secondary;
    line-height: 1.55;
    word-wrap: break-word;
    overflow-wrap: break-word;
  }

  // 超时错误 - 蓝色
  &.timeout-err {
    background: linear-gradient(145deg, rgba(59, 130, 246, 0.12) 0%, rgba(37, 99, 235, 0.08) 100%);
    border-color: rgba(59, 130, 246, 0.28);
    box-shadow: 0 4px 20px rgba(59, 130, 246, 0.08);

    &::before {
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(59, 130, 246, 0.35) 50%,
        transparent 100%
      );
    }

    .error-body {
      .error-icon {
        filter: drop-shadow(0 2px 4px rgba(59, 130, 246, 0.3));
      }
      .error-message {
        color: rgba(147, 197, 253, 0.92);
      }
      .detail-btn {
        background: linear-gradient(
          145deg,
          rgba(59, 130, 246, 0.12) 0%,
          rgba(37, 99, 235, 0.08) 100%
        );
        border-color: rgba(59, 130, 246, 0.22);
        color: rgba(147, 197, 253, 0.95);
        &:hover {
          background: linear-gradient(
            145deg,
            rgba(59, 130, 246, 0.2) 0%,
            rgba(37, 99, 235, 0.14) 100%
          );
          box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
        }
      }
    }
    .error-suggestion {
      border-color: rgba(59, 130, 246, 0.18);
    }
  }

  // 网络错误 - 橙色
  &.network-err {
    background: linear-gradient(145deg, rgba(249, 115, 22, 0.12) 0%, rgba(234, 88, 12, 0.08) 100%);
    border-color: rgba(249, 115, 22, 0.28);
    box-shadow: 0 4px 20px rgba(249, 115, 22, 0.08);

    &::before {
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(249, 115, 22, 0.35) 50%,
        transparent 100%
      );
    }

    .error-body {
      .error-icon {
        filter: drop-shadow(0 2px 4px rgba(249, 115, 22, 0.3));
      }
      .error-message {
        color: rgba(253, 186, 116, 0.92);
      }
      .detail-btn {
        background: linear-gradient(
          145deg,
          rgba(249, 115, 22, 0.12) 0%,
          rgba(234, 88, 12, 0.08) 100%
        );
        border-color: rgba(249, 115, 22, 0.22);
        color: rgba(253, 186, 116, 0.95);
        &:hover {
          background: linear-gradient(
            145deg,
            rgba(249, 115, 22, 0.2) 0%,
            rgba(234, 88, 12, 0.14) 100%
          );
          box-shadow: 0 4px 12px rgba(249, 115, 22, 0.15);
        }
      }
    }
    .error-suggestion {
      border-color: rgba(249, 115, 22, 0.18);
    }
  }

  // API 错误 - 紫色
  &.api-err {
    background: linear-gradient(145deg, rgba(139, 92, 246, 0.12) 0%, rgba(124, 58, 237, 0.08) 100%);
    border-color: rgba(139, 92, 246, 0.28);
    box-shadow: 0 4px 20px rgba(139, 92, 246, 0.08);

    &::before {
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(139, 92, 246, 0.35) 50%,
        transparent 100%
      );
    }

    .error-body {
      .error-icon {
        filter: drop-shadow(0 2px 4px rgba(139, 92, 246, 0.3));
      }
      .error-message {
        color: rgba(196, 181, 253, 0.92);
      }
      .detail-btn {
        background: linear-gradient(
          145deg,
          rgba(139, 92, 246, 0.12) 0%,
          rgba(124, 58, 237, 0.08) 100%
        );
        border-color: rgba(139, 92, 246, 0.22);
        color: rgba(196, 181, 253, 0.95);
        &:hover {
          background: linear-gradient(
            145deg,
            rgba(139, 92, 246, 0.2) 0%,
            rgba(124, 58, 237, 0.14) 100%
          );
          box-shadow: 0 4px 12px rgba(139, 92, 246, 0.15);
        }
      }
    }
    .error-suggestion {
      border-color: rgba(139, 92, 246, 0.18);
    }
  }

  // 数据库连接错误 - 青色
  &.db-connection-err {
    background: linear-gradient(145deg, rgba(6, 182, 212, 0.12) 0%, rgba(8, 145, 178, 0.08) 100%);
    border-color: rgba(6, 182, 212, 0.28);
    box-shadow: 0 4px 20px rgba(6, 182, 212, 0.08);

    &::before {
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(6, 182, 212, 0.35) 50%,
        transparent 100%
      );
    }

    .error-body {
      .error-icon {
        filter: drop-shadow(0 2px 4px rgba(6, 182, 212, 0.3));
      }
      .error-message {
        color: rgba(103, 232, 249, 0.92);
      }
      .detail-btn {
        background: linear-gradient(
          145deg,
          rgba(6, 182, 212, 0.12) 0%,
          rgba(8, 145, 178, 0.08) 100%
        );
        border-color: rgba(6, 182, 212, 0.22);
        color: rgba(103, 232, 249, 0.95);
        &:hover {
          background: linear-gradient(
            145deg,
            rgba(6, 182, 212, 0.2) 0%,
            rgba(8, 145, 178, 0.14) 100%
          );
          box-shadow: 0 4px 12px rgba(6, 182, 212, 0.15);
        }
      }
    }
    .error-suggestion {
      border-color: rgba(6, 182, 212, 0.18);
    }
  }

  // SQL 执行错误 - 琥珀色
  &.exec-sql-err {
    background: linear-gradient(145deg, rgba(245, 158, 11, 0.12) 0%, rgba(217, 119, 6, 0.08) 100%);
    border-color: rgba(245, 158, 11, 0.28);
    box-shadow: 0 4px 20px rgba(245, 158, 11, 0.08);

    &::before {
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(245, 158, 11, 0.35) 50%,
        transparent 100%
      );
    }

    .error-body {
      .error-icon {
        filter: drop-shadow(0 2px 4px rgba(245, 158, 11, 0.3));
      }
      .error-message {
        color: rgba(252, 211, 77, 0.92);
      }
      .detail-btn {
        background: linear-gradient(
          145deg,
          rgba(245, 158, 11, 0.12) 0%,
          rgba(217, 119, 6, 0.08) 100%
        );
        border-color: rgba(245, 158, 11, 0.22);
        color: rgba(252, 211, 77, 0.95);
        &:hover {
          background: linear-gradient(
            145deg,
            rgba(245, 158, 11, 0.2) 0%,
            rgba(217, 119, 6, 0.14) 100%
          );
          box-shadow: 0 4px 12px rgba(245, 158, 11, 0.15);
        }
      }
    }
    .error-suggestion {
      border-color: rgba(245, 158, 11, 0.18);
    }
  }

  // 解析错误 - 粉色
  &.parse-err {
    background: linear-gradient(145deg, rgba(236, 72, 153, 0.12) 0%, rgba(219, 39, 119, 0.08) 100%);
    border-color: rgba(236, 72, 153, 0.28);
    box-shadow: 0 4px 20px rgba(236, 72, 153, 0.08);

    &::before {
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(236, 72, 153, 0.35) 50%,
        transparent 100%
      );
    }

    .error-body {
      .error-icon {
        filter: drop-shadow(0 2px 4px rgba(236, 72, 153, 0.3));
      }
      .error-message {
        color: rgba(249, 168, 212, 0.92);
      }
      .detail-btn {
        background: linear-gradient(
          145deg,
          rgba(236, 72, 153, 0.12) 0%,
          rgba(219, 39, 119, 0.08) 100%
        );
        border-color: rgba(236, 72, 153, 0.22);
        color: rgba(249, 168, 212, 0.95);
        &:hover {
          background: linear-gradient(
            145deg,
            rgba(236, 72, 153, 0.2) 0%,
            rgba(219, 39, 119, 0.14) 100%
          );
          box-shadow: 0 4px 12px rgba(236, 72, 153, 0.15);
        }
      }
    }
    .error-suggestion {
      border-color: rgba(236, 72, 153, 0.18);
    }
  }

  // 数据源错误 - 靛蓝色
  &.datasource-err {
    background: linear-gradient(145deg, rgba(99, 102, 241, 0.12) 0%, rgba(79, 70, 229, 0.08) 100%);
    border-color: rgba(99, 102, 241, 0.28);
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.08);

    &::before {
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(99, 102, 241, 0.35) 50%,
        transparent 100%
      );
    }

    .error-body {
      .error-icon {
        filter: drop-shadow(0 2px 4px rgba(99, 102, 241, 0.3));
      }
      .error-message {
        color: rgba(165, 180, 252, 0.92);
      }
      .detail-btn {
        background: linear-gradient(
          145deg,
          rgba(99, 102, 241, 0.12) 0%,
          rgba(79, 70, 229, 0.08) 100%
        );
        border-color: rgba(99, 102, 241, 0.22);
        color: rgba(165, 180, 252, 0.95);
        &:hover {
          background: linear-gradient(
            145deg,
            rgba(99, 102, 241, 0.2) 0%,
            rgba(79, 70, 229, 0.14) 100%
          );
          box-shadow: 0 4px 12px rgba(99, 102, 241, 0.15);
        }
      }
    }
    .error-suggestion {
      border-color: rgba(99, 102, 241, 0.18);
    }
  }

  // 模型错误 - 紫罗兰色
  &.model-err {
    background: linear-gradient(
      145deg,
      rgba(167, 139, 250, 0.12) 0%,
      rgba(139, 92, 246, 0.08) 100%
    );
    border-color: rgba(167, 139, 250, 0.28);
    box-shadow: 0 4px 20px rgba(167, 139, 250, 0.08);

    &::before {
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(167, 139, 250, 0.35) 50%,
        transparent 100%
      );
    }

    .error-body {
      .error-icon {
        filter: drop-shadow(0 2px 4px rgba(167, 139, 250, 0.3));
      }
      .error-message {
        color: rgba(196, 181, 253, 0.92);
      }
      .detail-btn {
        background: linear-gradient(
          145deg,
          rgba(167, 139, 250, 0.12) 0%,
          rgba(139, 92, 246, 0.08) 100%
        );
        border-color: rgba(167, 139, 250, 0.22);
        color: rgba(196, 181, 253, 0.95);
        &:hover {
          background: linear-gradient(
            145deg,
            rgba(167, 139, 250, 0.2) 0%,
            rgba(139, 92, 246, 0.14) 100%
          );
          box-shadow: 0 4px 12px rgba(167, 139, 250, 0.15);
        }
      }
    }
    .error-suggestion {
      border-color: rgba(167, 139, 250, 0.18);
    }
  }
}

.error-traceback {
  font-size: 13px;
  background: linear-gradient(145deg, rgba(26, 18, 37, 0.95) 0%, rgba(20, 14, 32, 0.95) 100%);
  padding: 18px;
  border-radius: 12px;
  color: rgba(255, 200, 200, 0.88);
  white-space: pre-wrap;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  word-wrap: break-word;
  overflow-wrap: break-word;
  overflow-x: auto;
  border: 1px solid rgba(248, 113, 113, 0.15);
  line-height: 1.6;
}

@media (max-width: 768px) {
  .quota-card {
    padding: 14px;
    border-radius: 12px;
    .quota-header {
      .quota-icon {
        font-size: 16px;
      }
      .quota-title {
        font-size: 13px;
      }
    }
    .quota-message {
      font-size: 12px;
      margin-bottom: 12px;
    }
    .quota-detail {
      padding: 12px 14px;
      .detail-item {
        padding: 6px 0;
        .detail-label {
          font-size: 12px;
        }
        .detail-value {
          font-size: 15px;
        }
      }
    }
    .quota-tip {
      font-size: 12px;
      padding: 10px 14px;
    }
  }
  .error-block {
    padding: 12px 14px;
    border-radius: 12px;
    .error-body {
      .error-header {
        .error-icon {
          font-size: 15px;
        }
      }
      .error-message {
        font-size: 13px;
      }
      .detail-btn {
        padding: 6px 12px;
        font-size: 12px;
      }
    }
    .error-suggestion {
      font-size: 12px;
      margin-top: 12px;
      padding-top: 12px;
    }
  }
}

@media (max-width: 480px) {
  .quota-card {
    padding: 12px;
    border-radius: 10px;
    .quota-header {
      margin-bottom: 8px;
      .quota-icon {
        font-size: 15px;
      }
      .quota-title {
        font-size: 12px;
      }
    }
    .quota-message {
      font-size: 11px;
      margin-bottom: 10px;
    }
    .quota-detail {
      padding: 10px 12px;
      border-radius: 10px;
      .detail-item {
        .detail-label {
          font-size: 11px;
        }
        .detail-value {
          font-size: 14px;
        }
      }
    }
    .quota-tip {
      font-size: 11px;
      padding: 8px 12px;
      border-radius: 8px;
    }
  }
  .error-block {
    padding: 10px 12px;
    border-radius: 10px;
    .error-body {
      .error-header {
        gap: 8px;
        .error-icon {
          font-size: 14px;
        }
      }
      .error-message {
        font-size: 12px;
      }
      .detail-btn {
        padding: 5px 10px;
        font-size: 11px;
        border-radius: 8px;
      }
    }
    .error-suggestion {
      font-size: 11px;
      margin-top: 10px;
      padding-top: 10px;
    }
  }
}
</style>
