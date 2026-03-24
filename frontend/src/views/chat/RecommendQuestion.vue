<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { endsWith, startsWith } from 'lodash-es'
import { useI18n } from 'vue-i18n'
import { chatApi, ChatInfo } from '@/api/chat.ts'
import { detectErrorType, type ErrorType } from '@/utils/errorDetection'
import icon_search_fancy from '@/assets/svg/icon_search_fancy.svg'
import icon_refresh_outlined from '@/assets/svg/icon_refresh_outlined.svg'

const props = withDefaults(
  defineProps<{
    recordId?: number
    currentChat?: ChatInfo
    questions?: string
    firstChat?: boolean
    disabled?: boolean
  }>(),
  {
    recordId: undefined,
    currentChat: () => new ChatInfo(),
    questions: '[]',
    firstChat: false,
    disabled: false,
  }
)

const emits = defineEmits(['clickQuestion', 'update:currentChat', 'stop', 'loadingOver'])

const loading = ref(false)
const hasTriedLoading = ref(false)
const stoppedByUser = ref(false)

// 错误状态管理 - 使用统一的错误类型
const errorType = ref<ErrorType>(null)
const errorMessage = ref('')

// 动画状态
const questionsVisible = ref(false)

// 记录上次错误时间，用于判断是否需要自动重试
const lastErrorTime = ref<number>(0)
// 自动重试的最小间隔（毫秒）- 防止频繁重试
// quota 错误使用更长间隔（30秒），避免持续消耗配额
const AUTO_RETRY_MIN_INTERVAL = 5000
const AUTO_RETRY_QUOTA_INTERVAL = 30000

// 清除错误状态
function clearError() {
  errorType.value = null
  errorMessage.value = ''
  lastErrorTime.value = 0
  // 同时清除 record 中的错误
  if (_currentChat.value?.records && props.recordId) {
    for (let record of _currentChat.value.records) {
      if (record.id === props.recordId) {
        record.recommend_error = undefined
        break
      }
    }
  }
}

// 保存错误到 record
function saveErrorToRecord(type: ErrorType, message: string) {
  lastErrorTime.value = Date.now()
  if (_currentChat.value?.records && props.recordId) {
    for (let record of _currentChat.value.records) {
      if (record.id === props.recordId) {
        record.recommend_error = JSON.stringify({ type, message, timestamp: lastErrorTime.value })
        break
      }
    }
  }
}

// 从 record 恢复错误状态
function restoreErrorFromRecord(): boolean {
  if (_currentChat.value?.records && props.recordId) {
    for (let record of _currentChat.value.records) {
      if (record.id === props.recordId && record.recommend_error) {
        try {
          const errorData = JSON.parse(record.recommend_error)
          errorType.value = errorData.type as ErrorType
          errorMessage.value = errorData.message
          lastErrorTime.value = errorData.timestamp || Date.now()
          return true
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  }
  return false
}

// 判断是否可以自动重试（可重试的错误类型 + 距离上次错误超过最小间隔）
function canAutoRetry(): boolean {
  // 只有这些错误类型可以自动重试
  const retryableErrors: ErrorType[] = ['quota', 'timeout', 'network']
  if (!errorType.value || !retryableErrors.includes(errorType.value)) {
    return false
  }
  // 检查时间间隔
  const now = Date.now()
  // quota 错误使用更长的重试间隔
  const interval = errorType.value === 'quota' ? AUTO_RETRY_QUOTA_INTERVAL : AUTO_RETRY_MIN_INTERVAL
  return now - lastErrorTime.value >= interval
}

// 页面可见性变化处理 - 用户充值后返回页面时自动重试
function handleVisibilityChange() {
  if (document.visibilityState === 'visible' && errorType.value && canAutoRetry()) {
    retryGetQuestions()
  }
}

// 窗口获得焦点时也尝试重试
function handleWindowFocus() {
  if (errorType.value && canAutoRetry()) {
    retryGetQuestions()
  }
}

const _currentChat = computed({
  get() {
    return props.currentChat
  },
  set(v) {
    emits('update:currentChat', v)
  },
})

const computedQuestions = computed<string[]>(() => {
  if (
    props.questions &&
    props.questions.length > 0 &&
    startsWith(props.questions.trim(), '[') &&
    endsWith(props.questions.trim(), ']')
  ) {
    try {
      const parsed = JSON.parse(props.questions)
      // 确保返回的是数组
      return Array.isArray(parsed) ? parsed : []
    } catch (e) {
      return []
    }
  }
  return []
})

// 根据推荐问题文本推断意图类型，显示对应的emoji标签
function getQuestionIntent(question: string): { icon: string; label: string } {
  const q = question.toLowerCase()
  // 预测类（最高优先级，因为预测是最明确的意图信号）
  if (['预测', '预估', '预计', '未来', 'forecast', 'predict'].some(kw => q.includes(kw))) {
    return { icon: '🔮', label: t('qa.intent_prediction') }
  }
  // 分析类
  if (['分析', '解读', '洞察', '评估', 'analyze', 'analysis'].some(kw => q.includes(kw))) {
    return { icon: '📈', label: t('qa.intent_analysis') }
  }
  // 文档类（PDF推荐问题）— 排在分析之后，因为"分析文档"应归为分析
  if (['文档', '文件', '核心内容', '核心结论', '核心观点', '关键数据', '补充内容', 'document', 'summary', 'conclusion'].some(kw => q.includes(kw))) {
    return { icon: '📄', label: t('qa.intent_document') }
  }
  // 总结类
  if (['总结', '概括', '概述', '整体', '情况', '特点'].some(kw => q.includes(kw))) {
    return { icon: '📝', label: t('qa.intent_summary') }
  }
  // 默认：数据查询
  return { icon: '🔍', label: t('qa.intent_query') }
}

// 检查是否是保存的错误状态（从后端恢复）
const savedErrorFromBackend = computed(() => {
  if (
    props.questions &&
    props.questions.length > 0 &&
    startsWith(props.questions.trim(), '{') &&
    endsWith(props.questions.trim(), '}')
  ) {
    try {
      const data = JSON.parse(props.questions)
      if (data.error === true && data.message) {
        return data
      }
    } catch (e) {
      // 忽略解析错误
    }
  }
  return null
})

// 监听 recordId 变化，恢复错误状态
watch(
  () => props.recordId,
  (newRecordId, oldRecordId) => {
    // 当 recordId 变化时（切换对话或切换记录），完全重置所有状态
    // 先重置所有本地状态
    errorType.value = null
    errorMessage.value = ''
    loading.value = false
    questionsVisible.value = false
    
    // 如果 recordId 变为 undefined（切换到空对话），完全重置
    if (newRecordId === undefined) {
      hasTriedLoading.value = false
      stoppedByUser.value = false
      lastErrorTime.value = 0
      return
    }
    
    // 如果是切换到不同的 recordId（不是初始化），重置 hasTriedLoading
    if (oldRecordId !== undefined && newRecordId !== oldRecordId) {
      hasTriedLoading.value = false
      stoppedByUser.value = false
      lastErrorTime.value = 0
    }

    // 首先检查是否有从后端恢复的错误
    if (savedErrorFromBackend.value) {
      const detectedType = detectErrorType(savedErrorFromBackend.value.message)
      errorType.value = detectedType
      errorMessage.value = savedErrorFromBackend.value.message
      hasTriedLoading.value = true
      return
    }

    // 尝试从 record 恢复错误状态（前端临时状态）
    const hasError = restoreErrorFromRecord()

    // 检查是否已有推荐问题
    const hasQuestions = computedQuestions.value.length > 0

    // 如果有错误或有问题，说明之前已经尝试过加载
    // 如果是新的 recordId 且没有错误也没有问题，则重置 hasTriedLoading
    if (hasError || hasQuestions) {
      hasTriedLoading.value = true
    } else {
      hasTriedLoading.value = false
    }
  },
  { immediate: true }
)

// 监听 questions 变化，检查是否是后端恢复的错误
watch(
  () => props.questions,
  () => {
    if (savedErrorFromBackend.value && !errorType.value) {
      const detectedType = detectErrorType(savedErrorFromBackend.value.message)
      errorType.value = detectedType
      errorMessage.value = savedErrorFromBackend.value.message
      hasTriedLoading.value = true
    }
  },
  { immediate: true }
)

// 监听问题变化，触发动画
watch(
  computedQuestions,
  (newVal) => {
    if (newVal.length > 0) {
      questionsVisible.value = false
      setTimeout(() => {
        questionsVisible.value = true
      }, 50)
    }
  },
  { immediate: true }
)

// 是否应该显示组件
const shouldShow = computed(() => {
  // 如果 recordId 为 undefined，不显示组件
  if (props.recordId === undefined) return false
  // 首次对话总是显示
  if (props.firstChat) return true
  // 有错误时显示
  if (errorType.value) return true
  // 被用户打断时显示（提供重试入口）
  if (stoppedByUser.value) return true
  // 有问题或正在加载时显示
  return computedQuestions.value.length > 0 || loading.value
})

// 判断是否应该显示空状态（只有在确实尝试过加载且没有错误且不是被打断时才显示）
const showEmptyState = computed(() => {
  return (
    props.firstChat &&
    !loading.value &&
    !errorType.value &&
    !stoppedByUser.value &&
    computedQuestions.value.length === 0 &&
    hasTriedLoading.value
  )
})

// 判断是否显示初始状态（还没有尝试加载，提供手动触发按钮）
const showInitialState = computed(() => {
  return (
    props.firstChat &&
    !loading.value &&
    !errorType.value &&
    !hasTriedLoading.value &&
    !stoppedByUser.value &&
    computedQuestions.value.length === 0
  )
})

// 判断是否显示"被打断，可重试"状态
const showStoppedState = computed(() => {
  return (
    stoppedByUser.value &&
    !loading.value &&
    !errorType.value &&
    computedQuestions.value.length === 0
  )
})

const { t } = useI18n()

function clickQuestion(question: string): void {
  if (!props.disabled) {
    emits('clickQuestion', question)
  }
}

const stopFlag = ref(false)

async function getRecommendQuestions() {
  stopFlag.value = false
  stoppedByUser.value = false
  loading.value = true
  hasTriedLoading.value = true
  clearError()

  try {
    const controller: AbortController = new AbortController()
    const response = await chatApi.recommendQuestions(props.recordId, controller)
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let tempResult = ''

    while (true) {
      if (stopFlag.value) {
        controller.abort()
        loading.value = false
        break
      }

      const { done, value } = await reader.read()

      if (!done) {
        let chunk = decoder.decode(value, { stream: true })
        tempResult += chunk
      }

      // done 时也要处理 tempResult 中残留的最后一条消息
      // SSE 流结束时，最后一条消息可能没有 \n\n 结尾
      if (done && tempResult.trim()) {
        // 使用与主循环一致的 data: 前缀解析方式，替代旧的正则匹配
        // 旧正则 /data:\{.*\}/g 在 data 字段包含 } 时会截断
        const residualEvents = tempResult.split('\n\n')
        for (const residualEvent of residualEvents) {
          const trimmedResidual = residualEvent.trim()
          if (!trimmedResidual || !trimmedResidual.startsWith('data:')) continue
          const residualJson = trimmedResidual.slice(5).trim()
          if (!residualJson) continue
          try {
            const data = JSON.parse(residualJson)
            if (data.type === 'recommended_question' && data.content) {
              if (startsWith(data.content.trim(), '[') && endsWith(data.content.trim(), ']')) {
                if (_currentChat.value?.records) {
                  for (let record of _currentChat.value.records) {
                    if (record.id === props.recordId) {
                      record.recommended_question = data.content
                      record.recommend_error = undefined
                    }
                  }
                }
              }
            } else if (data.type === 'layered_recommendations' && data.data) {
              if (_currentChat.value?.records) {
                for (let record of _currentChat.value.records) {
                  if (record.id === props.recordId) {
                    record.layered_recommendations = {
                      ...(record.layered_recommendations || {}),
                      ...data.data,
                    }
                  }
                }
              }
            }
          } catch (_e) {
            // 忽略解析错误
          }
        }
        break
      }
      if (done) break

      // 使用 \n\n 分隔符解析 SSE 事件
      // 原正则 /data:.*}\n\n/g 在 data 字段包含 } 时会截断
      const events = tempResult.split('\n\n')
      // 最后一个元素可能是不完整的事件，保留到下次处理
      const incomplete = events.pop() || ''
      tempResult = incomplete

      if (events.length === 0) {
        continue
      }

      for (const event of events) {
        const trimmed = event.trim()
        if (!trimmed || !trimmed.startsWith('data:')) continue
        const jsonStr = trimmed.slice(5).trim() // 去掉 "data:" 前缀
        if (!jsonStr) continue

        let data
        try {
          data = JSON.parse(jsonStr)
        } catch (err) {
          throw err
        }

        // 处理错误响应
        if (data.type === 'error' || (data.code && data.code !== 200)) {
          const detectedType = detectErrorType(data.msg || data.content)
          errorType.value = detectedType
          errorMessage.value = data.msg || data.content
          // 保存错误到 record，以便切换对话后恢复
          saveErrorToRecord(detectedType, errorMessage.value)
          return
        }

        switch (data.type) {
          case 'recommended_question':
            if (
              data.content &&
              data.content.length > 0 &&
              startsWith(data.content.trim(), '[') &&
              endsWith(data.content.trim(), ']')
            ) {
              if (_currentChat.value?.records) {
                for (let record of _currentChat.value.records) {
                  if (record.id === props.recordId) {
                    record.recommended_question = data.content
                    // 清除之前的错误
                    record.recommend_error = undefined
                    await nextTick()
                  }
                }
              }
            }
            break
          case 'layered_recommendations':
            // 处理三层推荐系统的pre层（之前被静默丢弃）
            // 保存到record中，以便历史记录恢复和其他组件使用
            if (data.data && _currentChat.value?.records) {
              for (let record of _currentChat.value.records) {
                if (record.id === props.recordId) {
                  record.layered_recommendations = {
                    ...(record.layered_recommendations || {}),
                    ...data.data,
                  }
                }
              }
            }
            break
          case 'recommended_question_result':
            // LLM流式生成的中间chunk，无需处理（最终结果由recommended_question事件发送）
            break
          case 'recommend_questions_finish':
            break
        }
      }
    }
  } catch (error: any) {
    const detectedType = detectErrorType(error)
    errorType.value = detectedType
    errorMessage.value = error?.message || String(error)
    // 保存错误到 record
    saveErrorToRecord(detectedType, errorMessage.value)
  } finally {
    loading.value = false
    emits('loadingOver')
  }
}

function retryGetQuestions() {
  clearError()
  getRecommendQuestions()
}

function stop() {
  stopFlag.value = true
  // 只有在正在加载时才标记为用户打断，且没有已生成的问题
  if (loading.value) {
    stoppedByUser.value = true
  }
  loading.value = false
  emits('stop')
}

// 组件挂载时注册事件监听
onMounted(() => {
  // 监听页面可见性变化
  document.addEventListener('visibilitychange', handleVisibilityChange)
  // 监听窗口焦点
  window.addEventListener('focus', handleWindowFocus)
})

onBeforeUnmount(() => {
  stop()
  // 清理事件监听
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  window.removeEventListener('focus', handleWindowFocus)
})

// 新增：监听 currentChat 变化，当切换对话时停止加载
watch(
  () => props.currentChat?.id,
  (newChatId, oldChatId) => {
    // 当对话 ID 变化时（切换对话），停止当前的加载
    if (oldChatId !== undefined && newChatId !== oldChatId) {
      if (loading.value) {
        stop()
      }
    }
  }
)

defineExpose({ getRecommendQuestions, id: () => props.recordId, stop, retryGetQuestions })
</script>

<template>
  <div v-if="shouldShow" class="recommend-questions" :class="{ 'first-chat': firstChat }">
    <!-- 标题区域 - 只在有问题或加载时显示 -->
    <div class="section-header">
      <div
        v-if="firstChat && !errorType && !loading && computedQuestions.length > 0"
        class="title-row"
      >
        <span class="title-icon"><el-icon :size="18"><icon_search_fancy /></el-icon></span>
        <span class="title-text">{{ t('qa.guess_u_ask') }}</span>
        <button class="refresh-btn" :disabled="disabled" @click="retryGetQuestions" :title="t('qa.recommend_refresh')">
          <span class="refresh-icon-text"><el-icon :size="14"><icon_refresh_outlined /></el-icon></span>
          <span class="refresh-label">{{ t('qa.recommend_refresh') }}</span>
        </button>
      </div>
      <div
        v-else-if="!firstChat && !errorType && !loading && computedQuestions.length > 0"
        class="title-row continue"
      >
        <span class="title-icon"><el-icon :size="16"><icon_search_fancy /></el-icon></span>
        <span class="title-text">{{ t('qa.continue_to_ask') }}</span>
        <button class="refresh-btn" :disabled="disabled" @click="retryGetQuestions" :title="t('qa.recommend_refresh')">
          <span class="refresh-icon-text"><el-icon :size="14"><icon_refresh_outlined /></el-icon></span>
          <span class="refresh-label">{{ t('qa.recommend_refresh') }}</span>
        </button>
      </div>
    </div>

    <!-- 加载状态 - 骨架屏效果 -->
    <div v-if="loading" class="loading-container">
      <div class="loading-header">
        <div class="loading-spinner"></div>
        <span class="loading-text">{{ t('qa.recommend_loading') }}</span>
      </div>
      <div class="skeleton-grid">
        <div v-for="i in 4" :key="i" class="skeleton-item">
          <div class="skeleton-line" :style="{ width: `${60 + Math.random() * 30}%` }"></div>
        </div>
      </div>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="errorType" class="error-container" :class="errorType">
      <div class="error-card">
        <div class="error-icon-wrapper">
          <span class="error-icon">
            <template v-if="errorType === 'quota'">⚠️</template>
            <template v-else-if="errorType === 'timeout'">⏱️</template>
            <template v-else-if="errorType === 'network'">🌐</template>
            <template v-else-if="errorType === 'parse'">🔍</template>
            <template v-else-if="errorType === 'datasource'">💾</template>
            <template v-else-if="errorType === 'model'">🤖</template>
            <template v-else-if="errorType === 'api'">🔑</template>
            <template v-else-if="errorType === 'db'">🔌</template>
            <template v-else-if="errorType === 'sql'">📝</template>
            <template v-else>❌</template>
          </span>
        </div>
        <div class="error-body">
          <div class="error-title">
            <template v-if="errorType === 'quota'">{{ t('qa.api_quota_exceeded') }}</template>
            <template v-else-if="errorType === 'timeout'">{{
              t('qa.error_suggestion_timeout').split('，')[0]
            }}</template>
            <template v-else-if="errorType === 'network'">{{
              t('qa.error_network').split('，')[0]
            }}</template>
            <template v-else-if="errorType === 'parse'">{{
              t('qa.error_parse').split('，')[0]
            }}</template>
            <template v-else-if="errorType === 'datasource'">{{
              t('qa.error_datasource')
            }}</template>
            <template v-else-if="errorType === 'model'">{{ t('qa.error_model') }}</template>
            <template v-else-if="errorType === 'api'">{{
              t('qa.error_suggestion_model').split('，')[0]
            }}</template>
            <template v-else-if="errorType === 'db'">{{ t('chat.ds_is_invalid') }}</template>
            <template v-else-if="errorType === 'sql'">{{ t('chat.exec-sql-err') }}</template>
            <template v-else>{{ t('qa.error') }}</template>
          </div>
          <div class="error-desc">
            <template v-if="errorType === 'quota'">{{ t('qa.recommend_error_quota') }}</template>
            <template v-else-if="errorType === 'timeout'">{{
              t('qa.recommend_error_timeout')
            }}</template>
            <template v-else-if="errorType === 'network'">{{
              t('qa.recommend_error_network')
            }}</template>
            <template v-else-if="errorType === 'parse'">{{
              t('qa.error_suggestion_parse')
            }}</template>
            <template v-else-if="errorType === 'datasource'">{{
              t('qa.error_suggestion_datasource')
            }}</template>
            <template v-else-if="errorType === 'model'">{{
              t('qa.error_suggestion_model')
            }}</template>
            <template v-else-if="errorType === 'api'">{{
              t('qa.error_suggestion_model')
            }}</template>
            <template v-else-if="errorType === 'db'">{{ t('qa.error_suggestion_db') }}</template>
            <template v-else-if="errorType === 'sql'">{{ t('qa.error_suggestion_sql') }}</template>
            <template v-else>{{ t('qa.recommend_error_unknown') }}</template>
          </div>
          <div v-if="errorType === 'quota'" class="error-hint">
            <span class="hint-icon">💡</span>
            <span>{{ t('qa.recommend_quota_hint') }}</span>
          </div>
        </div>
        <button class="retry-btn" @click="retryGetQuestions">
          <span class="btn-icon">🔄</span>
          <span>{{ t('qa.recommend_retry') }}</span>
        </button>
      </div>
    </div>

    <!-- 问题网格 -->
    <div
      v-else-if="computedQuestions.length > 0"
      class="questions-container"
      :class="{ visible: questionsVisible }"
    >
      <div class="question-grid">
        <div
          v-for="(question, index) in computedQuestions"
          :key="index"
          class="question-card"
          :class="{ disabled: disabled }"
          :style="{ '--delay': `${index * 0.08}s` }"
          @click="clickQuestion(question)"
        >
          <span class="question-intent-badge" :title="getQuestionIntent(question).label">{{ getQuestionIntent(question).icon }}</span>
          <span class="question-text">{{ question }}</span>
          <span class="question-arrow">→</span>
        </div>
      </div>
    </div>

    <!-- 空状态 - 只有在确实尝试过加载且没有错误时才显示 -->
    <div v-else-if="showEmptyState" class="empty-container">
      <div class="empty-icon">🔍</div>
      <div class="empty-text">{{ t('qa.recommend_empty') }}</div>
    </div>

    <!-- 被用户打断状态 - 提供重新生成入口 -->
    <div v-else-if="showStoppedState" class="initial-container">
      <div class="initial-content">
        <span class="initial-icon">⏸️</span>
        <span class="initial-text">{{ t('qa.recommend_stopped') || '推荐问题生成已中断' }}</span>
      </div>
      <button class="fetch-btn" @click="retryGetQuestions">
        <span class="btn-icon">🔄</span>
        <span>{{ t('qa.recommend_retry') || '重新生成' }}</span>
      </button>
    </div>

    <!-- 初始状态 - 还没有尝试加载，显示手动获取按钮 -->
    <div v-else-if="showInitialState" class="initial-container">
      <div class="initial-content">
        <span class="initial-icon">💡</span>
        <span class="initial-text">{{ t('qa.guess_u_ask') }}</span>
      </div>
      <button class="fetch-btn" @click="getRecommendQuestions">
        <span class="btn-icon">💡</span>
        <span>{{ t('qa.recommend_fetch') }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped lang="less">
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.7);
@dark-border: rgba(139, 92, 246, 0.2);

.recommend-questions {
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 24px;

  // 标题区域
  .section-header {
    .title-row {
      display: flex;
      align-items: center;
      gap: 8px;

      .title-icon {
        font-size: 18px;
        display: inline-flex;
        align-items: center;
        color: @primary-400;
      }

      .title-text {
        font-size: 15px;
        font-weight: 600;
        color: @dark-text;
        letter-spacing: 0.3px;
      }

      .refresh-btn {
        margin-left: auto;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 5px 12px;
        background: rgba(139, 92, 246, 0.1);
        border: 1px solid rgba(139, 92, 246, 0.25);
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.25s ease;
        font-family: inherit;
        outline: none;

        .refresh-icon-text {
          font-size: 13px;
          display: inline-flex;
          align-items: center;
          transition: transform 0.4s ease;
          color: @dark-text-muted;
        }

        .refresh-label {
          font-size: 12px;
          color: @dark-text-muted;
          font-weight: 500;
        }

        &:hover:not(:disabled) {
          background: rgba(139, 92, 246, 0.2);
          border-color: rgba(139, 92, 246, 0.4);
          transform: translateY(-1px);

          .refresh-icon-text {
            transform: rotate(180deg);
            color: @primary-400;
          }

          .refresh-label {
            color: @primary-400;
          }
        }

        &:active:not(:disabled) {
          transform: scale(0.96);
        }

        &:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }
      }

      &.continue {
        .title-icon {
          color: @dark-text-secondary;
        }
        .title-text {
          font-size: 14px;
          font-weight: 500;
          color: @dark-text-secondary;
        }
      }
    }
  }

  // 加载状态
  .loading-container {
    display: flex;
    flex-direction: column;
    gap: 14px;

    .loading-header {
      display: flex;
      align-items: center;
      gap: 10px;

      .loading-spinner {
        width: 18px;
        height: 18px;
        border: 2px solid rgba(139, 92, 246, 0.2);
        border-top-color: @primary-400;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
      }

      .loading-text {
        font-size: 13px;
        color: @dark-text-muted;
      }
    }

    .skeleton-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;

      .skeleton-item {
        background: linear-gradient(
          135deg,
          rgba(139, 92, 246, 0.08) 0%,
          rgba(168, 85, 247, 0.04) 100%
        );
        border: 1px solid rgba(139, 92, 246, 0.1);
        border-radius: 12px;
        padding: 14px 16px;
        height: 48px;

        .skeleton-line {
          height: 14px;
          background: linear-gradient(
            90deg,
            rgba(139, 92, 246, 0.1) 0%,
            rgba(139, 92, 246, 0.2) 50%,
            rgba(139, 92, 246, 0.1) 100%
          );
          background-size: 200% 100%;
          border-radius: 4px;
          animation: shimmer 1.5s ease-in-out infinite;
        }
      }
    }
  }

  // 错误状态
  .error-container {
    .error-card {
      display: flex;
      align-items: flex-start;
      gap: 14px;
      padding: 16px 18px;
      border-radius: 14px;
      animation: slideIn 0.3s ease;

      .error-icon-wrapper {
        width: 42px;
        height: 42px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;

        .error-icon {
          font-size: 22px;
        }
      }

      .error-body {
        flex: 1;
        min-width: 0;

        .error-title {
          font-size: 14px;
          font-weight: 600;
          margin-bottom: 4px;
        }

        .error-desc {
          font-size: 13px;
          line-height: 1.5;
          opacity: 0.85;
        }
      }

      .retry-btn {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 14px;
        border-radius: 10px;
        font-size: 13px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
        flex-shrink: 0;
        align-self: center;

        .btn-icon {
          font-size: 14px;
          transition: transform 0.3s ease;
        }

        &:hover {
          transform: translateY(-2px);
          .btn-icon {
            transform: rotate(180deg);
          }
        }

        &:active {
          transform: translateY(0);
        }
      }
    }

    // 余额不足 - 金色警告
    &.quota .error-card {
      background: linear-gradient(
        135deg,
        rgba(251, 191, 36, 0.15) 0%,
        rgba(245, 158, 11, 0.08) 100%
      );
      border: 1px solid rgba(251, 191, 36, 0.3);

      .error-icon-wrapper {
        background: rgba(251, 191, 36, 0.2);
        .error-icon {
          filter: drop-shadow(0 0 6px rgba(251, 191, 36, 0.5));
        }
      }
      .error-title {
        color: rgba(253, 224, 71, 1);
      }
      .error-desc {
        color: rgba(253, 224, 71, 0.8);
      }
      .error-hint {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-top: 8px;
        padding: 8px 12px;
        background: rgba(251, 191, 36, 0.1);
        border-radius: 8px;
        font-size: 12px;
        color: rgba(253, 224, 71, 0.7);

        .hint-icon {
          font-size: 14px;
        }
      }
      .retry-btn {
        background: rgba(251, 191, 36, 0.2);
        border: 1px solid rgba(251, 191, 36, 0.3);
        color: rgba(253, 224, 71, 1);
        &:hover {
          background: rgba(251, 191, 36, 0.3);
        }
      }
    }

    // 超时 - 蓝色
    &.timeout .error-card {
      background: linear-gradient(
        135deg,
        rgba(59, 130, 246, 0.15) 0%,
        rgba(37, 99, 235, 0.08) 100%
      );
      border: 1px solid rgba(59, 130, 246, 0.3);

      .error-icon-wrapper {
        background: rgba(59, 130, 246, 0.2);
      }
      .error-title {
        color: rgba(147, 197, 253, 1);
      }
      .error-desc {
        color: rgba(147, 197, 253, 0.8);
      }
      .retry-btn {
        background: rgba(59, 130, 246, 0.2);
        border: 1px solid rgba(59, 130, 246, 0.3);
        color: rgba(147, 197, 253, 1);
        &:hover {
          background: rgba(59, 130, 246, 0.3);
        }
      }
    }

    // 网络错误 - 橙色
    &.network .error-card {
      background: linear-gradient(
        135deg,
        rgba(249, 115, 22, 0.15) 0%,
        rgba(234, 88, 12, 0.08) 100%
      );
      border: 1px solid rgba(249, 115, 22, 0.3);

      .error-icon-wrapper {
        background: rgba(249, 115, 22, 0.2);
      }
      .error-title {
        color: rgba(253, 186, 116, 1);
      }
      .error-desc {
        color: rgba(253, 186, 116, 0.8);
      }
      .retry-btn {
        background: rgba(249, 115, 22, 0.2);
        border: 1px solid rgba(249, 115, 22, 0.3);
        color: rgba(253, 186, 116, 1);
        &:hover {
          background: rgba(249, 115, 22, 0.3);
        }
      }
    }

    // 未知错误 - 红色
    &.unknown .error-card {
      background: linear-gradient(
        135deg,
        rgba(248, 113, 113, 0.15) 0%,
        rgba(239, 68, 68, 0.08) 100%
      );
      border: 1px solid rgba(248, 113, 113, 0.3);

      .error-icon-wrapper {
        background: rgba(248, 113, 113, 0.2);
      }
      .error-title {
        color: rgba(252, 165, 165, 1);
      }
      .error-desc {
        color: rgba(252, 165, 165, 0.8);
      }
      .retry-btn {
        background: rgba(248, 113, 113, 0.2);
        border: 1px solid rgba(248, 113, 113, 0.3);
        color: rgba(252, 165, 165, 1);
        &:hover {
          background: rgba(248, 113, 113, 0.3);
        }
      }
    }

    // 解析错误 - 粉色
    &.parse .error-card {
      background: linear-gradient(
        135deg,
        rgba(236, 72, 153, 0.15) 0%,
        rgba(219, 39, 119, 0.08) 100%
      );
      border: 1px solid rgba(236, 72, 153, 0.3);

      .error-icon-wrapper {
        background: rgba(236, 72, 153, 0.2);
      }
      .error-title {
        color: rgba(249, 168, 212, 1);
      }
      .error-desc {
        color: rgba(249, 168, 212, 0.8);
      }
      .retry-btn {
        background: rgba(236, 72, 153, 0.2);
        border: 1px solid rgba(236, 72, 153, 0.3);
        color: rgba(249, 168, 212, 1);
        &:hover {
          background: rgba(236, 72, 153, 0.3);
        }
      }
    }

    // 数据源错误 - 靛蓝色
    &.datasource .error-card {
      background: linear-gradient(
        135deg,
        rgba(99, 102, 241, 0.15) 0%,
        rgba(79, 70, 229, 0.08) 100%
      );
      border: 1px solid rgba(99, 102, 241, 0.3);

      .error-icon-wrapper {
        background: rgba(99, 102, 241, 0.2);
      }
      .error-title {
        color: rgba(165, 180, 252, 1);
      }
      .error-desc {
        color: rgba(165, 180, 252, 0.8);
      }
      .retry-btn {
        background: rgba(99, 102, 241, 0.2);
        border: 1px solid rgba(99, 102, 241, 0.3);
        color: rgba(165, 180, 252, 1);
        &:hover {
          background: rgba(99, 102, 241, 0.3);
        }
      }
    }

    // 模型错误 - 紫罗兰色
    &.model .error-card {
      background: linear-gradient(
        135deg,
        rgba(167, 139, 250, 0.15) 0%,
        rgba(139, 92, 246, 0.08) 100%
      );
      border: 1px solid rgba(167, 139, 250, 0.3);

      .error-icon-wrapper {
        background: rgba(167, 139, 250, 0.2);
      }
      .error-title {
        color: rgba(196, 181, 253, 1);
      }
      .error-desc {
        color: rgba(196, 181, 253, 0.8);
      }
      .retry-btn {
        background: rgba(167, 139, 250, 0.2);
        border: 1px solid rgba(167, 139, 250, 0.3);
        color: rgba(196, 181, 253, 1);
        &:hover {
          background: rgba(167, 139, 250, 0.3);
        }
      }
    }

    // API 错误 - 深紫色
    &.api .error-card {
      background: linear-gradient(
        135deg,
        rgba(139, 92, 246, 0.15) 0%,
        rgba(124, 58, 237, 0.08) 100%
      );
      border: 1px solid rgba(139, 92, 246, 0.3);

      .error-icon-wrapper {
        background: rgba(139, 92, 246, 0.2);
      }
      .error-title {
        color: rgba(196, 181, 253, 1);
      }
      .error-desc {
        color: rgba(196, 181, 253, 0.8);
      }
      .retry-btn {
        background: rgba(139, 92, 246, 0.2);
        border: 1px solid rgba(139, 92, 246, 0.3);
        color: rgba(196, 181, 253, 1);
        &:hover {
          background: rgba(139, 92, 246, 0.3);
        }
      }
    }

    // 数据库错误 - 青色
    &.db .error-card {
      background: linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(8, 145, 178, 0.08) 100%);
      border: 1px solid rgba(6, 182, 212, 0.3);

      .error-icon-wrapper {
        background: rgba(6, 182, 212, 0.2);
      }
      .error-title {
        color: rgba(103, 232, 249, 1);
      }
      .error-desc {
        color: rgba(103, 232, 249, 0.8);
      }
      .retry-btn {
        background: rgba(6, 182, 212, 0.2);
        border: 1px solid rgba(6, 182, 212, 0.3);
        color: rgba(103, 232, 249, 1);
        &:hover {
          background: rgba(6, 182, 212, 0.3);
        }
      }
    }

    // SQL 错误 - 琥珀色
    &.sql .error-card {
      background: linear-gradient(
        135deg,
        rgba(245, 158, 11, 0.15) 0%,
        rgba(217, 119, 6, 0.08) 100%
      );
      border: 1px solid rgba(245, 158, 11, 0.3);

      .error-icon-wrapper {
        background: rgba(245, 158, 11, 0.2);
      }
      .error-title {
        color: rgba(252, 211, 77, 1);
      }
      .error-desc {
        color: rgba(252, 211, 77, 0.8);
      }
      .retry-btn {
        background: rgba(245, 158, 11, 0.2);
        border: 1px solid rgba(245, 158, 11, 0.3);
        color: rgba(252, 211, 77, 1);
        &:hover {
          background: rgba(245, 158, 11, 0.3);
        }
      }
    }
  }

  // 问题网格 - 高级卡片设计
  .questions-container {
    opacity: 0;
    transform: translateY(10px);
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);

    &.visible {
      opacity: 1;
      transform: translateY(0);
    }

    .question-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
    }

    .question-card {
      position: relative;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 14px 16px;
      background: linear-gradient(
        145deg,
        rgba(139, 92, 246, 0.12) 0%,
        rgba(168, 85, 247, 0.06) 100%
      );
      border: 1.5px solid rgba(139, 92, 246, 0.18);
      border-radius: 14px;
      cursor: pointer;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      animation: cardFadeIn 0.45s ease backwards;
      animation-delay: var(--delay);
      overflow: hidden;

      // 顶部高光
      &::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 50%;
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.04) 0%, transparent 100%);
        pointer-events: none;
        transition: opacity 0.3s ease;
      }

      // 悬停背景
      &::after {
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(
          145deg,
          rgba(139, 92, 246, 0.22) 0%,
          rgba(168, 85, 247, 0.12) 100%
        );
        opacity: 0;
        transition: opacity 0.3s ease;
      }

      .question-intent-badge {
        width: 28px;
        height: 28px;
        border-radius: 8px;
        background: linear-gradient(
          145deg,
          rgba(139, 92, 246, 0.28) 0%,
          rgba(168, 85, 247, 0.2) 100%
        );
        font-size: 15px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        z-index: 1;
        box-shadow: 0 2px 8px rgba(139, 92, 246, 0.15);
      }

      .question-text {
        flex: 1;
        font-size: 13px;
        line-height: 1.55;
        color: @dark-text;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        position: relative;
        z-index: 1;
        font-weight: 400;
        letter-spacing: 0.2px;
      }

      .question-arrow {
        font-size: 16px;
        color: @dark-text-muted;
        opacity: 0;
        transform: translateX(-10px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        z-index: 1;
      }

      &:hover {
        border-color: rgba(139, 92, 246, 0.4);
        transform: translateY(-3px);
        box-shadow:
          0 12px 32px rgba(139, 92, 246, 0.2),
          0 0 0 1px rgba(139, 92, 246, 0.1) inset;

        &::after {
          opacity: 1;
        }

        .question-intent-badge {
          background: linear-gradient(145deg, @primary-500 0%, @primary-600 100%);
          transform: scale(1.1);
          box-shadow: 0 4px 12px rgba(139, 92, 246, 0.35);
        }

        .question-arrow {
          opacity: 1;
          transform: translateX(0);
          color: @primary-400;
        }
      }

      &:active {
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(139, 92, 246, 0.15);
      }

      &.disabled {
        cursor: not-allowed;
        opacity: 0.5;
        &:hover {
          transform: none;
          box-shadow: none;
          &::after {
            opacity: 0;
          }
          .question-intent-badge {
            transform: none;
            background: linear-gradient(
              145deg,
              rgba(139, 92, 246, 0.28) 0%,
              rgba(168, 85, 247, 0.2) 100%
            );
            box-shadow: 0 2px 8px rgba(139, 92, 246, 0.15);
          }
          .question-arrow {
            opacity: 0;
          }
        }
      }
    }
  }

  // 空状态
  .empty-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px 16px;
    background: rgba(139, 92, 246, 0.06);
    border: 1px dashed rgba(139, 92, 246, 0.2);
    border-radius: 14px;
    animation: fadeIn 0.3s ease;

    .empty-icon {
      font-size: 28px;
      margin-bottom: 10px;
      opacity: 0.7;
    }

    .empty-text {
      font-size: 13px;
      color: @dark-text-muted;
      text-align: center;
    }
  }

  // 初始状态 - 还没有尝试加载，显示手动获取按钮
  .initial-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 20px;
    padding: 28px 16px;
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.08) 0%, rgba(168, 85, 247, 0.04) 100%);
    border: 1px solid rgba(139, 92, 246, 0.15);
    border-radius: 14px;
    animation: fadeIn 0.3s ease;

    .initial-content {
      display: flex;
      align-items: center;
      gap: 10px;

      .initial-icon {
        font-size: 22px;
        animation: bounce 2s ease-in-out infinite;
      }

      .initial-text {
        font-size: 15px;
        font-weight: 600;
        color: @dark-text;
        letter-spacing: 0.3px;
      }
    }

    .fetch-btn {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 20px;
      background: linear-gradient(
        135deg,
        rgba(139, 92, 246, 0.2) 0%,
        rgba(168, 85, 247, 0.15) 100%
      );
      border: 1px solid rgba(139, 92, 246, 0.3);
      border-radius: 10px;
      color: @primary-400;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.25s ease;

      .btn-icon {
        font-size: 16px;
      }

      &:hover {
        background: linear-gradient(
          135deg,
          rgba(139, 92, 246, 0.3) 0%,
          rgba(168, 85, 247, 0.2) 100%
        );
        border-color: rgba(139, 92, 246, 0.5);
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(139, 92, 246, 0.25);
      }

      &:active {
        transform: translateY(0);
      }
    }
  }
}

// 动画
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

@keyframes bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-3px);
  }
}

@keyframes sparkle {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.15);
    opacity: 0.8;
  }
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes cardFadeIn {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

// 响应式
@media (max-width: 768px) {
  .recommend-questions {
    gap: 12px;

    .section-header .title-row {
      .title-icon {
        font-size: 16px;
        :deep(.ed-icon) {
          font-size: 16px !important;
        }
      }
      .title-text {
        font-size: 14px;
      }
    }

    .loading-container .skeleton-grid {
      gap: 8px;
    }

    .error-container .error-card {
      padding: 14px;
      gap: 12px;
      flex-wrap: wrap;

      .error-icon-wrapper {
        width: 38px;
        height: 38px;
      }
      .error-body {
        .error-title {
          font-size: 13px;
        }
        .error-desc {
          font-size: 12px;
        }
      }
      .retry-btn {
        width: 100%;
        justify-content: center;
        margin-top: 4px;
      }
    }

    .questions-container .question-grid {
      gap: 8px;
    }
    .questions-container .question-card {
      padding: 10px 12px;
      .question-intent-badge {
        width: 24px;
        height: 24px;
        font-size: 13px;
      }
      .question-text {
        font-size: 12px;
      }
    }
  }
}

@media (max-width: 480px) {
  .recommend-questions {
    .questions-container .question-grid {
      grid-template-columns: 1fr;
      gap: 6px;
    }

    .error-container .error-card {
      padding: 12px;
      .error-icon-wrapper {
        width: 34px;
        height: 34px;
        .error-icon {
          font-size: 18px;
        }
      }
    }

    .empty-container {
      padding: 20px 14px;
      .empty-icon {
        font-size: 24px;
      }
      .empty-text {
        font-size: 12px;
      }
    }

    .initial-container {
      padding: 24px 14px;
      gap: 18px;

      .initial-content {
        .initial-icon {
          font-size: 18px;
        }
        .initial-text {
          font-size: 13px;
        }
      }

      .fetch-btn {
        padding: 8px 16px;
        font-size: 13px;
        .btn-icon {
          font-size: 14px;
        }
      }
    }
  }
}
</style>
