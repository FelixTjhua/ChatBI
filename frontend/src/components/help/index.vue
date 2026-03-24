<script lang="ts" setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

const dialogVisible = ref(false)
const { t } = useI18n()

const open = () => {
  dialogVisible.value = true
}

defineExpose({
  open,
})
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    width="480px"
    class="help-dialog-ultimate"
    :show-close="false"
    :modal="true"
    :close-on-click-modal="true"
    :close-on-press-escape="true"
    destroy-on-close
    append-to-body
  >
    <!-- 自定义头部 -->
    <template #header>
      <div class="dialog-header-ultimate">
        <div class="header-content">
          <div class="header-icon">
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          </div>
          <div class="header-text">
            <h2>{{ t('help.title') }}</h2>
            <p>{{ t('help.subtitle') }}</p>
          </div>
        </div>
        <button class="close-btn" @click="dialogVisible = false">
          <span class="close-x">×</span>
        </button>
      </div>
    </template>

    <!-- 内容区域 -->
    <div class="help-content-ultimate">
      <!-- 联系方式卡片 -->
      <div class="contact-cards">
        <!-- 邮箱 -->
        <a
          href="mailto:felixtjhua@gmail.com"
          class="contact-card"
        >
          <div class="card-icon email-icon">
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
              <polyline points="22,6 12,13 2,6" />
            </svg>
          </div>
          <div class="card-content">
            <span class="card-label">{{ t('help.email') }}</span>
            <span class="card-value">felixtjhua@gmail.com</span>
          </div>
        </a>

        <!-- GitHub -->
        <a
          href="https://github.com/FelixTjhua"
          target="_blank"
          class="contact-card"
        >
          <div class="card-icon github-icon">
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path
                d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"
              />
            </svg>
          </div>
          <div class="card-content">
            <span class="card-label">GitHub</span>
            <span class="card-value">FelixTjhua</span>
          </div>
        </a>
      </div>

      <!-- 提示文本 -->
      <div class="help-tip">
        <p>{{ t('help.contact_desc') }}</p>
      </div>
    </div>

    <!-- 底部 -->
    <template #footer>
      <div class="dialog-footer-ultimate">
        <el-button 
          type="primary" 
          class="close-button" 
          @click="dialogVisible = false"
        >
          {{ t('common.close') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style lang="less" scoped>
// 深色主题变量
@dark-bg: #1a1225;
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.85);
@dark-text-muted: rgba(196, 181, 253, 0.6);
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@success: #4ade80;

// 对话框头部
.dialog-header-ultimate {
  padding: 28px 28px 24px;
  background: linear-gradient(
    135deg,
    rgba(168, 85, 247, 0.2) 0%,
    rgba(139, 92, 246, 0.12) 100%
  );
  border-bottom: 1px solid rgba(168, 85, 247, 0.3);
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 16px;

  .header-content {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 14px;

    .header-icon {
      width: 48px;
      height: 48px;
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(168, 85, 247, 0.12));
      border-radius: 14px;
      border: 1.5px solid rgba(168, 85, 247, 0.35);
      color: @primary-400;
      transition: all 0.3s ease;

      &:hover {
        transform: scale(1.08) rotate(5deg);
        border-color: rgba(168, 85, 247, 0.5);
      }
    }

    .header-text {
      flex: 1;

      h2 {
        margin: 0 0 4px;
        font-size: 20px;
        font-weight: 700;
        color: @dark-text;
      }

      p {
        margin: 0;
        font-size: 13px;
        font-weight: 500;
        color: @dark-text-secondary;
      }
    }
  }

  .close-btn {
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(139, 92, 246, 0.12);
    border: 1.5px solid rgba(139, 92, 246, 0.25);
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.3s ease;

    .close-x {
      font-size: 26px;
      font-weight: 300;
      line-height: 1;
      color: rgba(196, 181, 253, 0.7);
      transition: all 0.3s ease;
    }

    &:hover {
      background: rgba(239, 68, 68, 0.15);
      border-color: rgba(239, 68, 68, 0.35);
      transform: scale(1.05) rotate(90deg);

      .close-x {
        color: #ef4444;
      }
    }
  }
}

// 内容区域
.help-content-ultimate {
  padding: 0;

  .contact-cards {
    display: flex;
    flex-direction: column;
    gap: 14px;
    margin-bottom: 20px;

    .contact-card {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 18px 20px;
      background: linear-gradient(
        135deg,
        rgba(139, 92, 246, 0.15) 0%,
        rgba(168, 85, 247, 0.1) 100%
      );
      border: 1.5px solid rgba(139, 92, 246, 0.25);
      border-radius: 12px;
      text-decoration: none;
      transition: all 0.3s ease;
      cursor: pointer;

      &:hover {
        background: linear-gradient(
          135deg,
          rgba(139, 92, 246, 0.22) 0%,
          rgba(168, 85, 247, 0.15) 100%
        );
        border-color: rgba(139, 92, 246, 0.4);
        transform: translateX(4px);
        box-shadow: 0 4px 16px rgba(139, 92, 246, 0.3);
      }

      .card-icon {
        width: 48px;
        height: 48px;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 12px;
        transition: all 0.3s ease;

        &.email-icon {
          background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
          color: white;
          box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
        }

        &.github-icon {
          background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
          color: white;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
      }

      .card-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 4px;

        .card-label {
          font-size: 11px;
          font-weight: 700;
          color: @dark-text-muted;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .card-value {
          font-size: 15px;
          font-weight: 600;
          color: @dark-text;
        }
      }

      &:hover .card-icon {
        transform: scale(1.08);

        &.email-icon {
          box-shadow: 0 6px 16px rgba(124, 58, 237, 0.4);
        }

        &.github-icon {
          box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
        }
      }
    }
  }

  .help-tip {
    padding: 16px;
    background: rgba(139, 92, 246, 0.08);
    border-radius: 10px;
    border: 1.5px solid rgba(139, 92, 246, 0.2);
    text-align: center;

    p {
      margin: 0;
      font-size: 13px;
      color: @dark-text-secondary;
      line-height: 1.6;
    }
  }
}

// 底部
.dialog-footer-ultimate {
  display: flex;
  justify-content: center;
  padding-top: 4px;

  .close-button {
    width: 100%;
    height: 44px;
    font-size: 15px;
    font-weight: 700;
    border-radius: 12px;
    background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%) !important;
    border: none !important;
    color: #fff !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    transition: all 0.3s ease;

    &:hover {
      background: linear-gradient(135deg, #6d28d9 0%, #9333ea 100%) !important;
      transform: translateY(-2px);
      box-shadow: 0 8px 20px rgba(124, 58, 237, 0.4);
    }

    &:active {
      transform: translateY(0);
    }
  }
}

// 响应式
@media (max-width: 600px) {
  .dialog-header-ultimate {
    padding: 20px 20px 18px;

    .header-content {
      .header-icon {
        width: 40px;
        height: 40px;

        svg {
          width: 26px;
          height: 26px;
        }
      }

      .header-text {
        h2 {
          font-size: 18px;
        }

        p {
          font-size: 12px;
        }
      }
    }
  }
}
</style>

<style lang="less">
// 全局样式 - 对话框深色主题
.help-dialog-ultimate,
.help-dialog-ultimate.ed-dialog,
.help-dialog-ultimate.el-dialog,
.el-dialog.help-dialog-ultimate,
.ed-dialog.help-dialog-ultimate {
  background: #1a1225 !important;
  border: 1.5px solid rgba(168, 85, 247, 0.3) !important;
  border-radius: 20px !important;
  box-shadow:
    0 20px 60px rgba(0, 0, 0, 0.6),
    0 0 0 1px rgba(168, 85, 247, 0.15),
    inset 0 1px 0 rgba(168, 85, 247, 0.1) !important;
  overflow: visible;
  max-width: 90vw;
  padding: 0 !important;

  // 隐藏默认头部
  .ed-dialog__header,
  .el-dialog__header {
    display: none !important;
    padding: 0 !important;
    margin: 0 !important;
  }

  .ed-dialog__body,
  .el-dialog__body {
    padding: 28px !important;
    background: #1a1225 !important;
  }

  .ed-dialog__footer,
  .el-dialog__footer {
    padding: 20px 28px 28px !important;
    background: transparent;
    border-top: none;
  }
}

// 遮罩层 - 半透明深色背景
:deep(.ed-overlay):has(+ .help-dialog-ultimate),
:deep(.el-overlay):has(+ .help-dialog-ultimate),
:deep(.ed-overlay-dialog):has(+ .help-dialog-ultimate),
:deep(.el-overlay-dialog):has(+ .help-dialog-ultimate) {
  background-color: rgba(15, 10, 26, 0.75) !important;
  backdrop-filter: blur(6px) !important;
  -webkit-backdrop-filter: blur(6px) !important;
}

// 全局遮罩层样式
.el-overlay:has(+ .help-dialog-ultimate),
.ed-overlay:has(+ .help-dialog-ultimate) {
  background-color: rgba(15, 10, 26, 0.75) !important;
  backdrop-filter: blur(6px) !important;
  -webkit-backdrop-filter: blur(6px) !important;
}

// 响应式适配
@media (max-width: 600px) {
  .help-dialog-ultimate,
  .help-dialog-ultimate.ed-dialog,
  .help-dialog-ultimate.el-dialog {
    border-radius: 18px !important;
    max-width: 95vw;

    .ed-dialog__body,
    .el-dialog__body {
      padding: 20px !important;
    }

    .ed-dialog__footer,
    .el-dialog__footer {
      padding: 16px 20px 20px !important;
    }
  }
}
</style>
