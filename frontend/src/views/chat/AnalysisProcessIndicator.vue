<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    stage: 'idle' | 'query' | 'rag' | 'augment' | 'loading' | 'analyzing' | 'generating' | 'chart' | 'done' | 'failed'
    errorMessage?: string
  }>(),
  {
    stage: 'idle',
    errorMessage: '',
  }
)

const stages = computed(() => [
  {
    key: 'query',
    icon: '🎯',
    label: t('analysis_process.query_understanding'),
    desc: t('analysis_process.query_understanding_desc'),
    detail: t('analysis_process.detail_query_understanding'),
    show: true,
    ragPhase: 'Q',
  },
  {
    key: 'rag',
    icon: '🔍',
    label: t('analysis_process.rag_retrieve'),
    desc: t('analysis_process.rag_retrieve_desc'),
    detail: t('rag.terminology') + ' + ' + t('rag.sql_examples'),
    show: true,
    ragPhase: 'R',
  },
  {
    key: 'augment',
    icon: '',
    label: t('thinking.step_context_augmentation'),
    desc: t('analysis_process.context_augmentation_desc'),
    detail: t('analysis_process.context_augmentation_detail'),
    show: true,
    ragPhase: 'A',
  },
  {
    key: 'analyzing',
    icon: '🧠',
    label: t('analysis_process.ai_analyze'),
    desc: t('analysis_process.ai_analyze_desc'),
    detail: t('thinking.rag_detail_deep_analysis'),
    show: true,
    ragPhase: 'G',
  },
])

const currentStageIndex = computed(() => {
  if (props.stage === 'query') return 0
  if (props.stage === 'rag') return 1
  // 新增上下文增强阶段
  if (props.stage === 'augment') return 2
  if (['loading', 'analyzing'].includes(props.stage)) return 3
  if (props.stage === 'generating') return 3
  // 'chart' 阶段（加载图表数据）映射到最后一个阶段
  if (props.stage === 'chart') return 3
  // 'failed' 状态回退到最后一个已知阶段
  if (props.stage === 'failed') return 3
  return -1
})

const getStageStatus = (index: number) => {
  if (props.stage === 'done') return 'completed'
  if (props.stage === 'failed') {
    // 当 currentStageIndex 为 -1 时，至少将第一个阶段标记为 failed
    const failIdx = Math.max(currentStageIndex.value, 0)
    if (index < failIdx) return 'completed'
    if (index === failIdx) return 'failed'
    return 'pending'
  }
  if (index < currentStageIndex.value) return 'completed'
  if (index === currentStageIndex.value) return 'active'
  return 'pending'
}
</script>

<template>
  <div v-if="stage !== 'idle' && stage !== 'done'" class="analysis-process-indicator">
    <div class="process-header">
      <div class="header-glow"></div>
      <span class="header-icon">{{ stage === 'failed' ? '❌' : '📈' }}</span>
      <span class="header-text">{{ stage === 'failed' ? t('analysis_process.process_failed') : t('analysis_process.processing') }}</span>
      <span class="rag-mode-badge enabled">
        {{ t('thinking.rag_mode_enhanced') }}
      </span>
    </div>

    <div class="process-stages">
      <div
        v-for="(stageItem, index) in stages"
        :key="stageItem.key"
        class="stage-item"
        :class="[`status-${getStageStatus(index)}`]"
      >
        <div class="stage-indicator">
          <div class="indicator-ring">
            <div class="ring-inner"></div>
          </div>
          <span v-if="getStageStatus(index) !== 'failed'" class="stage-icon">{{ stageItem.icon }}</span>
          <span v-else class="stage-icon failed-icon">❌</span>
        </div>

        <div class="stage-content">
          <span class="stage-label">{{ stageItem.label }}</span>
          <span v-if="stageItem.ragPhase" class="rag-phase-tag">{{ stageItem.ragPhase }}</span>
          <span class="stage-desc">{{ stageItem.desc }}</span>
          <span v-if="getStageStatus(index) === 'active'" class="stage-detail">
            {{ stageItem.detail }}
          </span>
        </div>

        <div v-if="getStageStatus(index) === 'active'" class="stage-loader">
          <span></span><span></span><span></span>
        </div>
        <div v-else-if="getStageStatus(index) === 'completed'" class="stage-check">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <path d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <div v-else-if="getStageStatus(index) === 'failed'" class="stage-fail">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
        </div>

        <div v-if="index < stages.length - 1" class="stage-connector">
          <div
            class="connector-line"
            :class="{ filled: getStageStatus(index) === 'completed', 'failed-line': getStageStatus(index) === 'failed' }"
          ></div>
        </div>
      </div>
    </div>

    <!-- 错误消息展示 -->
    <div v-if="stage === 'failed' && errorMessage" class="process-error">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <span>{{ errorMessage }}</span>
    </div>
  </div>
</template>

<style scoped lang="less">
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@success-400: #4ade80;
@success-500: #22c55e;

.analysis-process-indicator {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 24px;
  background: linear-gradient(145deg, rgba(139, 92, 246, 0.08) 0%, rgba(88, 28, 135, 0.04) 100%);
  border: 1px solid rgba(139, 92, 246, 0.15);
  border-radius: 20px;
  position: relative;
  overflow: hidden;
  animation: fadeIn 0.4s ease-out;
  margin-top: 12px;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, @primary-500, transparent);
    animation: shimmer 2s ease-in-out infinite;
  }
}

.process-header {
  display: flex;
  align-items: center;
  gap: 10px;
  position: relative;

  .header-glow {
    position: absolute;
    left: -10px;
    top: 50%;
    transform: translateY(-50%);
    width: 40px;
    height: 40px;
    background: radial-gradient(circle, rgba(139, 92, 246, 0.3) 0%, transparent 70%);
    animation: pulse-glow 2s ease-in-out infinite;
  }

  .header-icon {
    font-size: 18px;
    z-index: 1;
    animation: sparkle 1.5s ease-in-out infinite;
  }

  .header-text {
    font-size: 14px;
    font-weight: 600;
    color: rgba(196, 181, 253, 0.9);
    letter-spacing: 0.5px;
    z-index: 1;
    flex: 1;
  }

  .rag-mode-badge {
    font-size: 10px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 6px;
    background: rgba(139, 92, 246, 0.2);
    color: rgba(196, 181, 253, 0.8);
    border: 1px solid rgba(139, 92, 246, 0.3);
    letter-spacing: 1px;
    z-index: 1;

    &.enabled {
      background: linear-gradient(135deg, rgba(34, 197, 94, 0.2) 0%, rgba(74, 222, 128, 0.1) 100%);
      color: @success-400;
      border-color: rgba(34, 197, 94, 0.4);
      box-shadow: 0 0 12px rgba(34, 197, 94, 0.2);
    }
  }
}

.process-stages {
  display: flex;
  flex-direction: column;
  gap: 0;
  position: relative;
}

.stage-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 14px;
  position: relative;
  transition: all 0.3s ease;

  &.status-pending {
    opacity: 0.4;

    .stage-indicator {
      .indicator-ring {
        border-color: rgba(139, 92, 246, 0.2);
      }
      .stage-icon {
        filter: grayscale(0.8);
      }
    }
  }

  &.status-active {
    background: rgba(139, 92, 246, 0.12);

    .stage-indicator {
      .indicator-ring {
        border-color: @primary-500;
        animation: ring-pulse 1.5s ease-in-out infinite;

        .ring-inner {
          background: @primary-500;
          animation: inner-pulse 1.5s ease-in-out infinite;
        }
      }
    }

    .stage-label {
      color: rgba(255, 255, 255, 0.95);
    }
  }

  &.status-completed {
    .stage-indicator {
      .indicator-ring {
        border-color: @success-500;

        .ring-inner {
          background: @success-500;
        }
      }
    }

    .stage-label {
      color: rgba(196, 181, 253, 0.8);
    }
  }

  &.status-failed {
    background: rgba(248, 113, 113, 0.08);

    .stage-indicator {
      .indicator-ring {
        border-color: #f87171;

        .ring-inner {
          background: #f87171;
        }
      }
    }

    .stage-label {
      color: #f87171;
    }

    .stage-desc {
      color: rgba(248, 113, 113, 0.7);
    }
  }
}

.stage-fail {
  width: 24px;
  height: 24px;
  color: #f87171;
  animation: check-pop 0.3s ease-out;

  svg {
    width: 100%;
    height: 100%;
  }
}

.failed-icon {
  filter: none !important;
}

.process-error {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  background: rgba(248, 113, 113, 0.08);
  border: 1px solid rgba(248, 113, 113, 0.25);
  border-radius: 12px;
  color: #fca5a5;
  font-size: 13px;
  line-height: 1.5;
  animation: fadeIn 0.4s ease-out;

  svg {
    width: 20px;
    height: 20px;
    flex-shrink: 0;
    color: #f87171;
    margin-top: 1px;
  }
}
.stage-indicator {
  position: relative;
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;

  .indicator-ring {
    position: absolute;
    inset: 0;
    border: 2px solid rgba(139, 92, 246, 0.3);
    border-radius: 50%;
    transition: all 0.3s ease;

    .ring-inner {
      position: absolute;
      inset: 6px;
      background: rgba(139, 92, 246, 0.2);
      border-radius: 50%;
      transition: all 0.3s ease;
    }
  }

  .stage-icon {
    font-size: 20px;
    z-index: 1;
    transition: all 0.3s ease;
  }
}

.stage-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;

  .stage-label {
    font-size: 14px;
    font-weight: 500;
    color: rgba(196, 181, 253, 0.7);
    transition: color 0.3s ease;
  }

  .stage-desc {
    font-size: 12px;
    color: rgba(196, 181, 253, 0.75);
    font-weight: 500;
  }

  .rag-phase-tag {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 9px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 4px;
    background: rgba(139, 92, 246, 0.2);
    color: @primary-400;
    border: 1px solid rgba(139, 92, 246, 0.3);
    letter-spacing: 0.5px;
    line-height: 1.4;
    vertical-align: middle;
  }

  .stage-detail {
    font-size: 11px;
    color: @primary-400;
    font-weight: 500;
    padding: 2px 8px;
    background: rgba(139, 92, 246, 0.15);
    border-radius: 4px;
    display: inline-block;
    width: fit-content;
    margin-top: 2px;
    animation: fadeIn 0.3s ease;
  }
}

.stage-loader {
  display: flex;
  gap: 4px;

  span {
    width: 6px;
    height: 6px;
    background: @primary-400;
    border-radius: 50%;
    animation: loader-bounce 1.4s ease-in-out infinite;

    &:nth-child(1) {
      animation-delay: 0s;
    }
    &:nth-child(2) {
      animation-delay: 0.16s;
    }
    &:nth-child(3) {
      animation-delay: 0.32s;
    }
  }
}

.stage-check {
  width: 24px;
  height: 24px;
  color: @success-500;
  animation: check-pop 0.3s ease-out;

  svg {
    width: 100%;
    height: 100%;
  }
}

.stage-connector {
  position: absolute;
  left: 37px;
  top: 58px;
  width: 2px;
  height: 28px;

  .connector-line {
    width: 100%;
    height: 100%;
    background: rgba(139, 92, 246, 0.2);
    border-radius: 1px;
    transition: background 0.3s ease;

    &.filled {
      background: linear-gradient(180deg, @success-500 0%, @primary-500 100%);
    }

    &.failed-line {
      background: linear-gradient(180deg, #f87171 0%, rgba(248, 113, 113, 0.3) 100%);
    }
  }
}

// 动画
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes shimmer {
  0%,
  100% {
    opacity: 0.3;
  }
  50% {
    opacity: 1;
  }
}

@keyframes pulse-glow {
  0%,
  100% {
    transform: translateY(-50%) scale(1);
    opacity: 0.5;
  }
  50% {
    transform: translateY(-50%) scale(1.2);
    opacity: 0.8;
  }
}

@keyframes sparkle {
  0%,
  100% {
    transform: scale(1) rotate(0deg);
  }
  50% {
    transform: scale(1.1) rotate(5deg);
  }
}

@keyframes ring-pulse {
  0%,
  100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(139, 92, 246, 0.4);
  }
  50% {
    transform: scale(1.05);
    box-shadow: 0 0 0 8px rgba(139, 92, 246, 0);
  }
}

@keyframes inner-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.1);
    opacity: 1;
  }
}

@keyframes loader-bounce {
  0%,
  80%,
  100% {
    transform: scale(0.6);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes check-pop {
  0% {
    transform: scale(0);
  }
  50% {
    transform: scale(1.2);
  }
  100% {
    transform: scale(1);
  }
}

// 响应式
@media (max-width: 480px) {
  .analysis-process-indicator {
    padding: 16px 18px;
    border-radius: 16px;
  }

  .stage-item {
    padding: 12px 14px;
    gap: 12px;
  }

  .stage-indicator {
    width: 38px;
    height: 38px;

    .stage-icon {
      font-size: 18px;
    }
  }

  .stage-content {
    .stage-label {
      font-size: 13px;
    }
    .stage-desc {
      font-size: 11px;
    }
  }

  .stage-connector {
    left: 33px;
    top: 52px;
    height: 24px;
  }
}

</style>
