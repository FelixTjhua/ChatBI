<template>
  <el-dialog
    v-model="visible"
    :title="''"
    width="780px"
    :close-on-click-modal="false"
    custom-class="tutorial-dialog-inner"
    class="tutorial-dialog"
    destroy-on-close
    :show-close="false"
    :modal-class="'tutorial-dialog-overlay'"
  >
    <div class="tutorial-wrapper">
      <!-- 顶部区域 -->
      <div class="tutorial-header">
        <div class="header-left">
          <div class="logo-badge">
            <div class="logo-glow-effect"></div>
            <img 
              src="@/assets/chatbi-logo-new.svg?url" 
              alt="ChatBI" 
              class="logo-badge-img"
            />
          </div>
          <div class="header-text">
            <h2>{{ t('tutorial.welcome') }}</h2>
            <p>{{ t('tutorial.subtitle') }}</p>
          </div>
        </div>
        <button class="close-btn" @click="visible = false">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <!-- 进度条 -->
      <div class="progress-section">
        <div class="progress-info">
          <span class="progress-label">{{ t('tutorial.progress') }}</span>
          <span class="progress-value">{{ currentStep + 1 }} / {{ steps.length }}</span>
        </div>
        <div class="progress-track">
          <div
            class="progress-fill"
            :style="{ width: ((currentStep + 1) / steps.length) * 100 + '%' }"
          ></div>
        </div>
      </div>

      <!-- 主内容区域 -->
      <div class="tutorial-content">
        <transition name="slide-fade" mode="out-in">
          <div :key="currentStep" class="step-container">
            <!-- 左侧：步骤图标和信息 -->
            <div class="step-sidebar">
              <div class="step-visual">
                <div class="visual-rings">
                  <div class="ring ring-1"></div>
                  <div class="ring ring-2"></div>
                  <div class="ring ring-3"></div>
                </div>
                <div class="visual-icon">
                  <component :is="steps[currentStep].icon" />
                </div>
              </div>

              <div class="step-badge">
                <span class="badge-step">STEP {{ currentStep + 1 }}</span>
              </div>

              <h3 class="step-title">{{ t(steps[currentStep].titleKey) }}</h3>
              <p class="step-desc">{{ t(steps[currentStep].descKey) }}</p>
            </div>

            <!-- 右侧：操作指南 -->
            <div class="step-main">
              <div class="guide-header">
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
                <span>{{ t('tutorial.operation_guide') }}</span>
              </div>

              <div class="guide-list">
                <div
                  v-for="(detail, idx) in steps[currentStep].details"
                  :key="idx"
                  class="guide-item"
                  :class="{ animate: true }"
                  :style="{ animationDelay: idx * 0.12 + 's' }"
                >
                  <div class="item-number">
                    <span>{{ idx + 1 }}</span>
                    <div
                      v-if="idx < steps[currentStep].details.length - 1"
                      class="number-line"
                    ></div>
                  </div>
                  <div class="item-content">
                    <h4>{{ t(detail.titleKey) }}</h4>
                    <p>{{ t(detail.descKey) }}</p>
                  </div>
                </div>
              </div>

              <!-- 提示卡片 -->
              <div v-if="steps[currentStep].tipKey" class="tip-card">
                <div class="tip-icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                    <path
                      d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z"
                    />
                    <path d="M9 21h6M10 21v-1h4v1" />
                  </svg>
                </div>
                <div class="tip-content">
                  <span class="tip-label">{{ t('tutorial.pro_tip') }}</span>
                  <p>{{ t(steps[currentStep].tipKey) }}</p>
                </div>
              </div>
            </div>
          </div>
        </transition>
      </div>

      <!-- 底部控制区域 -->
      <div class="tutorial-footer">
        <div class="footer-left">
          <label class="checkbox-wrapper">
            <input v-model="dontShowAgain" type="checkbox" />
            <span class="checkbox-box">
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="3"
              >
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </span>
            <span class="checkbox-label">{{
              t('tutorial.dont_show_again')
            }}</span>
          </label>
        </div>

        <div class="footer-center">
          <div class="step-indicators">
            <button
              v-for="(_, index) in steps"
              :key="index"
              class="indicator"
              :class="{
                active: currentStep === index,
                completed: currentStep > index,
              }"
              @click="currentStep = index"
            >
              <span class="indicator-inner"></span>
            </button>
          </div>
        </div>

        <div class="footer-right">
          <button
            class="btn btn-secondary"
            :class="{ 'btn-invisible': currentStep === 0 }"
            :disabled="currentStep === 0"
            @click="currentStep > 0 && currentStep--"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path d="M15 18l-6-6 6-6" />
            </svg>
            <span>{{ t('tutorial.prev') }}</span>
          </button>

          <button
            v-if="currentStep < steps.length - 1"
            class="btn btn-primary"
            @click="currentStep++"
          >
            <span>{{ t('tutorial.next') }}</span>
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path d="M9 18l6-6-6-6" />
            </svg>
          </button>

          <button v-else class="btn btn-success" @click="finish">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            <span>{{ t('tutorial.start_using') }}</span>
          </button>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCache } from '@/utils/useCache'
// 导入项目实际使用的菜单图标
import IconModel from '@/assets/svg/menu/icon_dataset_filled.svg'
import IconDatasource from '@/assets/svg/menu/icon_database_filled.svg'
import IconChat from '@/assets/svg/menu/icon_chat_filled.svg'
import IconDashboard from '@/assets/svg/menu/icon_dashboard_filled.svg'

const { t } = useI18n()
const { wsCache } = useCache()

const visible = ref(false)
const currentStep = ref(0)
const dontShowAgain = ref(false)

// 教程步骤 - 模型配置、数据源、智能对话、仪表板（4步）
// 知识库属于系统管理模块，不纳入新手引导
const steps = computed(() => [
  {
    titleKey: 'tutorial.step1.title',
    descKey: 'tutorial.step1.desc',
    icon: IconModel,
    tipKey: 'tutorial.step1.tip',
    details: [
      { titleKey: 'tutorial.step1.detail1.title', descKey: 'tutorial.step1.detail1.desc' },
      { titleKey: 'tutorial.step1.detail2.title', descKey: 'tutorial.step1.detail2.desc' },
      { titleKey: 'tutorial.step1.detail3.title', descKey: 'tutorial.step1.detail3.desc' },
    ],
  },
  {
    titleKey: 'tutorial.step2.title',
    descKey: 'tutorial.step2.desc',
    icon: IconDatasource,
    tipKey: 'tutorial.step2.tip',
    details: [
      { titleKey: 'tutorial.step2.detail1.title', descKey: 'tutorial.step2.detail1.desc' },
      { titleKey: 'tutorial.step2.detail2.title', descKey: 'tutorial.step2.detail2.desc' },
      { titleKey: 'tutorial.step2.detail3.title', descKey: 'tutorial.step2.detail3.desc' },
    ],
  },
  {
    titleKey: 'tutorial.step4.title',
    descKey: 'tutorial.step4.desc',
    icon: IconChat,
    tipKey: 'tutorial.step4.tip',
    details: [
      { titleKey: 'tutorial.step4.detail1.title', descKey: 'tutorial.step4.detail1.desc' },
      { titleKey: 'tutorial.step4.detail2.title', descKey: 'tutorial.step4.detail2.desc' },
      { titleKey: 'tutorial.step4.detail3.title', descKey: 'tutorial.step4.detail3.desc' },
    ],
  },
  {
    titleKey: 'tutorial.step5.title',
    descKey: 'tutorial.step5.desc',
    icon: IconDashboard,
    tipKey: 'tutorial.step5.tip',
    details: [
      { titleKey: 'tutorial.step5.detail1.title', descKey: 'tutorial.step5.detail1.desc' },
      { titleKey: 'tutorial.step5.detail2.title', descKey: 'tutorial.step5.detail2.desc' },
      { titleKey: 'tutorial.step5.detail3.title', descKey: 'tutorial.step5.detail3.desc' },
    ],
  },
])

const show = () => {
  currentStep.value = 0
  visible.value = true
}

const finish = () => {
  if (dontShowAgain.value) {
    wsCache.set('tutorial.dontShow', true)
  }
  visible.value = false
}

const shouldShow = () => {
  return !wsCache.get('tutorial.dontShow')
}

defineExpose({ show, shouldShow })
</script>

<style lang="less">
// 深色主题变量
@dark-bg: #1a1a2e;
@dark-bg-secondary: #16162a;
@dark-bg-card: #1e1e36;
@dark-border: rgba(139, 92, 246, 0.35);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

// 教程弹窗 - 强制覆盖 Element Plus 默认样式
// 使用 custom-class 确保样式正确应用
.tutorial-dialog-inner.ed-dialog,
.tutorial-dialog-inner.el-dialog,
.ed-dialog.tutorial-dialog-inner,
.el-dialog.tutorial-dialog-inner {
  background: @dark-bg !important;
  border: 1px solid @dark-border !important;
  border-radius: 24px !important;
  overflow: hidden !important;
  box-shadow:
    0 25px 80px rgba(0, 0, 0, 0.6),
    0 10px 40px rgba(0, 0, 0, 0.4),
    0 0 80px rgba(124, 58, 237, 0.12) !important;
  height: auto !important;
  max-height: calc(100vh - 40px) !important;

  // 移除所有伪元素
  &::before,
  &::after {
    display: none !important;
    content: none !important;
  }

  // 隐藏默认头部
  .ed-dialog__header,
  .el-dialog__header {
    display: none !important;
    padding: 0 !important;
    margin: 0 !important;
  }

  // 弹窗内容区
  .ed-dialog__body,
  .el-dialog__body {
    padding: 0 !important;
    margin: 0 !important;
    overflow: hidden !important;
    background: @dark-bg !important;
    border: none !important;
    color: @dark-text !important;
  }

  // 隐藏默认底部
  .ed-dialog__footer,
  .el-dialog__footer {
    display: none !important;
    padding: 0 !important;
    margin: 0 !important;
  }
}

// 遮罩层深色
.tutorial-dialog-overlay {
  background-color: rgba(0, 0, 0, 0.65) !important;
}

// 备用选择器
.tutorial-dialog {
  .ed-dialog,
  .el-dialog {
    background: @dark-bg !important;
    border: 1px solid @dark-border !important;
    border-radius: 24px !important;
    overflow: hidden !important;
    box-shadow:
      0 25px 80px rgba(0, 0, 0, 0.6),
      0 10px 40px rgba(0, 0, 0, 0.4),
      0 0 80px rgba(124, 58, 237, 0.12) !important;

    .ed-dialog__header,
    .el-dialog__header {
      display: none !important;
    }

    .ed-dialog__body,
    .el-dialog__body {
      padding: 0 !important;
      background: @dark-bg !important;
    }

    .ed-dialog__footer,
    .el-dialog__footer {
      display: none !important;
    }
  }
}

@media (max-width: 840px) {
  .tutorial-dialog-inner.ed-dialog,
  .tutorial-dialog-inner.el-dialog {
    width: calc(100vw - 32px) !important;
    max-width: 780px !important;
    margin: 16px auto !important;
    max-height: calc(100vh - 32px) !important;
  }
}

@media (max-width: 600px) {
  .tutorial-dialog-inner.ed-dialog,
  .tutorial-dialog-inner.el-dialog {
    width: calc(100vw - 16px) !important;
    margin: 8px auto !important;
    max-height: calc(100vh - 16px) !important;
    border-radius: 18px !important;
  }
}
</style>

<style lang="less" scoped>
// 深色主题变量
@dark-bg: #1a1a2e;
@dark-bg-secondary: #16162a;
@dark-bg-card: #1e1e36;
@dark-bg-hover: #252542;
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.85);
@dark-text-muted: rgba(196, 181, 253, 0.5);
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;

.tutorial-wrapper {
  background: @dark-bg;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 24px;
  height: 100%;
}

.tutorial-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 28px 16px;
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 50%, #5b21b6 100%);
  position: relative;
  overflow: hidden;
  flex-shrink: 0;

  &::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -20%;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 70%);
    pointer-events: none;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
    position: relative;
    z-index: 1;
  }

  .logo-badge {
    width: 48px;
    height: 48px;
    min-width: 48px;
    min-height: 48px;
    background: rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(10px);
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 8px;
    flex-shrink: 0;
    position: relative;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 
      0 4px 12px rgba(0, 0, 0, 0.15),
      0 0 20px rgba(255, 255, 255, 0.1);

    &::before {
      content: '';
      position: absolute;
      inset: -2px;
      background: linear-gradient(135deg, rgba(255, 255, 255, 0.3), transparent);
      border-radius: 16px;
      opacity: 0;
      transition: opacity 0.3s ease;
    }

    &:hover {
      background: rgba(255, 255, 255, 0.25);
      transform: translateY(-2px) scale(1.05);
      box-shadow: 
        0 8px 24px rgba(0, 0, 0, 0.2),
        0 0 30px rgba(255, 255, 255, 0.2);

      &::before {
        opacity: 1;
      }

      .logo-glow-effect {
        opacity: 1;
        transform: scale(1.2);
      }
    }

    .logo-glow-effect {
      position: absolute;
      inset: -8px;
      background: radial-gradient(circle, rgba(255, 255, 255, 0.3) 0%, transparent 70%);
      border-radius: 50%;
      opacity: 0;
      transition: all 0.4s ease;
      pointer-events: none;
    }

    .logo-badge-img {
      width: 100%;
      height: 100%;
      display: block;
      object-fit: contain;
      position: relative;
      z-index: 1;
      filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
    }

    :deep(svg) {
      width: 100%;
      height: 100%;
      border-radius: 12px;
      filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
    }
  }

  .header-text {
    h2 {
      margin: 0 0 4px;
      font-size: 20px;
      font-weight: 700;
      color: white;
    }
    p {
      margin: 0;
      font-size: 13px;
      color: rgba(255, 255, 255, 0.8);
    }
  }

  .close-btn {
    position: relative;
    z-index: 1;
    width: 40px;
    height: 40px;
    border: none;
    background: rgba(255, 255, 255, 0.15);
    color: white;
    border-radius: 12px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.25s;

    &:hover {
      background: rgba(255, 255, 255, 0.25);
      transform: rotate(90deg);
    }
  }
}

.progress-section {
  padding: 14px 28px;
  background: @dark-bg-secondary;
  border-bottom: 1px solid @dark-border;
  flex-shrink: 0;

  .progress-info {
    display: flex;
    justify-content: space-between;
    margin-bottom: 10px;

    .progress-label {
      font-size: 12px;
      font-weight: 600;
      color: @dark-text-muted;
      text-transform: uppercase;
    }
    .progress-value {
      font-size: 13px;
      font-weight: 700;
      color: @primary-400;
    }
  }

  .progress-track {
    height: 6px;
    background: rgba(139, 92, 246, 0.15);
    border-radius: 3px;
    overflow: hidden;

    .progress-fill {
      height: 100%;
      background: linear-gradient(90deg, #7c3aed 0%, #a855f7 100%);
      border-radius: 3px;
      transition: width 0.5s ease;
    }
  }
}

.tutorial-content {
  flex: 1;
  padding: 20px 28px;
  overflow: hidden;
  min-height: 0;
  background: @dark-bg;
}

.step-container {
  display: flex;
  gap: 24px;
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
  min-height: 320px;
  background: @dark-bg-card;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  border: 1px solid @dark-border;
}

.step-sidebar {
  width: 180px;
  flex-shrink: 0;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-right: 20px;
  border-right: 1px solid @dark-border;

  .step-visual {
    position: relative;
    width: 72px;
    height: 72px;
    margin: 0 auto 14px;

    .visual-rings {
      position: absolute;
      inset: 0;

      .ring {
        position: absolute;
        border-radius: 50%;
        border: 1px solid;
        animation: ring-pulse 3s ease-in-out infinite;

        &.ring-1 {
          inset: -8px;
          border-color: rgba(139, 92, 246, 0.3);
        }
        &.ring-2 {
          inset: -18px;
          border-color: rgba(139, 92, 246, 0.2);
          animation-delay: 0.4s;
        }
        &.ring-3 {
          inset: -28px;
          border-color: rgba(139, 92, 246, 0.1);
          animation-delay: 0.8s;
        }
      }
    }

    .visual-icon {
      position: relative;
      width: 100%;
      height: 100%;
      background: linear-gradient(145deg, #7c3aed 0%, #6d28d9 50%, #5b21b6 100%);
      border-radius: 20px;
      padding: 16px;
      color: white;
      box-sizing: border-box;
      box-shadow: 
        0 12px 40px rgba(124, 58, 237, 0.5),
        0 4px 12px rgba(0, 0, 0, 0.3),
        inset 0 1px 0 rgba(255, 255, 255, 0.2);
      transition: all 0.3s ease;

      &::before {
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.2) 0%, transparent 50%);
        border-radius: 20px;
        opacity: 0.5;
      }

      &:hover {
        transform: translateY(-2px);
        box-shadow: 
          0 16px 48px rgba(124, 58, 237, 0.6),
          0 6px 16px rgba(0, 0, 0, 0.4),
          inset 0 1px 0 rgba(255, 255, 255, 0.3);
      }

      :deep(svg) {
        width: 100%;
        height: 100%;
        color: white;
        position: relative;
        z-index: 1;
        filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));

        // 确保所有元素都是白色
        path,
        rect,
        ellipse,
        line,
        circle,
        polygon,
        polyline {
          stroke: white !important;
          fill: none;

          &[fill]:not([fill='none']) {
            fill: rgba(255, 255, 255, 0.25) !important;
          }
        }
      }
    }
  }

  .step-badge {
    margin-bottom: 8px;

    .badge-step {
      display: inline-block;
      padding: 3px 10px;
      background: rgba(139, 92, 246, 0.2);
      color: @primary-400;
      font-size: 10px;
      font-weight: 700;
      border-radius: 20px;
      border: 1px solid rgba(139, 92, 246, 0.3);
    }
  }

  .step-title {
    margin: 0 0 4px;
    font-size: 15px;
    font-weight: 700;
    color: @dark-text;
  }

  .step-desc {
    margin: 0;
    font-size: 11px;
    color: @dark-text-muted;
    line-height: 1.5;
  }
}

.step-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  .guide-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid @dark-border;
    color: @primary-400;
    font-size: 13px;
    font-weight: 600;
  }

  .guide-list {
    flex: 1;
    min-height: 0;
    margin-bottom: 10px;
    overflow-y: auto;

    &::-webkit-scrollbar {
      width: 4px;
    }
    &::-webkit-scrollbar-track {
      background: transparent;
    }
    &::-webkit-scrollbar-thumb {
      background: rgba(139, 92, 246, 0.3);
      border-radius: 2px;
    }

    .guide-item {
      display: flex;
      gap: 12px;
      opacity: 0;
      animation: slide-in 0.4s ease forwards;

      &:not(:last-child) {
        padding-bottom: 8px;
      }

      .item-number {
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;

        span {
          width: 22px;
          height: 22px;
          background: linear-gradient(145deg, #7c3aed 0%, #6d28d9 100%);
          border-radius: 6px;
          font-size: 10px;
          font-weight: 700;
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 8px rgba(124, 58, 237, 0.4);
        }

        .number-line {
          position: absolute;
          top: 26px;
          left: 50%;
          transform: translateX(-50%);
          width: 2px;
          height: calc(100% - 4px);
          background: linear-gradient(
            180deg,
            rgba(139, 92, 246, 0.4) 0%,
            rgba(139, 92, 246, 0.1) 100%
          );
        }
      }

      .item-content {
        flex: 1;
        padding-top: 1px;

        h4 {
          margin: 0 0 2px;
          font-size: 12px;
          font-weight: 600;
          color: @dark-text;
        }
        p {
          margin: 0;
          font-size: 11px;
          color: @dark-text-secondary;
          line-height: 1.35;
        }
      }
    }
  }

  .tip-card {
    display: flex;
    gap: 10px;
    padding: 10px 12px;
    background: rgba(245, 158, 11, 0.1);
    border-radius: 10px;
    border: 1px solid rgba(245, 158, 11, 0.25);
    flex-shrink: 0;

    .tip-icon {
      width: 28px;
      height: 28px;
      background: linear-gradient(145deg, #f59e0b 0%, #d97706 100%);
      border-radius: 7px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      flex-shrink: 0;

      svg {
        width: 14px;
        height: 14px;
      }
    }

    .tip-content {
      flex: 1;

      .tip-label {
        display: block;
        font-size: 9px;
        font-weight: 700;
        color: #fbbf24;
        text-transform: uppercase;
        margin-bottom: 2px;
      }
      p {
        margin: 0;
        font-size: 11px;
        color: rgba(251, 191, 36, 0.9);
        line-height: 1.4;
      }
    }
  }
}

.tutorial-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 28px 20px;
  background: @dark-bg-secondary;
  border-top: 1px solid @dark-border;
  flex-shrink: 0;
  gap: 16px;

  .footer-left {
    flex: 1;
  }

  .footer-center {
    flex-shrink: 0;
  }

  .footer-right {
    flex: 1;
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }

  .checkbox-wrapper {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;

    input {
      display: none;
    }

    .checkbox-box {
      width: 20px;
      height: 20px;
      border: 2px solid rgba(139, 92, 246, 0.4);
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.25s;
      color: transparent;
      background: rgba(139, 92, 246, 0.1);
    }

    input:checked + .checkbox-box {
      background: linear-gradient(145deg, #7c3aed 0%, #6d28d9 100%);
      border-color: #7c3aed;
      color: white;
    }

    .checkbox-label {
      font-size: 13px;
      color: @dark-text-secondary;
    }
  }

  .step-indicators {
    display: flex;
    gap: 8px;
    padding: 6px 12px;
    background: rgba(139, 92, 246, 0.1);
    border-radius: 20px;
    border: 1px solid @dark-border;

    .indicator {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      border: none;
      background: rgba(139, 92, 246, 0.3);
      cursor: pointer;
      padding: 0;
      transition: all 0.35s;

      &:hover {
        background: @primary-400;
        transform: scale(1.2);
      }
      &.active {
        width: 28px;
        border-radius: 5px;
        background: linear-gradient(90deg, #7c3aed 0%, #a855f7 100%);
      }
      &.completed {
        background: linear-gradient(145deg, #7c3aed 0%, #6d28d9 100%);
      }
    }
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 44px;
    padding: 0 20px;
    border: none;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.25s;
    white-space: nowrap;
    flex-shrink: 0;

    &.btn-invisible {
      visibility: hidden;
      pointer-events: none;
    }

    &.btn-secondary {
      background: rgba(139, 92, 246, 0.15);
      color: @dark-text-secondary;
      border: 1px solid @dark-border;
      &:hover {
        background: rgba(139, 92, 246, 0.25);
        color: @dark-text;
        transform: translateY(-1px);
      }
    }

    &.btn-primary {
      background: linear-gradient(145deg, #7c3aed 0%, #6d28d9 100%);
      color: white;
      box-shadow: 0 4px 14px rgba(124, 58, 237, 0.4);
      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(124, 58, 237, 0.5);
      }
    }

    &.btn-success {
      background: linear-gradient(145deg, #10b981 0%, #059669 100%);
      color: white;
      box-shadow: 0 4px 14px rgba(16, 185, 129, 0.4);
      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.5);
      }
    }
  }
}

@keyframes ring-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.08);
    opacity: 0.6;
  }
}

@keyframes slide-in {
  from {
    opacity: 0;
    transform: translateX(-12px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.4s ease;
}
.slide-fade-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.slide-fade-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

@media (max-width: 768px) {
  .step-container {
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    min-height: 300px;
  }

  .step-sidebar {
    width: 100%;
    padding-right: 0;
    border-right: none;
    padding-bottom: 12px;
    border-bottom: 1px solid @dark-border;

    .step-visual {
      width: 56px;
      height: 56px;
      margin-bottom: 10px;
      .visual-icon {
        border-radius: 14px;
        padding: 12px;
      }
    }
  }

  .tutorial-footer {
    .footer-left {
      display: none;
    }
  }
}
</style>
