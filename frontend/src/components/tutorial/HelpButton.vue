<template>
  <Teleport to="body">
    <!-- 高级帮助按钮 - 在智能对话页面显示 -->
    <div v-if="isVisible" class="help-button-wrapper">
      <div class="help-btn-pulse"></div>
      <div class="help-btn" @click="openTutorial">
        <div class="btn-icon">
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        </div>
        <span class="btn-tooltip">{{ t('tutorial.help') }}</span>
      </div>
    </div>

    <TutorialGuide ref="tutorialRef" />
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { useCache } from '@/utils/useCache'
import { useUserStore } from '@/stores/user'
import TutorialGuide from './TutorialGuide.vue'

const { t } = useI18n()
const { wsCache } = useCache()
const route = useRoute()
const userStore = useUserStore()
const tutorialRef = ref()

let checkTimeoutId: ReturnType<typeof setTimeout> | null = null

// 监听聊天页面是否有对话内容
const hasChatContent = ref(false)

// 监听自定义事件来更新聊天内容状态
const updateChatContentStatus = (event: CustomEvent) => {
  hasChatContent.value = event.detail?.hasContent || false
}

onMounted(() => {
  window.addEventListener('chatContentChange', updateChatContentStatus as EventListener)
})

onUnmounted(() => {
  window.removeEventListener('chatContentChange', updateChatContentStatus as EventListener)
})

// 只在智能对话首页（欢迎页面，没有对话内容时）显示帮助按钮
const isVisible = computed(() => {
  // 只在 /chat/index 或 /chat 路径显示
  const isExactChatIndex = route.path === '/chat/index' || route.path === '/chat'
  // 并且没有对话内容时才显示
  return isExactChatIndex && !hasChatContent.value
})

const openTutorial = () => {
  // 每次点击都清除"不再显示"状态，确保教程能打开
  wsCache.delete('tutorial.dontShow')
  tutorialRef.value?.show()
}

// 首次登录后自动显示教程（只显示一次）
const checkAndShowTutorial = () => {
  // 只在首次登录时自动显示
  if (isVisible.value && userStore.getIsFirstLogin && tutorialRef.value?.shouldShow()) {
    tutorialRef.value?.show()
    // 清除首次登录标记，确保不会再次自动显示
    userStore.clearFirstLoginFlag()
  }
}

// 监听路由变化，当进入智能对话页面时检查是否需要显示教程
watch(isVisible, (newVal) => {
  if (newVal) {
    // 清除之前的定时器
    if (checkTimeoutId) {
      clearTimeout(checkTimeoutId)
      checkTimeoutId = null
    }
    // 只在首次登录时自动显示
    if (userStore.getIsFirstLogin) {
      checkTimeoutId = setTimeout(checkAndShowTutorial, 1000)
    }
  }
})

onMounted(() => {
  // 延迟检查，确保组件完全加载
  // 只在首次登录时自动显示
  if (userStore.getIsFirstLogin) {
    if (checkTimeoutId) {
      clearTimeout(checkTimeoutId)
      checkTimeoutId = null
    }
    checkTimeoutId = setTimeout(checkAndShowTutorial, 1500)
  }
})

onUnmounted(() => {
  // 清理定时器
  if (checkTimeoutId) {
    clearTimeout(checkTimeoutId)
    checkTimeoutId = null
  }
})

defineExpose({ openTutorial })
</script>

<style lang="less" scoped>
.help-button-wrapper {
  position: fixed;
  bottom: 28px;
  right: 28px;
  z-index: 1999;
}

// 脉冲动画背景
.help-btn-pulse {
  position: absolute;
  inset: -6px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(124, 58, 237, 0.3) 0%, rgba(139, 92, 246, 0.2) 100%);
  animation: pulse-ring 2.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  pointer-events: none;
}

.help-btn {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background: linear-gradient(145deg, #7c3aed 0%, #6d28d9 50%, #5b21b6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow:
    0 8px 24px rgba(124, 58, 237, 0.4),
    0 2px 8px rgba(124, 58, 237, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.15),
    inset 0 -1px 0 rgba(0, 0, 0, 0.1);
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: visible;
  border: 1px solid rgba(255, 255, 255, 0.1);

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 18px;
    background: linear-gradient(145deg, rgba(255, 255, 255, 0.2) 0%, transparent 50%);
    pointer-events: none;
  }

  .btn-icon {
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.3s ease;
  }

  .btn-tooltip {
    position: absolute;
    right: calc(100% + 14px);
    top: 50%;
    transform: translateY(-50%) translateX(8px);
    padding: 10px 16px;
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
    color: white;
    font-size: 13px;
    font-weight: 500;
    border-radius: 10px;
    white-space: nowrap;
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow:
      0 4px 16px rgba(0, 0, 0, 0.2),
      0 2px 6px rgba(0, 0, 0, 0.1);
    pointer-events: none;
    border: 1px solid rgba(255, 255, 255, 0.1);

    &::after {
      content: '';
      position: absolute;
      right: -6px;
      top: 50%;
      transform: translateY(-50%);
      border: 6px solid transparent;
      border-left-color: #312e81;
    }
  }

  &:hover {
    transform: scale(1.08) translateY(-2px);
    box-shadow:
      0 12px 32px rgba(124, 58, 237, 0.5),
      0 4px 12px rgba(124, 58, 237, 0.3),
      inset 0 1px 0 rgba(255, 255, 255, 0.2),
      inset 0 -1px 0 rgba(0, 0, 0, 0.1);
    border-color: rgba(255, 255, 255, 0.2);

    .btn-icon {
      transform: rotate(15deg) scale(1.1);
    }

    .btn-tooltip {
      opacity: 1;
      visibility: visible;
      transform: translateY(-50%) translateX(0);
    }
  }

  &:active {
    transform: scale(0.95);
    box-shadow:
      0 4px 16px rgba(124, 58, 237, 0.4),
      0 2px 6px rgba(124, 58, 237, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.15);
  }
}

@keyframes pulse-ring {
  0% {
    transform: scale(1);
    opacity: 0.6;
  }
  50% {
    transform: scale(1.15);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 0;
  }
}

// 响应式 - 小屏幕
@media (max-width: 768px) {
  .help-button-wrapper {
    bottom: 20px;
    right: 20px;
  }

  .help-btn {
    width: 50px;
    height: 50px;
    border-radius: 16px;

    &::before {
      border-radius: 16px;
    }

    .btn-icon svg {
      width: 20px;
      height: 20px;
    }

    .btn-tooltip {
      display: none;
    }
  }

  .help-btn-pulse {
    inset: -4px;
  }
}

// 响应式 - 超小屏幕
@media (max-width: 480px) {
  .help-button-wrapper {
    bottom: 16px;
    right: 16px;
  }

  .help-btn {
    width: 46px;
    height: 46px;
    border-radius: 14px;

    &::before {
      border-radius: 14px;
    }

    .btn-icon svg {
      width: 18px;
      height: 18px;
    }
  }

  .help-btn-pulse {
    inset: -3px;
  }
}

// 响应式 - 极小屏幕
@media (max-width: 360px) {
  .help-button-wrapper {
    bottom: 12px;
    right: 12px;
  }

  .help-btn {
    width: 42px;
    height: 42px;
    border-radius: 12px;
    box-shadow:
      0 6px 18px rgba(124, 58, 237, 0.35),
      0 2px 6px rgba(124, 58, 237, 0.15),
      inset 0 1px 0 rgba(255, 255, 255, 0.15);

    &::before {
      border-radius: 12px;
    }

    .btn-icon svg {
      width: 16px;
      height: 16px;
    }
  }

  .help-btn-pulse {
    inset: -2px;
  }
}

// 横屏模式 - 避免遮挡内容
@media (max-height: 500px) and (orientation: landscape) {
  .help-button-wrapper {
    bottom: 12px;
    right: 12px;
  }

  .help-btn {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    opacity: 0.85;

    &::before {
      border-radius: 10px;
    }

    .btn-icon svg {
      width: 16px;
      height: 16px;
    }

    &:hover {
      opacity: 1;
    }
  }

  .help-btn-pulse {
    display: none;
  }
}

// 安全区域适配 (iPhone X 等设备)
@supports (padding-bottom: env(safe-area-inset-bottom)) {
  .help-button-wrapper {
    bottom: calc(28px + env(safe-area-inset-bottom));
    right: calc(28px + env(safe-area-inset-right));
  }

  @media (max-width: 768px) {
    .help-button-wrapper {
      bottom: calc(20px + env(safe-area-inset-bottom));
      right: calc(20px + env(safe-area-inset-right));
    }
  }

  @media (max-width: 480px) {
    .help-button-wrapper {
      bottom: calc(16px + env(safe-area-inset-bottom));
      right: calc(16px + env(safe-area-inset-right));
    }
  }
}
</style>
