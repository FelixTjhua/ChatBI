<script setup lang="ts">
import { computed } from 'vue'
import MdComponent from '@/views/chat/component/MdComponent.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  answer: string
  ragResults?: any
}>()

// Fix F3-1: 移除死代码 sourceEntries 和 expanded
// 引用来源展示已迁移到 BaseAnswer.vue 的 citation-bar 统一处理

/** 清理回答文本：移除中英文两种来源标注 */
const cleanAnswer = computed(() => {
  if (!props.answer) return ''
  return props.answer
    .replace(/【来源[:：][^】]*】/g, '')
    .replace(/\[Source[:：][^\]]*\]/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
})
</script>

<template>
  <div v-if="answer" class="pdf-answer-block">
    <div class="pdf-answer-content">
      <MdComponent :message="cleanAnswer" />
    </div>
    <!-- 引用来源已由 BaseAnswer.vue 的 citation-bar 统一展示，此处不再重复 -->
  </div>
</template>

<style scoped lang="less">
@text-1: rgba(255, 255, 255, 0.95);
@text-2: rgba(255, 255, 255, 0.75);
@text-3: rgba(255, 255, 255, 0.5);
@blue: #60a5fa;
@purple: #a78bfa;

.pdf-answer-block { display: flex; flex-direction: column; }

.pdf-answer-content {
  padding: 16px 20px;
  background: rgba(139, 92, 246, 0.04);
  border: 1px solid rgba(139, 92, 246, 0.12);
  border-radius: 12px;
  color: @text-1; font-size: 14px; line-height: 1.7;

  :deep(h1), :deep(h2), :deep(h3), :deep(h4) { color: @text-1; margin-top: 16px; margin-bottom: 8px; }
  :deep(ul), :deep(ol) { padding-left: 20px; margin: 8px 0; }
  :deep(li) { margin: 4px 0; }
  :deep(strong) { color: #c4b5fd; }
  :deep(p) { margin: 8px 0; }
}

/* 引用来源盒子 */
.src-box {
  margin-top: 8px;
  background: rgba(59, 130, 246, 0.07);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 10px;
  overflow: hidden;
  &.open { border-color: rgba(59, 130, 246, 0.35); }
}

/* 摘要行 */
.src-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; cursor: pointer; user-select: none;
  transition: background 0.15s;
  &:hover { background: rgba(59, 130, 246, 0.05); }

  .src-icon { font-size: 15px; flex-shrink: 0; }
  .src-label { font-size: 13px; color: @text-1; font-weight: 600; flex: 1; }
  .src-toggle {
    font-size: 12px; color: @blue; font-weight: 500; flex-shrink: 0;
    white-space: nowrap;
  }
}

/* 展开列表 */
.src-list {
  padding: 2px 14px 10px;
  display: flex; flex-direction: column; gap: 4px;
  animation: srcSlide 0.15s ease;
}

.src-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  font-size: 12px;

  .si-idx {
    width: 18px; height: 18px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    background: rgba(59, 130, 246, 0.15); color: @blue;
    font-size: 10px; font-weight: 700; flex-shrink: 0;
  }
  .si-file { color: @text-1; font-weight: 500; }
  .si-tag {
    padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500;
  }
  .si-page { background: rgba(139, 92, 246, 0.12); color: @purple; }
  .si-section { background: rgba(59, 130, 246, 0.1); color: @blue; }
  .si-type { background: rgba(255, 255, 255, 0.06); color: @text-3; }
}

@keyframes srcSlide {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
