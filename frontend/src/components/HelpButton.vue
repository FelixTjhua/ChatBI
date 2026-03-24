<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { QuestionFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus-secondary'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const showMenu = ref(false)
const hasContent = ref(false)

// 监听聊天内容变化
const handleChatContentChange = (event: CustomEvent) => {
  hasContent.value = event.detail.hasContent
}

onMounted(() => {
  window.addEventListener('chatContentChange', handleChatContentChange as EventListener)
})

onBeforeUnmount(() => {
  window.removeEventListener('chatContentChange', handleChatContentChange as EventListener)
})

const openGuide = () => {
  showMenu.value = false
  ElMessage.info(t('help.guide_coming_soon'))
}

const loadDemoData = () => {
  showMenu.value = false
  ElMessageBox.confirm(
    t('help.demo_data_desc'),
    '📦 ' + t('help.load_demo_data'),
    {
      confirmButtonText: t('help.load_demo_data'),
      cancelButtonText: t('common.skip'),
      type: 'info',
      customClass: 'demo-data-dialog',
      showClose: false,
    }
  ).then(() => {
    ElMessage.success(t('help.demo_data_success'))
  }).catch(() => {
    // 用户取消
  })
}

const contactSupport = () => {
  showMenu.value = false
  ElMessageBox.alert(
    t('help.contact_desc'),
    t('help.contact_us'),
    {
      confirmButtonText: t('common.ok'),
      customClass: 'contact-dialog',
    }
  )
}
</script>

<template>
  <div class="help-button-container">
    <el-popover
      v-model:visible="showMenu"
      placement="top-end"
      :width="240"
      trigger="click"
      popper-class="help-menu-popover"
    >
      <template #reference>
        <el-button circle class="help-button" type="primary">
          <el-icon :size="20">
            <QuestionFilled />
          </el-icon>
        </el-button>
      </template>

      <div class="help-menu">
        <div class="help-menu-header">
          <span class="help-icon">❓</span>
          <span class="help-title">{{ t('help.need_help') }}</span>
        </div>

        <div class="help-menu-items">
          <div class="help-menu-item" @click="openGuide">
            <span class="item-icon">📘</span>
            <div class="item-content">
              <div class="item-title">{{ t('help.user_guide') }}</div>
              <div class="item-desc">{{ t('help.user_guide_desc') }}</div>
            </div>
          </div>

          <div class="help-menu-item" @click="loadDemoData">
            <span class="item-icon">📦</span>
            <div class="item-content">
              <div class="item-title">{{ t('help.load_demo_data') }}</div>
              <div class="item-desc">{{ t('help.load_demo_data_short') }}</div>
            </div>
          </div>

          <div class="help-menu-item" @click="contactSupport">
            <span class="item-icon">✉️</span>
            <div class="item-content">
              <div class="item-title">{{ t('help.contact_us') }}</div>
              <div class="item-desc">{{ t('help.contact_us_desc') }}</div>
            </div>
          </div>
        </div>
      </div>
    </el-popover>
  </div>
</template>

<style lang="less" scoped>
.help-button-container {
  position: fixed;
  bottom: 32px;
  right: 32px;
  z-index: 1000;

  .help-button {
    width: 56px;
    height: 56px;
    background: linear-gradient(145deg, #8b5cf6 0%, #7c3aed 100%);
    border: none;
    box-shadow: 0 8px 24px rgba(124, 58, 237, 0.4);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

    &:hover {
      transform: translateY(-4px) scale(1.05);
      box-shadow: 0 12px 32px rgba(124, 58, 237, 0.5);
    }

    &:active {
      transform: translateY(-2px) scale(1.02);
    }

    :deep(.el-icon),
    :deep(.ed-icon) {
      color: #fff;
    }
  }
}

.help-menu {
  padding: 4px 0;

  .help-menu-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    border-bottom: 1px solid rgba(139, 92, 246, 0.15);
    margin-bottom: 4px;

    .help-icon {
      font-size: 20px;
    }

    .help-title {
      font-size: 15px;
      font-weight: 600;
      color: rgba(255, 255, 255, 0.95);
    }
  }

  .help-menu-items {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .help-menu-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    cursor: pointer;
    border-radius: 8px;
    transition: all 0.2s ease;

    &:hover {
      background: rgba(139, 92, 246, 0.1);
    }

    .item-icon {
      font-size: 20px;
      flex-shrink: 0;
    }

    .item-content {
      flex: 1;
      min-width: 0;

      .item-title {
        font-size: 14px;
        font-weight: 500;
        color: rgba(255, 255, 255, 0.95);
        margin-bottom: 2px;
      }

      .item-desc {
        font-size: 12px;
        color: rgba(196, 181, 253, 0.7);
        line-height: 1.4;
      }
    }
  }
}

// 响应式
@media (max-width: 768px) {
  .help-button-container {
    bottom: 24px;
    right: 24px;

    .help-button {
      width: 48px;
      height: 48px;
    }
  }
}
</style>

<style lang="less">
// 全局样式 - Popover
.help-menu-popover {
  background: linear-gradient(145deg, rgba(26, 18, 37, 0.98) 0%, rgba(20, 14, 32, 0.98) 100%) !important;
  border: 1.5px solid rgba(139, 92, 246, 0.2) !important;
  border-radius: 14px !important;
  padding: 0 !important;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.4) !important;

  .ed-popper__arrow::before,
  .el-popper__arrow::before {
    background: rgba(26, 18, 37, 0.98) !important;
    border: 1.5px solid rgba(139, 92, 246, 0.2) !important;
  }
}

// 演示数据对话框样式
.demo-data-dialog {
  background: linear-gradient(145deg, rgba(26, 18, 37, 0.98) 0%, rgba(20, 14, 32, 0.98) 100%) !important;
  border: 1.5px solid rgba(139, 92, 246, 0.2) !important;
  border-radius: 16px !important;

  .ed-message-box__title,
  .el-message-box__title {
    color: rgba(255, 255, 255, 0.95) !important;
  }

  .ed-message-box__message,
  .el-message-box__message {
    color: rgba(196, 181, 253, 0.85) !important;
    white-space: pre-line;
    line-height: 1.6;
  }
}

// 联系对话框样式
.contact-dialog {
  background: linear-gradient(145deg, rgba(26, 18, 37, 0.98) 0%, rgba(20, 14, 32, 0.98) 100%) !important;
  border: 1.5px solid rgba(139, 92, 246, 0.2) !important;
  border-radius: 16px !important;

  .ed-message-box__title,
  .el-message-box__title {
    color: rgba(255, 255, 255, 0.95) !important;
  }

  .ed-message-box__message,
  .el-message-box__message {
    color: rgba(196, 181, 253, 0.85) !important;
    white-space: pre-line;
    line-height: 1.8;
    font-family: monospace;
  }
}
</style>
