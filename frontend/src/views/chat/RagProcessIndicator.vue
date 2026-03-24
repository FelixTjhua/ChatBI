<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    stage: 'idle' | 'query' | 'rag' | 'sql' | 'execute' | 'chart' | 'direct' | 'analysis' | 'predict' | 'done' | 'failed'
    ragEnabled?: boolean  // RAG 永远开启，此字段保留用于历史兼容，始终为 true
    isDirectAnswer?: boolean  // 是否为直接回答路径（非SQL）
    intent?: string  // 用户意图，用于决定是否显示分析/预测阶段
    dsType?: string  //  数据源类型，用于适配PDF文档问答路径
    errorMessage?: string  // 错误消息
  }>(),
  {
    ragEnabled: true,  // RAG 永远开启
    isDirectAnswer: false,
    intent: '',
    dsType: '',
    errorMessage: '',
  }
)

// 处理阶段配置 - 根据路径类型显示不同阶段
const stages = computed(() => {
  if (props.isDirectAnswer) {
    // 直接回答路径（非SQL）：查询理解 → RAG知识检索 → LLM生成回答
    return [
      {
        key: 'query',
        icon: '🎯',
        label: t('rag_process.query_understanding'),
        desc: t('rag_process.query_understanding_desc'),
        show: true,
        detail: t('rag_process.detail_query_understanding'),
        ragPhase: 'Q',
      },
      {
        key: 'rag',
        icon: '🔍',
        label: t('rag_process.rag_retrieval'),
        desc: t('rag_process.rag_desc_direct'),
        show: props.ragEnabled,
        detail: t('rag_process.detail_terminology_doc'),
        ragPhase: 'R+A',
      },
      {
        key: 'direct',
        icon: '💬',
        label: t('rag_process.generate_answer'),
        desc: t('rag_process.answer_desc'),
        show: true,
        detail: t('rag_process.detail_llm_text'),
        ragPhase: 'G',
      },
    ]
  }
  // PDF数据源走文档问答路径，不走SQL路径
  // PDF路径增加"上下文增强"步骤，展示完整的RAG三阶段
  // 后端 augment() 对PDF文档片段执行了预算控制和压缩，之前前端未展示
  if (props.dsType?.toLowerCase() === 'pdf') {
    return [
      {
        key: 'query',
        icon: '🎯',
        label: t('rag_process.query_understanding'),
        desc: t('rag_process.query_understanding_desc_pdf'),
        show: true,
        detail: t('rag_process.detail_query_understanding'),
        ragPhase: 'Q',
      },
      {
        key: 'rag',
        icon: '🔍',
        label: t('rag_process.rag_retrieval'),
        desc: t('rag_process.rag_desc_pdf'),
        show: props.ragEnabled,
        detail: t('rag_process.detail_pdf_retrieval_full'),
        ragPhase: 'R',
      },
      {
        key: 'direct',
        icon: '💬',
        label: t('rag_process.generate_answer'),
        desc: t('rag_process.answer_desc_pdf'),
        show: true,
        detail: t('rag_process.detail_llm_text'),
        ragPhase: 'A+G',
      },
    ]
  }
  // 结构化数据源（Database/Excel/CSV）：SQL查询路径
  // 可用知识库：商业术语库(向量检索) + SQL示例库(向量检索) + 自定义提示词(规则注入)
  // 完整流程：查询理解 → RAG知识检索 → SQL生成 → SQL执行 → 图表生成 [→ 数据分析/预测]
  const baseStages = [
    {
      key: 'query',
      icon: '🎯',
      label: t('rag_process.query_understanding'),
      desc: t('rag_process.query_understanding_desc'),
      show: true,
      detail: t('rag_process.detail_query_understanding'),
      ragPhase: 'Q',
    },
    {
      key: 'rag',
      icon: '🔍',
      label: t('rag_process.rag_retrieval'),
      desc: t('rag_process.rag_desc_structured'),
      show: props.ragEnabled,
      detail: t('rag_process.detail_structured_retrieval'),
      ragPhase: 'R+A',
    },
    {
      key: 'sql',
      icon: '🧠',
      label: t('rag_process.sql_generate'),
      desc: t('rag_process.sql_desc'),
      show: true,
      detail: t('rag_process.detail_sql_generate'),
      ragPhase: 'G',
    },
    {
      key: 'execute',
      icon: '⚡',
      label: t('rag_process.execute_query'),
      desc: t('rag_process.execute_desc'),
      show: true,
      detail: t('rag_process.detail_sql_execute'),
      ragPhase: 'G',
    },
    {
      key: 'chart',
      icon: '📊',
      label: t('rag_process.generate_chart'),
      desc: t('rag_process.chart_desc'),
      show: true,
      detail: t('rag_process.detail_chart_generate'),
      ragPhase: 'G',
    },
  ]
  
  // analysis意图：图表后自动内联执行数据分析
  const analysisIntents = ['analysis', 'statistical_analysis', 'comparison_analysis', 'trend_analysis']
  if (analysisIntents.includes(props.intent)) {
    baseStages.push({
      key: 'analysis',
      icon: '📈',
      label: t('rag_process.data_analysis'),
      desc: t('rag_process.analysis_desc'),
      show: true,
      detail: t('rag_process.detail_analysis'),
      ragPhase: 'G',
    })
  }
  // prediction意图：图表后自动内联执行数据预测
  if (props.intent === 'prediction') {
    baseStages.push({
      key: 'predict',
      icon: '🔮',
      label: t('rag_process.data_prediction'),
      desc: t('rag_process.prediction_desc'),
      show: true,
      detail: t('rag_process.detail_prediction'),
      ragPhase: 'G',
    })
  }
  
  return baseStages
})

const visibleStages = computed(() => stages.value.filter((s) => s.show))

const currentStageIndex = computed(() => {
  const idx = visibleStages.value.findIndex((s) => s.key === props.stage)
  return idx >= 0 ? idx : -1
})

// 记录失败前最后一个活跃阶段的索引
const _prevValidIndex = ref(0)
watch(() => currentStageIndex.value, (newIdx) => {
  if (newIdx >= 0) _prevValidIndex.value = newIdx
}, { immediate: true })

const lastActiveStageIndex = computed(() => {
  if (props.stage === 'failed') {
    // 失败时使用上一次有效的阶段索引（而非 currentStageIndex 的 -1）
    return _prevValidIndex.value
  }
  return currentStageIndex.value
})

const getStageStatus = (index: number) => {
  if (props.stage === 'done') return 'completed'
  if (props.stage === 'failed') {
    // When failed, mark current stage as failed and previous as completed
    // 使用 lastActiveStageIndex 替代 currentStageIndex
    // 当 currentStageIndex 为 -1 时，至少将第一个阶段标记为 failed
    const failIdx = lastActiveStageIndex.value
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
  <div v-if="stage !== 'idle'" class="rag-process-indicator" :class="{ 'stage-done': stage === 'done' }">
    <div class="process-header">
      <div class="header-glow"></div>
      <span class="header-icon">{{ stage === 'failed' ? '❌' : stage === 'done' ? '✅' : '⚙️' }}</span>
      <span class="header-text">{{ stage === 'failed' ? t('rag_process.process_failed') : stage === 'done' ? t('rag_process.process_done') : t('rag_process.processing') }}</span>
      <!-- RAG 模式标识 -->
      <span class="rag-mode-badge" :class="{ enabled: ragEnabled }">
        {{ ragEnabled ? t('thinking.rag_mode_enhanced') : t('thinking.rag_mode_direct') }}
      </span>
    </div>

    <div class="process-stages">
      <div
        v-for="(stageItem, index) in visibleStages"
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
          <!-- 显示详细信息 -->
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

        <!-- 连接线 -->
        <div v-if="index < visibleStages.length - 1" class="stage-connector">
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

.rag-process-indicator {
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

  &.stage-done {
    animation: fadeOutShrink 0.8s ease-out 0.5s forwards;
  }

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

  .stage-desc {
    font-size: 12px;
    color: rgba(196, 181, 253, 0.75);
    font-weight: 500;
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

@keyframes fadeOutShrink {
  0% {
    opacity: 1;
    max-height: 500px;
    margin-top: 0;
    margin-bottom: 0;
    padding: 20px 24px;
  }
  60% {
    opacity: 0;
    max-height: 500px;
    padding: 20px 24px;
  }
  100% {
    opacity: 0;
    max-height: 0;
    padding: 0 24px;
    margin-top: 0;
    margin-bottom: 0;
    overflow: hidden;
  }
}

// 响应式
@media (max-width: 480px) {
  .rag-process-indicator {
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
