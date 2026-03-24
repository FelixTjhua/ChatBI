<script setup lang="ts">
import { ChatInfo, type ChatMessage } from '@/api/chat.ts'
import icon_ai from '@/assets/svg/icon_ai.svg'
import { useAppearanceStoreWithOut } from '@/stores/appearance'

withDefaults(
  defineProps<{
    msg: ChatMessage
    currentChat: ChatInfo
    hideAvatar?: boolean
    logoAssistant?: string
    isRecommend?: boolean
    isError?: boolean
  }>(),
  {
    hideAvatar: false,
    isRecommend: false,
    isError: false,
  }
)
const appearanceStore = useAppearanceStoreWithOut()
</script>

<template>
  <div class="chat-row-container">
    <div class="chat-row" :class="{ 'right-to-left': msg.role === 'user' }">
      <!-- AI头像 - 猜你想问时不显示，正常回复和错误时显示 -->
      <div
        v-if="msg.role === 'assistant' && !hideAvatar && !isRecommend"
        class="ai-avatar"
        :class="{ 'avatar-error': isError }"
      >
        <!-- 优先使用自定义logo，否则使用机器人图标 -->
        <img
          v-if="logoAssistant || appearanceStore.getLogin"
          :src="logoAssistant ? logoAssistant : appearanceStore.getLogin"
          alt=""
          class="avatar-img"
        />
        <el-icon v-else class="robot-icon">
          <icon_ai />
        </el-icon>
      </div>
      <div :class="{ 'row-full': msg.role === 'assistant', 'width-auto': msg.role === 'user' }">
        <slot></slot>
      </div>
    </div>
    <slot name="footer"></slot>
  </div>
</template>

<style scoped lang="less">
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;

.chat-row-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 900px;
  min-width: 0;
  overflow: hidden;

  .chat-row {
    display: flex;
    flex-direction: row;
    align-items: flex-start;
    gap: 14px;
    padding: 32px 0 0;
    width: 100%;
    min-width: 0;
    max-width: 100%;

    &.right-to-left {
      flex-direction: row-reverse;
    }

    .row-full {
      flex: 1;
      min-width: 0;
      max-width: 100%;
      overflow: hidden;
    }

    .width-auto {
      width: auto;
      max-width: 100%;
      min-width: 0;
    }

    // AI头像 - 高级紫色主题
    .ai-avatar {
      width: 36px;
      height: 36px;
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(
        145deg,
        rgba(139, 92, 246, 0.28) 0%,
        rgba(168, 85, 247, 0.18) 100%
      );
      border-radius: 12px;
      border: 1.5px solid rgba(139, 92, 246, 0.35);
      position: relative;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow:
        0 4px 12px rgba(139, 92, 246, 0.15),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);

      // 外发光效果
      &::before {
        content: '';
        position: absolute;
        inset: -3px;
        border-radius: 14px;
        background: linear-gradient(
          135deg,
          rgba(139, 92, 246, 0.2) 0%,
          rgba(168, 85, 247, 0.1) 100%
        );
        opacity: 0;
        transition: opacity 0.3s ease;
        z-index: -1;
        filter: blur(4px);
      }

      // 悬停时的光晕
      &:hover {
        transform: translateY(-1px);
        border-color: rgba(139, 92, 246, 0.5);
        box-shadow:
          0 6px 20px rgba(139, 92, 246, 0.25),
          inset 0 1px 0 rgba(255, 255, 255, 0.12);

        &::before {
          opacity: 1;
        }

        .robot-icon {
          :deep(path) {
            fill: #c4b5fd;
          }
        }
      }

      .avatar-img {
        border-radius: 8px;
        width: 26px;
        height: 26px;
        object-fit: cover;
        transition: transform 0.3s ease;
      }

      &:hover .avatar-img {
        transform: scale(1.05);
      }

      .robot-icon {
        font-size: 22px;
        transition: all 0.3s ease;

        :deep(svg) {
          width: 22px;
          height: 22px;
        }

        :deep(path) {
          fill: @primary-400;
          transition: fill 0.3s ease;
        }
      }

      // 错误状态 - 红色主题
      &.avatar-error {
        background: linear-gradient(
          145deg,
          rgba(239, 68, 68, 0.28) 0%,
          rgba(220, 38, 38, 0.18) 100%
        );
        border-color: rgba(239, 68, 68, 0.4);
        box-shadow:
          0 4px 12px rgba(239, 68, 68, 0.15),
          inset 0 1px 0 rgba(255, 255, 255, 0.08);
        animation: error-pulse 2s ease-in-out infinite;

        &::before {
          background: linear-gradient(
            135deg,
            rgba(239, 68, 68, 0.2) 0%,
            rgba(220, 38, 38, 0.1) 100%
          );
        }

        .robot-icon {
          :deep(path) {
            fill: #f87171;
          }
        }

        &:hover {
          border-color: rgba(239, 68, 68, 0.55);
          box-shadow:
            0 6px 20px rgba(239, 68, 68, 0.25),
            inset 0 1px 0 rgba(255, 255, 255, 0.12);

          .robot-icon {
            :deep(path) {
              fill: #fca5a5;
            }
          }
        }
      }
    }
  }
}

// 错误脉冲动画
@keyframes error-pulse {
  0%,
  100% {
    box-shadow:
      0 4px 12px rgba(239, 68, 68, 0.15),
      inset 0 1px 0 rgba(255, 255, 255, 0.08);
  }
  50% {
    box-shadow:
      0 4px 16px rgba(239, 68, 68, 0.25),
      inset 0 1px 0 rgba(255, 255, 255, 0.08),
      0 0 0 3px rgba(239, 68, 68, 0.1);
  }
}

// 响应式适配
@media (max-width: 768px) {
  .chat-row-container {
    .chat-row {
      gap: 12px;
      padding-top: 18px;

      .ai-avatar {
        width: 32px;
        height: 32px;
        border-radius: 10px;

        .avatar-img {
          width: 22px;
          height: 22px;
          border-radius: 6px;
        }

        .robot-icon {
          font-size: 20px;

          :deep(svg) {
            width: 20px;
            height: 20px;
          }
        }
      }
    }
  }
}

@media (max-width: 480px) {
  .chat-row-container {
    .chat-row {
      gap: 10px;
      padding-top: 16px;

      .ai-avatar {
        width: 30px;
        height: 30px;
        border-radius: 9px;

        .avatar-img {
          width: 20px;
          height: 20px;
        }

        .robot-icon {
          font-size: 18px;

          :deep(svg) {
            width: 18px;
            height: 18px;
          }
        }
      }
    }
  }
}
</style>
