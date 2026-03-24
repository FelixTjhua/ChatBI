<script lang="ts" setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const dialogVisible = ref(false)
const { t, locale } = useI18n()

// ChatBI 版本信息
const appInfo = computed(() => ({
  name: 'ChatBI',
  version: 'v1.0.0',
  description:
    locale.value === 'zh-CN'
      ? '基于RAG与大语言模型的商业智能分析对话系统'
      : 'Business Intelligence Analysis Dialogue System based on RAG and LLM',
  copyright: 'Felix Alvin Juandra（蔡威广）',
  license:
    locale.value === 'zh-CN'
      ? '仅供学术研究与个人学习使用'
      : 'For Academic Research & Personal Use Only',
  features:
    locale.value === 'zh-CN'
      ? ['自然语言转SQL', 'RAG 知识库检索', '多数据源接入', '数据洞察', '文档智能问答', '多模型支持']
      : ['NL-to-SQL', 'RAG Knowledge Base', 'Multi-Datasource', 'Data Insights', 'Doc Q&A', 'Multi-LLM Support'],
}))

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
    class="about-dialog-ultimate"
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
          <div class="logo-section">
            <img 
              src="@/assets/chatbi-logo-new.svg?url" 
              alt="ChatBI" 
              class="logo-img"
            />
            <div class="brand-info">
              <h2 class="brand-name">
                <span class="brand-chat">Chat</span><span class="brand-bi">BI</span>
              </h2>
              <span class="version-tag">{{ appInfo.version }}</span>
            </div>
          </div>
          <p class="brand-desc">{{ appInfo.description }}</p>
        </div>
        <button class="close-btn" @click="dialogVisible = false">
          <span class="close-x">×</span>
        </button>
      </div>
    </template>

    <!-- 内容区域 -->
    <div class="about-content-ultimate">
      <!-- 信息卡片 -->
      <div class="info-section">
        <div class="info-item">
          <span class="info-label">{{ t('about.copyright') }}</span>
          <span class="info-value">© {{ appInfo.copyright }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('about.license') }}</span>
          <span class="info-value license-text">{{ appInfo.license }}</span>
        </div>
      </div>

      <!-- 核心功能 -->
      <div class="features-section">
        <div class="features-title">
          <span class="title-icon">🧩</span>
          <span class="title-text">{{ t('about.features') }}</span>
        </div>
        <div class="features-list">
          <div 
            v-for="(feature, index) in appInfo.features" 
            :key="index" 
            class="feature-tag"
          >
            <span class="tag-dot"></span>
            <span class="tag-text">{{ feature }}</span>
          </div>
        </div>
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

    .logo-section {
      display: flex;
      align-items: center;
      gap: 14px;
      margin-bottom: 12px;

      .logo-img {
        width: 48px;
        height: 48px;
        flex-shrink: 0;
        padding: 8px;
        background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(168, 85, 247, 0.12));
        border-radius: 14px;
        border: 1.5px solid rgba(168, 85, 247, 0.35);
        transition: all 0.3s ease;

        &:hover {
          transform: scale(1.08) rotate(5deg);
          border-color: rgba(168, 85, 247, 0.5);
        }
      }

      .brand-info {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 6px;

        .brand-name {
          margin: 0;
          font-size: 26px;
          font-weight: 800;
          letter-spacing: -0.5px;
          line-height: 1;

          .brand-chat {
            color: @dark-text;
          }

          .brand-bi {
            background: linear-gradient(135deg, @primary-400 0%, @primary-500 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
          }
        }

        .version-tag {
          display: inline-block;
          font-size: 11px;
          font-weight: 700;
          color: @primary-400;
          background: rgba(139, 92, 246, 0.2);
          padding: 4px 10px;
          border-radius: 10px;
          border: 1.5px solid rgba(139, 92, 246, 0.35);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          width: fit-content;
        }
      }
    }

    .brand-desc {
      margin: 0;
      font-size: 13px;
      font-weight: 500;
      color: @dark-text-secondary;
      line-height: 1.5;
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
.about-content-ultimate {
  padding: 0;

  // 信息区域
  .info-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 24px;

    .info-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 18px;
      background: linear-gradient(
        135deg,
        rgba(139, 92, 246, 0.15) 0%,
        rgba(168, 85, 247, 0.1) 100%
      );
      border-radius: 12px;
      border: 1.5px solid rgba(139, 92, 246, 0.25);
      transition: all 0.3s ease;

      &:hover {
        border-color: rgba(139, 92, 246, 0.4);
        background: linear-gradient(
          135deg,
          rgba(139, 92, 246, 0.22) 0%,
          rgba(168, 85, 247, 0.15) 100%
        );
        transform: translateX(4px);
      }

      .info-label {
        font-size: 12px;
        font-weight: 700;
        color: @dark-text-muted;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .info-value {
        font-size: 14px;
        font-weight: 600;
        color: @dark-text;
        text-align: right;
      }

      .license-text {
        color: @success;
        font-weight: 700;
      }
    }
  }

  // 功能区域
  .features-section {
    padding: 20px;
    background: linear-gradient(
      135deg,
      rgba(139, 92, 246, 0.12) 0%,
      rgba(168, 85, 247, 0.08) 100%
    );
    border-radius: 12px;
    border: 1.5px solid rgba(139, 92, 246, 0.25);

    .features-title {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 16px;

      .title-icon {
        font-size: 18px;
      }

      .title-text {
        font-size: 14px;
        font-weight: 800;
        color: @dark-text;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
    }

    .features-list {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;

      .feature-tag {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 14px;
        background: rgba(139, 92, 246, 0.1);
        border: 1.5px solid rgba(139, 92, 246, 0.2);
        border-radius: 10px;
        transition: all 0.3s ease;

        &:hover {
          background: rgba(139, 92, 246, 0.18);
          border-color: rgba(139, 92, 246, 0.35);
          transform: translateX(4px);
        }

        .tag-dot {
          width: 6px;
          height: 6px;
          flex-shrink: 0;
          background: @success;
          border-radius: 50%;
          box-shadow: 0 0 8px rgba(74, 222, 128, 0.5);
        }

        .tag-text {
          flex: 1;
          font-size: 13px;
          font-weight: 600;
          color: @dark-text-secondary;
        }
      }
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
      .logo-section {
        .logo-img {
          width: 40px;
          height: 40px;
        }

        .brand-info {
          .brand-name {
            font-size: 22px;
          }
        }
      }

      .brand-desc {
        font-size: 12px;
      }
    }
  }

  .about-content-ultimate {
    .features-section {
      .features-list {
        grid-template-columns: 1fr;
      }
    }
  }
}
</style>

<style lang="less">
// 全局样式 - 对话框深色主题
.about-dialog-ultimate,
.about-dialog-ultimate.ed-dialog,
.about-dialog-ultimate.el-dialog,
.el-dialog.about-dialog-ultimate,
.ed-dialog.about-dialog-ultimate {
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
:deep(.ed-overlay):has(+ .about-dialog-ultimate),
:deep(.el-overlay):has(+ .about-dialog-ultimate),
:deep(.ed-overlay-dialog):has(+ .about-dialog-ultimate),
:deep(.el-overlay-dialog):has(+ .about-dialog-ultimate) {
  background-color: rgba(15, 10, 26, 0.75) !important;
  backdrop-filter: blur(6px) !important;
  -webkit-backdrop-filter: blur(6px) !important;
}

// 全局遮罩层样式
.el-overlay:has(+ .about-dialog-ultimate),
.ed-overlay:has(+ .about-dialog-ultimate) {
  background-color: rgba(15, 10, 26, 0.75) !important;
  backdrop-filter: blur(6px) !important;
  -webkit-backdrop-filter: blur(6px) !important;
}

// 响应式适配
@media (max-width: 600px) {
  .about-dialog-ultimate,
  .about-dialog-ultimate.ed-dialog,
  .about-dialog-ultimate.el-dialog {
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
