<script lang="ts" setup>
import { ref, computed } from 'vue'
import Default_avatar_custom from '@/assets/img/Default-avatar.svg'
import icon_admin_outlined from '@/assets/svg/icon_admin_outlined.svg'
import icon_info_outlined_1 from '@/assets/svg/icon_info_outlined_1.svg'
import { useAppearanceStoreWithOut } from '@/stores/appearance'
import icon_maybe_outlined from '@/assets/svg/icon-maybe_outlined.svg'
import icon_key_outlined from '@/assets/svg/icon-key_outlined.svg'
import icon_translate_outlined from '@/assets/svg/icon_translate_outlined.svg'
import icon_logout_outlined from '@/assets/svg/icon_logout_outlined.svg'
import icon_right_outlined from '@/assets/svg/icon_right_outlined.svg'
import AboutDialog from '@/components/about/index.vue'
import HelpDialog from '@/components/help/index.vue'
import icon_done_outlined from '@/assets/svg/icon_done_outlined.svg'
import { useI18n } from 'vue-i18n'
import PwdForm from './PwdForm.vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { userApi } from '@/api/auth'

const router = useRouter()
const appearanceStore = useAppearanceStoreWithOut()
const userStore = useUserStore()
const pwdFormRef = ref()
const { t, locale } = useI18n()
defineProps({
  collapse: { type: [Boolean], required: true },
  inSysmenu: { type: [Boolean], required: true },
})

const name = computed(() => userStore.getName)
const account = computed(() => userStore.getAccount)
const currentLanguage = computed(() => userStore.getLanguage)
const isAdmin = computed(() => userStore.isAdmin)
const dialogVisible = ref(false)
const aboutRef = ref()
const helpRef = ref()
const languageList = computed(() => [
  {
    name: 'English',
    value: 'en',
  },
  {
    name: '简体中文',
    value: 'zh-CN',
  },
])
const popoverRef = ref()

const toSystem = () => {
  popoverRef.value.hide()
  router.push('/system')
}

const changeLanguage = (lang: string) => {
  locale.value = lang
  userStore.setLanguage(lang)
  const param = {
    language: lang,
  }
  userApi.language(param).then(() => {
    window.location.reload()
  }).catch(() => {
    window.location.reload()
  })
}

const openHelp = () => {
  popoverRef.value?.hide()
  helpRef.value?.open()
}

const openPwd = () => {
  dialogVisible.value = true
}
const closePwd = () => {
  dialogVisible.value = false
}

const toAbout = () => {
  aboutRef.value?.open()
}
const savePwdHandler = () => {
  pwdFormRef.value?.submit()
}
const logout = async () => {
  await userStore.logout()
  router.push('/login')
}
</script>

<template>
  <el-popover
    ref="popoverRef"
    trigger="click"
    popper-class="system-person"
    :placement="collapse ? 'right' : 'top-start'"
  >
    <template #reference>
      <button class="person" :title="name" :class="collapse && 'collapse'">
        <el-icon size="32">
          <Default_avatar_custom></Default_avatar_custom>
        </el-icon>
        <span v-if="!collapse" class="name ellipsis">{{ name }}</span>
      </button></template
    >
    <div class="popover">
      <div class="popover-content">
        <div class="info">
          <div class="info-text">
            <div :title="name" class="top ellipsis">{{ name }}</div>
            <div :title="account" class="bottom ellipsis">{{ account }}</div>
          </div>
        </div>
        <div v-if="isAdmin && !inSysmenu" class="popover-item" @click="toSystem">
          <el-icon size="16">
            <icon_admin_outlined></icon_admin_outlined>
          </el-icon>
          <div class="datasource-name">{{ $t('common.system_manage') }}</div>
        </div>
        <div class="popover-item" @click="openPwd">
          <el-icon size="16">
            <icon_key_outlined></icon_key_outlined>
          </el-icon>
          <div class="datasource-name">{{ $t('user.change_password') }}</div>
        </div>
        <el-popover 
          popper-class="system-language" 
          placement="right-start"
          trigger="click"
          :show-arrow="false"
          :offset="10"
        >
          <template #reference>
            <div class="popover-item">
              <el-icon size="16">
                <icon_translate_outlined></icon_translate_outlined>
              </el-icon>
              <div class="datasource-name">{{ $t('common.language') }}</div>
              <el-icon class="right" size="16">
                <icon_right_outlined></icon_right_outlined>
              </el-icon>
            </div>
          </template>
          <div class="language-popover">
            <div
              v-for="ele in languageList"
              :key="ele.name"
              class="popover-item_language"
              :class="currentLanguage === ele.value && 'isActive'"
              @click="changeLanguage(ele.value)"
            >
              <div class="language-name">{{ ele.name }}</div>
              <el-icon size="16" class="done">
                <icon_done_outlined></icon_done_outlined>
              </el-icon>
            </div>
          </div>
        </el-popover>
        <div v-if="appearanceStore.getShowAbout" class="popover-item" @click="toAbout">
          <el-icon size="16">
            <icon_info_outlined_1></icon_info_outlined_1>
          </el-icon>
          <div class="datasource-name">{{ $t('about.title') }}</div>
        </div>
        <div v-if="appearanceStore.getShowDoc" class="popover-item" @click="openHelp">
          <el-icon size="16">
            <icon_maybe_outlined></icon_maybe_outlined>
          </el-icon>
          <div class="datasource-name">{{ $t('common.help') }}</div>
        </div>
        <div class="popover-item mr4" @click="logout">
          <el-icon size="16">
            <icon_logout_outlined></icon_logout_outlined>
          </el-icon>
          <div class="datasource-name">{{ $t('common.logout') }}</div>
        </div>
      </div>
    </div>
  </el-popover>

  <el-dialog
    v-model="dialogVisible"
    :show-close="false"
    width="520"
    class="pwd-dialog-premium"
    :modal="true"
    :close-on-click-modal="false"
    :close-on-press-escape="true"
    append-to-body
  >
    <template #header>
      <div class="dialog-header-premium">
        <div class="header-content">
          <h3 class="header-title">{{ t('user.upgrade_pwd.title') }}</h3>
          <p class="header-subtitle">{{ t('pwd.security_subtitle') }}</p>
        </div>
        <button class="header-close" @click="closePwd">
          <span class="close-icon">×</span>
        </button>
      </div>
    </template>
    
    <pwd-form v-if="dialogVisible" ref="pwdFormRef" @pwd-saved="closePwd" />
    
    <template #footer>
      <div class="dialog-footer-premium">
        <el-button class="btn-cancel-premium" size="large" @click="closePwd">
          {{ t('common.cancel') }}
        </el-button>
        <el-button type="primary" class="btn-save-premium" size="large" @click="savePwdHandler">
          {{ t('common.save') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
  <AboutDialog ref="aboutRef" />
  <HelpDialog ref="helpRef" />
</template>

<style lang="less" scoped>
// ChatBI 用户按钮 - 深色主题，简洁设计
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@dark-border: rgba(139, 92, 246, 0.25);

.person {
  padding: 0 14px;
  display: flex;
  align-items: center;
  cursor: pointer;
  height: 52px;
  border: none;
  background: linear-gradient(
    135deg,
    rgba(139, 92, 246, 0.15) 0%,
    rgba(168, 85, 247, 0.1) 100%
  );
  position: relative;
  color: rgba(255, 255, 255, 0.95);
  border-radius: 14px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  flex: 1;
  min-width: 0;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 14px;
    background: linear-gradient(
      135deg,
      rgba(139, 92, 246, 0.2) 0%,
      rgba(168, 85, 247, 0.15) 100%
    );
    opacity: 0;
    transition: opacity 0.3s ease;
  }

  &:hover {
    background: linear-gradient(
      135deg,
      rgba(139, 92, 246, 0.22) 0%,
      rgba(168, 85, 247, 0.15) 100%
    );
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(139, 92, 246, 0.3);

    &::before {
      opacity: 1;
    }
  }

  &:active {
    transform: translateY(0);
  }

  &.collapse {
    width: 52px;
    height: 52px;
    justify-content: center;
    padding: 0;
    flex: none;
    border-radius: 14px;

    .name {
      display: none;
    }
    
    :deep(svg) {
      width: 24px;
      height: 24px;
    }
  }

  .name {
    font-weight: 600;
    font-size: 14px;
    line-height: 1.4;
    margin-left: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: rgba(255, 255, 255, 0.95);
    position: relative;
    z-index: 1;
    letter-spacing: 0.02em;
  }

  :deep(svg) {
    flex-shrink: 0;
    filter: drop-shadow(0 0 6px rgba(139, 92, 246, 0.4));
    position: relative;
    z-index: 1;
  }
}
</style>

<style lang="less">
// ChatBI 用户菜单弹出框 - 高级深色玻璃态主题
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@dark-bg: #0f0a1a;
@dark-bg-secondary: #1a1225;
@dark-bg-card: rgba(20, 14, 32, 0.98);
@dark-border: rgba(139, 92, 246, 0.3);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.85);
@dark-text-muted: rgba(196, 181, 253, 0.6);

.system-person.system-person {
  padding: 0 !important;
  width: 200px !important;
  background: linear-gradient(
    180deg,
    rgba(26, 18, 37, 0.98) 0%,
    rgba(15, 10, 26, 0.98) 100%
  ) !important;
  backdrop-filter: blur(24px) !important;
  -webkit-backdrop-filter: blur(24px) !important;
  box-shadow:
    0 24px 70px rgba(0, 0, 0, 0.85),
    0 0 0 1px @dark-border,
    inset 0 1px 0 rgba(139, 92, 246, 0.2),
    0 0 50px rgba(124, 58, 237, 0.2) !important;
  border: 2px solid @dark-border !important;
  border-radius: 20px !important;
  overflow: hidden;

  &::after,
  &::before {
    display: none;
  }

  .popover {
    .popover-content {
      display: flex;
      flex-direction: column;
      gap: 0;
    }

    // 用户信息区域 - 紧凑优雅
    .info {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 18px 16px 16px;
      margin: 0;
      background: linear-gradient(
        135deg,
        rgba(139, 92, 246, 0.25) 0%,
        rgba(168, 85, 247, 0.15) 100%
      );
      border-bottom: 2px solid rgba(139, 92, 246, 0.25);
      position: relative;
      overflow: hidden;

      // 背景光晕
      &::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -30%;
        width: 150px;
        height: 150px;
        background: radial-gradient(circle, rgba(139, 92, 246, 0.2) 0%, transparent 70%);
        pointer-events: none;
      }

      .info-text {
        width: 100%;
        text-align: center;
        position: relative;
        z-index: 1;

        .top {
          font-weight: 700;
          font-size: 16px;
          line-height: 1.4;
          color: @dark-text;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          margin-bottom: 5px;
          text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
          letter-spacing: 0.3px;
        }

        .bottom {
          font-weight: 500;
          font-size: 12px;
          line-height: 1.4;
          color: @dark-text-muted;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }

    // 菜单项容器
    .popover-content > div:not(.info) {
      padding: 0 12px;
    }

    // 第一个菜单项添加上边距
    .popover-content > div:not(.info):first-of-type {
      margin-top: 12px;
    }

    // 最后一个菜单项添加下边距
    .popover-content > div:last-child {
      margin-bottom: 12px;
    }

    // 菜单项 - 适配长文本
    .popover-item {
      min-height: 46px;
      height: auto;
      display: flex;
      align-items: center;
      padding: 12px 14px;
      position: relative;
      cursor: pointer;
      border-radius: 12px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      color: @dark-text-secondary;
      border: 2px solid transparent;
      gap: 12px;
      margin-bottom: 6px;
      background: transparent;

      &::before {
        content: '';
        position: absolute;
        inset: 0;
        border-radius: 14px;
        background: linear-gradient(
          135deg,
          rgba(139, 92, 246, 0.1) 0%,
          rgba(168, 85, 247, 0.06) 100%
        );
        opacity: 0;
        transition: opacity 0.3s ease;
      }

      .ed-icon,
      .el-icon {
        flex-shrink: 0;
        width: 22px;
        height: 22px;
        color: @primary-400 !important;
        opacity: 0.85;
        transition: all 0.3s ease;
        position: relative;
        z-index: 1;
      }

      &:hover {
        background: linear-gradient(
          135deg,
          rgba(139, 92, 246, 0.22) 0%,
          rgba(168, 85, 247, 0.15) 100%
        );
        border-color: rgba(139, 92, 246, 0.35);
        color: @dark-text;
        transform: translateX(5px);
        box-shadow: 
          0 6px 20px rgba(139, 92, 246, 0.3),
          inset 0 1px 0 rgba(139, 92, 246, 0.2);

        &::before {
          opacity: 1;
        }

        .ed-icon,
        .el-icon {
          opacity: 1;
          color: @primary-400 !important;
          filter: drop-shadow(0 0 8px rgba(139, 92, 246, 0.7));
          transform: scale(1.15);
        }
      }

      &:active {
        transform: translateX(3px) scale(0.98);
      }

      // 菜单文字 - 适配长文本
      .datasource-name {
        flex: 1;
        min-width: 0;
        font-size: 13px;
        font-weight: 600;
        line-height: 1.5;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        position: relative;
        z-index: 1;
        letter-spacing: 0.2px;
      }

      // 退出登录按钮 - 红色主题，更大间距
      &.mr4 {
        margin-top: 20px;
        margin-bottom: 0;
        padding: 14px 16px;
        position: relative;
        background: transparent;
        border-color: transparent;

        // 分隔线 - 更大间距
        &::after {
          content: '';
          position: absolute;
          top: -10px;
          left: 20px;
          right: 20px;
          height: 1px;
          background: linear-gradient(
            90deg,
            transparent 0%,
            rgba(239, 68, 68, 0.3) 50%,
            transparent 100%
          );
        }

        color: #fca5a5;

        .ed-icon,
        .el-icon {
          color: #f87171 !important;
        }

        &:hover {
          background: linear-gradient(
            135deg,
            rgba(239, 68, 68, 0.18) 0%,
            rgba(220, 38, 38, 0.12) 100%
          );
          border-color: rgba(239, 68, 68, 0.35);
          color: #fecaca;
          box-shadow: 
            0 6px 20px rgba(239, 68, 68, 0.3),
            inset 0 1px 0 rgba(239, 68, 68, 0.15);

          .ed-icon,
          .el-icon {
            color: #fca5a5 !important;
            filter: drop-shadow(0 0 8px rgba(239, 68, 68, 0.6));
          }
        }
      }

      // 右箭头图标
      .right {
        flex-shrink: 0;
        margin-left: auto;
        color: @dark-text-muted !important;
        opacity: 0.5;
        transition: all 0.25s ease;
      }

      &:hover .right {
        opacity: 1;
        transform: translateX(2px);
      }
    }
  }
}

// 语言选择子菜单 - 适配长文本
.system-language.system-language {
  padding: 10px !important;
  width: 190px !important;
  background: linear-gradient(
    180deg,
    rgba(26, 18, 37, 0.98) 0%,
    rgba(15, 10, 26, 0.98) 100%
  ) !important;
  backdrop-filter: blur(24px) !important;
  -webkit-backdrop-filter: blur(24px) !important;
  box-shadow:
    0 16px 50px rgba(0, 0, 0, 0.75),
    0 0 0 1px @dark-border,
    inset 0 1px 0 rgba(139, 92, 246, 0.2) !important;
  border: 2px solid @dark-border !important;
  border-radius: 18px !important;
  overflow: hidden;

  &::after,
  &::before {
    display: none;
  }

  .language-popover {
    display: flex;
    flex-direction: column;
    gap: 6px;

    .popover-item_language {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 13px 14px;
      border-radius: 12px;
      cursor: pointer;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      color: @dark-text-secondary;
      border: 2px solid transparent;
      background: transparent;
      position: relative;
      overflow: hidden;
      min-height: 42px;

      &::before {
        content: '';
        position: absolute;
        inset: 0;
        border-radius: 12px;
        background: linear-gradient(
          135deg,
          rgba(139, 92, 246, 0.1) 0%,
          rgba(168, 85, 247, 0.06) 100%
        );
        opacity: 0;
        transition: opacity 0.3s ease;
      }

      &:hover {
        background: linear-gradient(
          135deg,
          rgba(139, 92, 246, 0.18) 0%,
          rgba(168, 85, 247, 0.12) 100%
        );
        border-color: rgba(139, 92, 246, 0.3);
        color: @dark-text;
        transform: translateX(4px);
        box-shadow: 0 4px 12px rgba(139, 92, 246, 0.25);

        &::before {
          opacity: 1;
        }
      }

      &:active {
        transform: translateX(2px) scale(0.98);
      }

      &.isActive {
        background: linear-gradient(
          135deg,
          rgba(139, 92, 246, 0.28) 0%,
          rgba(168, 85, 247, 0.2) 100%
        );
        border-color: rgba(139, 92, 246, 0.45);
        color: @dark-text;
        box-shadow: 
          0 6px 16px rgba(139, 92, 246, 0.35),
          inset 0 1px 0 rgba(139, 92, 246, 0.25);

        .language-name {
          font-weight: 700;
        }

        .done {
          opacity: 1;
          color: @primary-400 !important;
          filter: drop-shadow(0 0 8px rgba(139, 92, 246, 0.7));
          transform: scale(1);
        }
      }

      .language-name {
        flex: 1;
        font-size: 13px;
        font-weight: 500;
        line-height: 1.5;
        position: relative;
        z-index: 1;
        letter-spacing: 0.2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .done {
        flex-shrink: 0;
        opacity: 0;
        transition: all 0.3s ease;
        color: @primary-400 !important;
        transform: scale(0.8);
        position: relative;
        z-index: 1;
      }
    }
  }
}

// 修改密码对话框 - 全新高级设计
// 使用多种选择器确保样式生效
.pwd-dialog-premium,
.pwd-dialog-premium.ed-dialog,
.pwd-dialog-premium.el-dialog,
.el-dialog.pwd-dialog-premium,
.ed-dialog.pwd-dialog-premium {
  background: linear-gradient(
    165deg,
    rgba(25, 15, 45, 0.98) 0%,
    rgba(15, 10, 30, 0.98) 100%
  ) !important;
  backdrop-filter: blur(24px) !important;
  -webkit-backdrop-filter: blur(24px) !important;
  border: 2px solid rgba(168, 85, 247, 0.4) !important;
  border-radius: 28px !important;
  box-shadow:
    0 30px 80px rgba(0, 0, 0, 0.7),
    0 0 0 1px rgba(168, 85, 247, 0.25),
    inset 0 1px 0 rgba(168, 85, 247, 0.2),
    0 0 120px rgba(124, 58, 237, 0.2) !important;
  max-width: 90vw;
  overflow: visible;
  padding: 0 !important;

  // 隐藏默认头部
  .ed-dialog__header,
  .el-dialog__header {
    display: none !important;
    padding: 0 !important;
    margin: 0 !important;
  }
  
  // 自定义头部
  .dialog-header-premium {
    padding: 32px 32px 28px;
    background: linear-gradient(
      135deg,
      rgba(168, 85, 247, 0.22) 0%,
      rgba(139, 92, 246, 0.12) 50%,
      rgba(124, 58, 237, 0.08) 100%
    );
    border-bottom: 1.5px solid rgba(168, 85, 247, 0.3);
    border-radius: 28px 28px 0 0;
    position: relative;
    display: flex;
    align-items: flex-start;
    gap: 16px;

    &::after {
      content: '';
      position: absolute;
      bottom: 0;
      left: 32px;
      right: 32px;
      height: 1px;
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(168, 85, 247, 0.5) 50%,
        transparent 100%
      );
    }
    
    .header-content {
      flex: 1;
      min-width: 0;
      
      .header-title {
        margin: 0 0 8px 0;
        font-size: 22px;
        font-weight: 700;
        color: rgba(255, 255, 255, 0.98);
        letter-spacing: 0.02em;
        text-shadow: 0 2px 12px rgba(168, 85, 247, 0.4);
      }
      
      .header-subtitle {
        margin: 0;
        font-size: 14px;
        font-weight: 500;
        color: rgba(196, 181, 253, 0.75);
        line-height: 1.5;
      }
    }
    
    .header-close {
      flex-shrink: 0;
      width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(139, 92, 246, 0.12);
      border: 1.5px solid rgba(139, 92, 246, 0.25);
      border-radius: 12px;
      cursor: pointer;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      
      .close-icon {
        font-size: 28px;
        font-weight: 300;
        line-height: 1;
        color: rgba(196, 181, 253, 0.7);
        transition: all 0.3s ease;
      }
      
      &:hover {
        background: rgba(239, 68, 68, 0.15);
        border-color: rgba(239, 68, 68, 0.35);
        transform: scale(1.05);
        
        .close-icon {
          color: #ef4444;
        }
      }
      
      &:active {
        transform: scale(0.95);
      }
    }
  }

  .ed-dialog__body,
  .el-dialog__body {
    padding: 32px !important;
    background: transparent;
  }

  .ed-dialog__footer,
  .el-dialog__footer {
    padding: 24px 32px 32px !important;
    background: linear-gradient(
      180deg,
      transparent 0%,
      rgba(15, 10, 30, 0.7) 100%
    );
    border-top: 1.5px solid rgba(168, 85, 247, 0.18);
    border-radius: 0 0 28px 28px;
    position: relative;
    
    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: 32px;
      right: 32px;
      height: 1px;
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(168, 85, 247, 0.3) 50%,
        transparent 100%
      );
    }

    .dialog-footer-premium {
      display: flex;
      justify-content: flex-end;
      gap: 14px;

      .ed-button,
      .el-button {
        min-width: 120px;
        height: 48px;
        font-size: 15px;
        font-weight: 600;
        border-radius: 14px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        display: flex;
        align-items: center;
        justify-content: center;

        &.btn-cancel-premium {
          background: rgba(139, 92, 246, 0.12) !important;
          border: 1.5px solid rgba(139, 92, 246, 0.35) !important;
          color: rgba(196, 181, 253, 0.95) !important;
          box-shadow: 0 2px 8px rgba(139, 92, 246, 0.15);

          &:hover {
            background: rgba(139, 92, 246, 0.22) !important;
            border-color: rgba(139, 92, 246, 0.5) !important;
            color: #c4b5fd !important;
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(139, 92, 246, 0.3);
          }

          &:active {
            transform: translateY(0);
          }
        }

        &.btn-save-premium {
          background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%) !important;
          border: none !important;
          color: #fff !important;
          box-shadow: 
            0 8px 24px rgba(124, 58, 237, 0.45),
            inset 0 1px 0 rgba(255, 255, 255, 0.25);

          &:hover {
            background: linear-gradient(135deg, #6d28d9 0%, #9333ea 100%) !important;
            transform: translateY(-2px) scale(1.02);
            box-shadow: 
              0 12px 36px rgba(124, 58, 237, 0.6),
              inset 0 1px 0 rgba(255, 255, 255, 0.3);
          }

          &:active {
            transform: translateY(0) scale(1);
          }
        }
      }
    }
  }
}

// 响应式适配
@media (max-width: 480px) {
  .system-person.system-person {
    min-width: 200px;
    max-width: 280px;
    padding: 8px;

    .popover {
      .info {
        padding: 12px;

        .info-text {
          .top {
            font-size: 14px;
          }
          .bottom {
            font-size: 11px;
          }
        }
      }

      .popover-item {
        min-height: 38px;
        padding: 8px 12px;

        .datasource-name {
          font-size: 13px;
        }
      }
    }
  }

  .system-language.system-language {
    min-width: 140px;
    max-width: 200px;

    .language-popover {
      .popover-item_language {
        min-height: 36px;
        padding: 8px 12px;

        .language-name {
          font-size: 13px;
        }
      }
    }
  }
}

// 密码对话框遮罩层 - 半透明深色背景，可以看到后面的界面
:deep(.ed-overlay):has(+ .pwd-dialog-premium),
:deep(.el-overlay):has(+ .pwd-dialog-premium),
:deep(.ed-overlay-dialog):has(+ .pwd-dialog-premium),
:deep(.el-overlay-dialog):has(+ .pwd-dialog-premium) {
  background-color: rgba(15, 10, 26, 0.75) !important;
  backdrop-filter: blur(6px) !important;
  -webkit-backdrop-filter: blur(6px) !important;
}

// 全局遮罩层样式（针对密码对话框）
.el-overlay:has(+ .pwd-dialog-premium),
.ed-overlay:has(+ .pwd-dialog-premium) {
  background-color: rgba(15, 10, 26, 0.75) !important;
  backdrop-filter: blur(6px) !important;
  -webkit-backdrop-filter: blur(6px) !important;
}

// 全局对话框遮罩层 - 半透明
:global(.el-overlay) {
  background-color: rgba(0, 0, 0, 0.65) !important;
}
</style>
