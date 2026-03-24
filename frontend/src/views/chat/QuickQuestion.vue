<script lang="ts" setup>
import { computed, ref, watch } from 'vue'
import icon_quick_question from '@/assets/svg/icon_quick_question.svg'
import icon_replace_outlined from '@/assets/svg/icon_replace_outlined.svg'
import { ChatInfo } from '@/api/chat.ts'
import RecommendQuestion from '@/views/chat/RecommendQuestion.vue'

const recommendQuestionRef = ref()
const popoverRef = ref()

const getRecommendQuestions = () => {
  recommendQuestionRef.value?.getRecommendQuestions()
}

const retrieveQuestions = () => {
  recommendQuestionRef.value?.getRecommendQuestions()
}

const quickAsk = (question: string) => {
  if (props.disabled) {
    return
  }
  emits('quickAsk', question)
  hiddenProps()
}

const hiddenProps = () => {
  popoverRef.value?.hide()
}

const onChatStop = () => {
  emits('stop')
}

const loadingOver = () => {
  emits('loadingOver')
}

const emits = defineEmits(['quickAsk', 'loadingOver', 'stop'])

const props = withDefaults(
  defineProps<{
    recordId?: number
    datasourceId?: number
    currentChat?: ChatInfo
    firstChat?: boolean
    disabled?: boolean
  }>(),
  {
    recordId: undefined,
    datasourceId: undefined,
    currentChat: () => new ChatInfo(),
    firstChat: false,
    disabled: false,
  }
)

// 获取first_chat记录的推荐问题
const firstChatQuestions = computed(() => {
  if (props.currentChat?.records) {
    const firstChatRecord = props.currentChat.records.find((record) => record.first_chat)
    return firstChatRecord?.recommended_question || '[]'
  }
  return '[]'
})

// 监听recordId变化，当有新的recordId时自动获取推荐问题
// 使用闭包捕获 newId，防止快速切换时 300ms 延迟后 recordId 已变导致为错误的 record 发起请求
let _quickQuestionTimer: ReturnType<typeof setTimeout> | null = null
watch(
  () => props.recordId,
  (newId, oldId) => {
    // 清除上一次的延迟调用
    if (_quickQuestionTimer) {
      clearTimeout(_quickQuestionTimer)
      _quickQuestionTimer = null
    }
    if (newId && newId !== oldId) {
      const capturedId = newId
      _quickQuestionTimer = setTimeout(() => {
        _quickQuestionTimer = null
        // 确保 recordId 没有在延迟期间再次变化
        if (props.recordId === capturedId) {
          getRecommendQuestions()
        }
      }, 300)
    }
  },
  { immediate: false }
)

defineExpose({ getRecommendQuestions, id: () => props.recordId, stop })

function stop() {
  recommendQuestionRef.value?.stop()
}
</script>

<template>
  <el-popover
    ref="popoverRef"
    :title="$t('qa.guess_u_ask')"
    popper-class="quick-question-popover"
    placement="top-start"
    trigger="click"
    :width="320"
  >
    <el-tooltip effect="dark" :offset="8" :content="$t('qa.ask_again')" placement="top">
      <el-button class="refresh-btn" text :disabled="disabled" @click="retrieveQuestions">
        <el-icon size="16">
          <icon_replace_outlined />
        </el-icon>
      </el-button>
    </el-tooltip>
    <div class="popover-content">
      <RecommendQuestion
        ref="recommendQuestionRef"
        :current-chat="currentChat"
        :record-id="recordId"
        :questions="firstChatQuestions"
        :disabled="disabled"
        :first-chat="firstChat"
        @click-question="quickAsk"
        @stop="onChatStop"
        @loading-over="loadingOver"
      />
    </div>
    <template #reference>
      <el-button class="quick-ask-trigger">
        <el-icon size="15">
          <icon_quick_question />
        </el-icon>
        <span>{{ $t('qa.guess_u_ask') }}</span>
      </el-button>
    </template>
  </el-popover>
</template>

<style lang="less" scoped>
@primary-400: #a78bfa;
@primary-500: #8b5cf6;

.quick-ask-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(
    135deg,
    rgba(139, 92, 246, 0.15) 0%,
    rgba(168, 85, 247, 0.1) 100%
  ) !important;
  border: 1px solid rgba(139, 92, 246, 0.28) !important;
  color: rgba(196, 181, 253, 0.95) !important;
  border-radius: 22px !important;
  padding: 9px 18px !important;
  height: auto !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
  position: relative;
  overflow: hidden;

  // 顶部高光
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 50%;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.06) 0%, transparent 100%);
    pointer-events: none;
    border-radius: 22px 22px 0 0;
  }

  &:hover {
    background: linear-gradient(
      135deg,
      rgba(139, 92, 246, 0.25) 0%,
      rgba(168, 85, 247, 0.18) 100%
    ) !important;
    border-color: rgba(139, 92, 246, 0.45) !important;
    color: #d8b4fe !important;
    transform: translateY(-2px);
    box-shadow:
      0 6px 20px rgba(139, 92, 246, 0.3),
      0 0 0 1px rgba(139, 92, 246, 0.1) inset;
  }

  &:active {
    transform: translateY(0);
    box-shadow: 0 2px 8px rgba(139, 92, 246, 0.2);
  }

  :deep(.ed-icon) {
    transition: transform 0.3s ease;
  }

  &:hover :deep(.ed-icon) {
    transform: scale(1.1);
  }
}
</style>

<style lang="less">
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);

.quick-question-popover {
  padding: 18px !important;
  background: linear-gradient(
    165deg,
    rgba(26, 18, 37, 0.98) 0%,
    rgba(18, 16, 28, 0.99) 100%
  ) !important;
  border: 1px solid rgba(139, 92, 246, 0.25) !important;
  border-radius: 18px !important;
  box-shadow:
    0 16px 48px rgba(0, 0, 0, 0.55),
    0 0 0 1px rgba(139, 92, 246, 0.08) inset,
    0 0 60px rgba(139, 92, 246, 0.08) !important;
  backdrop-filter: blur(20px);
  position: relative;
  overflow: hidden;

  // 顶部高光线
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
      rgba(139, 92, 246, 0.4) 50%,
      transparent 100%
    );
    pointer-events: none;
  }

  // 内部光晕
  &::after {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at center, rgba(139, 92, 246, 0.03) 0%, transparent 50%);
    pointer-events: none;
  }

  .popover-content {
    max-height: 320px;
    margin-top: 10px;
    overflow-y: auto;
    position: relative;
    z-index: 1;

    &::-webkit-scrollbar {
      width: 5px;
    }

    &::-webkit-scrollbar-track {
      background: rgba(139, 92, 246, 0.05);
      border-radius: 3px;
    }

    &::-webkit-scrollbar-thumb {
      background: linear-gradient(180deg, rgba(139, 92, 246, 0.4) 0%, rgba(168, 85, 247, 0.3) 100%);
      border-radius: 3px;

      &:hover {
        background: linear-gradient(
          180deg,
          rgba(139, 92, 246, 0.55) 0%,
          rgba(168, 85, 247, 0.45) 100%
        );
      }
    }
  }

  .ed-popover__title {
    font-size: 15px;
    font-weight: 600;
    margin-bottom: 0;
    padding: 0 6px;
    color: @dark-text !important;
    letter-spacing: 0.3px;
    position: relative;
    z-index: 1;
  }

  .refresh-btn {
    position: absolute;
    cursor: pointer;
    top: 14px;
    right: 14px;
    z-index: 2;
    width: 34px;
    height: 34px;
    border-radius: 10px;
    color: @dark-text-secondary;
    background: rgba(139, 92, 246, 0.1);
    border: 1px solid rgba(139, 92, 246, 0.15);
    transition: all 0.25s ease;
    display: flex;
    align-items: center;
    justify-content: center;

    &:hover {
      background: rgba(139, 92, 246, 0.2);
      border-color: rgba(139, 92, 246, 0.3);
      color: @primary-400;
      transform: rotate(180deg);
      box-shadow: 0 4px 12px rgba(139, 92, 246, 0.2);
    }

    &:active {
      transform: rotate(180deg) scale(0.95);
    }
  }
}
</style>
