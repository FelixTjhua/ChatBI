<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    description?: string
    showIcon?: boolean
  }>(),
  {
    description: '',
    showIcon: true,
  }
)
</script>

<template>
  <div class="empty-background-modern">
    <div v-if="showIcon" class="empty-icon">
      <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="32" cy="32" r="28" stroke="currentColor" stroke-width="2" opacity="0.2"/>
        <path d="M32 20v24M20 32h24" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        <circle cx="32" cy="32" r="3" fill="currentColor" opacity="0.3"/>
      </svg>
    </div>
    <p v-if="description" class="empty-text">{{ description }}</p>
    <slot></slot>
  </div>
</template>

<style lang="less" scoped>
.empty-background-modern {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  min-height: 300px;
  
  .empty-icon {
    width: 80px;
    height: 80px;
    margin-bottom: 20px;
    color: #8b5cf6;
    opacity: 0.6;
    
    svg {
      width: 100%;
      height: 100%;
    }
  }
  
  .empty-text {
    font-size: 14px;
    color: #94a3b8;
    margin: 0;
    text-align: center;
    line-height: 1.6;
  }
}
</style>
