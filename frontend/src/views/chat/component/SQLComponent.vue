<script setup lang="ts">
import 'highlight.js/styles/github-dark.min.css'
import hljs from 'highlight.js'

defineProps<{
  sql: string
}>()
</script>

<template>
  <pre class="hljs sql-block">
    <div
      v-dompurify-html="hljs.highlight(sql, { language: 'sql', ignoreIllegals: true }).value"
    ></div>
  </pre>
</template>

<style lang="less">
// 深色主题变量
@dark-bg-card: rgba(26, 18, 37, 0.9);
@dark-border: rgba(139, 92, 246, 0.2);
@primary-400: #a78bfa;

.sql-block.hljs {
  overflow-x: auto;
  padding: 1.25rem;
  display: block;
  background: linear-gradient(
    145deg,
    rgba(26, 18, 37, 0.92) 0%,
    rgba(20, 14, 32, 0.95) 100%
  ) !important;
  border: 1px solid @dark-border;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.7;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  position: relative;

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
      rgba(139, 92, 246, 0.25) 50%,
      transparent 100%
    );
    pointer-events: none;
  }

  // SQL 语法高亮颜色调整 - 更鲜艳
  .hljs-keyword {
    color: #c084fc !important;
    font-weight: 600;
  }

  .hljs-string {
    color: #86efac !important;
  }

  .hljs-number {
    color: #fbbf24 !important;
  }

  .hljs-comment {
    color: rgba(196, 181, 253, 0.7) !important;
    font-weight: 500;
    font-style: italic;
  }

  .hljs-built_in {
    color: #67e8f9 !important;
  }

  .hljs-title {
    color: @primary-400 !important;
  }

  .hljs-params {
    color: rgba(255, 255, 255, 0.9) !important;
  }

  .hljs-operator {
    color: #f472b6 !important;
  }

  .hljs-function {
    color: #60a5fa !important;
  }
}

// 响应式适配
@media (max-width: 768px) {
  .sql-block.hljs {
    padding: 1rem;
    font-size: 12px;
    border-radius: 10px;
    line-height: 1.6;
  }
}

@media (max-width: 480px) {
  .sql-block.hljs {
    padding: 0.75rem;
    font-size: 11px;
    border-radius: 8px;
  }
}
</style>
