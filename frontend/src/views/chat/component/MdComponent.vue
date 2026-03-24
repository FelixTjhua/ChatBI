<script setup lang="ts">
import md from '@/utils/markdown.ts'
import 'highlight.js/styles/github-dark.min.css'
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus-secondary'
import { useI18n } from 'vue-i18n'
import { useClipboard } from '@vueuse/core'
import icon_copy_outlined from '@/assets/svg/icon_copy_outlined.svg'

const { t } = useI18n()
const { copy } = useClipboard({ legacy: true })

const props = withDefaults(
  defineProps<{
    message?: string
    showEmpty?: boolean // 是否显示空状态提示
    showCopyButton?: boolean // 是否显示复制按钮
  }>(),
  {
    showEmpty: false,
    showCopyButton: false, // 默认不显示，因为工具栏已有复制按钮
  }
)

const isEmpty = computed(() => {
  return !props.message || props.message.trim().length === 0
})

const renderMd = computed(() => {
  if (isEmpty.value) return ''
  // 安全过滤：移除可能残留的 <think>...</think> 标签（大模型推理过程不应显示在正文中）
  let cleaned = props.message ?? ''
  cleaned = cleaned.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
  if (!cleaned) return ''
  return md.render(cleaned)
})

const copied = ref(false)

function copyContent() {
  if (props.message) {
    copy(props.message).then(() => {
      copied.value = true
      ElMessage.success(t('common.copy_successful'))
      setTimeout(() => {
        copied.value = false
      }, 2000)
    }).catch(() => {
      ElMessage.error(t('qa.copy_failed'))
    })
  }
}
</script>

<template>
  <!-- 空状态 -->
  <div v-if="isEmpty && showEmpty" class="md-empty-state">
    <span class="empty-icon">📝</span>
    <span class="empty-text">{{ t('qa.no_content') }}</span>
  </div>
  <!-- 正常内容 -->
  <div v-else-if="!isEmpty" class="md-content-wrapper">
    <div
      v-dompurify-html="renderMd"
      class="markdown-body md-render-container"
    ></div>
    <!-- 复制按钮 - 优化样式和反馈 -->
    <el-button
      v-if="showCopyButton && !isEmpty"
      class="md-copy-btn"
      :class="{ 'is-copied': copied }"
      @click="copyContent"
    >
      <el-icon size="15">
        <icon_copy_outlined v-if="!copied" />
        <span v-else class="check-icon">✓</span>
      </el-icon>
      <span class="btn-text">{{ copied ? t('qa.copied') : t('qa.copy_content') }}</span>
    </el-button>
  </div>
</template>

<style lang="less">
// 深色主题变量
@dark-bg: #0f0a1a;
@dark-bg-card: rgba(26, 18, 37, 0.9);
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.7);
@primary-400: #a78bfa;
@primary-500: #8b5cf6;

// 空状态样式
.md-empty-state {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(139, 92, 246, 0.06);
  border: 1px dashed @dark-border;
  border-radius: 8px;

  .empty-icon {
    font-size: 16px;
    opacity: 0.7;
  }

  .empty-text {
    font-size: 13px;
    color: @dark-text-muted;
  }
}

// Markdown 内容包装器
.md-content-wrapper {
  position: relative;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;

  // 复制按钮 - 优化布局，始终可见
  .md-copy-btn {
    position: absolute;
    top: 12px;
    right: 12px;
    padding: 8px 14px;
    height: auto;
    min-height: 32px;
    background: rgba(139, 92, 246, 0.15);
    border: 1.5px solid rgba(139, 92, 246, 0.25);
    border-radius: 10px;
    color: @primary-400;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    display: flex;
    align-items: center;
    gap: 6px;
    z-index: 10;
    opacity: 0.85;
    backdrop-filter: blur(8px);
    box-shadow: 0 2px 8px rgba(139, 92, 246, 0.12);

    &:hover {
      opacity: 1;
      background: rgba(139, 92, 246, 0.25);
      border-color: rgba(139, 92, 246, 0.4);
      transform: translateY(-2px);
      box-shadow: 0 6px 16px rgba(139, 92, 246, 0.25);
    }

    &:active {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(139, 92, 246, 0.2);
    }

    // 已复制状态
    &.is-copied {
      background: rgba(34, 197, 94, 0.18);
      border-color: rgba(34, 197, 94, 0.35);
      
      .btn-text {
        color: #4ade80;
      }

      .check-icon {
        color: #4ade80;
        font-size: 16px;
        font-weight: 700;
        animation: checkmark-pop 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
      }

      &:hover {
        background: rgba(34, 197, 94, 0.25);
        border-color: rgba(34, 197, 94, 0.45);
        box-shadow: 0 6px 16px rgba(34, 197, 94, 0.25);
      }
    }

    .btn-text {
      font-size: 13px;
      font-weight: 600;
      color: @primary-400;
      letter-spacing: 0.3px;
      transition: color 0.2s ease;
    }

    .el-icon {
      transition: transform 0.2s ease;
    }

    &:hover .el-icon {
      transform: scale(1.1);
    }
  }

  // 悬停时增强复制按钮显示
  &:hover .md-copy-btn {
    opacity: 1;
  }
}

// 复制成功动画
@keyframes checkmark-pop {
  0% {
    transform: scale(0.5);
    opacity: 0;
  }
  50% {
    transform: scale(1.2);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.md-render-container {
  // 深色主题 Markdown 样式
  background: transparent !important;
  color: @dark-text !important;
  font-size: 15px;
  line-height: 1.7;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-word;
  box-sizing: border-box;
  overflow: hidden;

  .hljs {
    overflow-x: auto;
    padding: 1rem;
    display: block;
    background: rgba(26, 18, 37, 0.8) !important;
    border-radius: 8px;
    border: 1px solid @dark-border;
    max-width: 100%;
  }

  // 标题
  h1,
  h2,
  h3,
  h4,
  h5,
  h6 {
    color: @dark-text !important;
    border-bottom-color: @dark-border !important;
    margin-top: 1.5em;
    margin-bottom: 0.75em;
    font-weight: 600;
    word-break: break-word;
  }

  // 段落
  p {
    color: @dark-text !important;
    margin-bottom: 1em;
    word-break: break-word;
  }

  // 链接
  a {
    color: @primary-400 !important;
    text-decoration: none;
    word-break: break-all;

    &:hover {
      color: @primary-500 !important;
      text-decoration: underline;
    }
  }

  // 代码
  code {
    background: rgba(139, 92, 246, 0.15) !important;
    color: #e9d5ff !important;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.9em;
    word-break: break-all;
  }

  pre {
    background: rgba(26, 18, 37, 0.8) !important;
    border: 1px solid @dark-border;
    border-radius: 8px;
    max-width: 100%;
    overflow-x: auto;

    code {
      background: transparent !important;
      padding: 0;
      word-break: normal;
    }
  }

  // 引用
  blockquote {
    border-left: 3px solid @primary-500 !important;
    background: rgba(139, 92, 246, 0.08) !important;
    color: @dark-text-secondary !important;
    padding: 12px 16px;
    margin: 1em 0;
    border-radius: 0 8px 8px 0;
    word-break: break-word;
  }

  // 列表 - 确保不溢出
  ul,
  ol {
    color: @dark-text !important;
    padding-left: 1.2em;
    margin: 0.5em 0;

    li {
      margin-bottom: 0.5em;
      word-break: break-word;

      &::marker {
        color: @primary-400;
      }
    }
  }

  // 表格
  table {
    border-collapse: collapse;
    width: 100%;
    max-width: 100%;
    margin: 1em 0;
    display: block;
    overflow-x: auto;

    th,
    td {
      border: 1px solid @dark-border !important;
      padding: 10px 14px;
      color: @dark-text !important;
      white-space: nowrap;
    }

    th {
      background: rgba(139, 92, 246, 0.15) !important;
      font-weight: 600;
    }

    tr:nth-child(even) {
      background: rgba(139, 92, 246, 0.05) !important;
    }

    tr:hover {
      background: rgba(139, 92, 246, 0.1) !important;
    }
  }

  // 分割线
  hr {
    border: none;
    border-top: 1px solid @dark-border !important;
    margin: 1.5em 0;
  }

  // 图片
  img {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    border: 1px solid @dark-border;
  }

  // 强调
  strong {
    color: @dark-text !important;
    font-weight: 600;
  }

  em {
    color: @dark-text-secondary !important;
  }
}

// 响应式适配
@media (max-width: 768px) {
  .md-render-container {
    font-size: 14px;
    line-height: 1.6;

    .hljs {
      padding: 0.75rem;
      font-size: 12px;
    }

    h1 {
      font-size: 1.5em;
    }
    h2 {
      font-size: 1.3em;
    }
    h3 {
      font-size: 1.15em;
    }

    table {
      th,
      td {
        padding: 8px 10px;
        font-size: 13px;
      }
    }

    blockquote {
      padding: 10px 14px;
    }
  }

  .md-content-wrapper {
    .md-copy-btn {
      top: 10px;
      right: 10px;
      padding: 7px 12px;
      min-height: 30px;

      .btn-text {
        font-size: 12px;
      }

      .el-icon {
        font-size: 14px;
      }
    }
  }
}

@media (max-width: 480px) {
  .md-render-container {
    font-size: 13px;

    .hljs {
      padding: 0.5rem;
      font-size: 11px;
      border-radius: 6px;
    }

    pre {
      border-radius: 6px;
    }

    table {
      th,
      td {
        padding: 6px 8px;
        font-size: 12px;
      }
    }

    blockquote {
      padding: 8px 12px;
      border-radius: 0 6px 6px 0;
    }
  }

  .md-content-wrapper {
    .md-copy-btn {
      top: 8px;
      right: 8px;
      padding: 6px 10px;
      min-height: 28px;
      border-radius: 8px;

      .btn-text {
        font-size: 11px;
      }

      .el-icon {
        font-size: 13px;
      }
    }
  }
}
</style>
