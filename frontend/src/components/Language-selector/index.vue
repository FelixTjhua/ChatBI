<template>
  <el-dropdown trigger="hover" popper-class="language-dropdown-popper" @command="changeLanguage">
    <div class="lang-switch">
      <span class="lang-icon">🌐</span>
      <span class="lang-text">{{ displayLanguageName }}</span>
      <el-icon class="el-icon--right">
        <ArrowDown />
      </el-icon>
    </div>
    <template #dropdown>
      <el-dropdown-menu class="language-dropdown-menu">
        <el-dropdown-item
          v-for="option in languageOptions"
          :key="option.value"
          :command="option.value"
          :class="{ 'selected-lang': selectedLanguage === option.value }"
        >
          <span class="lang-flag">{{ option.flag }}</span>
          <span class="lang-label">{{ option.label }}</span>
          <span v-if="selectedLanguage === option.value" class="check-icon">✓</span>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'
import { ArrowDown } from '@element-plus/icons-vue'
import { userApi } from '@/api/auth'

const { t, locale } = useI18n()
const userStore = useUserStore()

const languageOptions = computed(() => [
  { value: 'zh-CN', label: '简体中文', flag: '🇨🇳' },
  { value: 'en', label: 'English', flag: '🇺🇸' },
])

const selectedLanguage = computed(() => {
  return userStore.language
})

const displayLanguageName = computed(() => {
  const current = languageOptions.value.find((item) => item.value === selectedLanguage.value)
  return current?.label ?? t('common.language')
})

const changeLanguage = (lang: string) => {
  locale.value = lang
  userStore.setLanguage(lang)

  const param = {
    language: lang,
  }
  userApi.language(param)
}
</script>

<style scoped lang="less">
.lang-switch {
  display: flex;
  align-items: center;
  cursor: pointer;
  color: rgba(248, 250, 252, 0.9);
  padding: 8px 12px;
  border-radius: 10px;
  transition: all 0.2s ease;
  gap: 8px;

  &:hover {
    background: rgba(139, 92, 246, 0.15);
    color: #ffffff;
  }

  .lang-icon {
    font-size: 16px;
  }

  .lang-text {
    font-size: 14px;
    font-weight: 500;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .el-icon--right {
    font-size: 12px;
    opacity: 0.7;
    transition: transform 0.2s ease;
  }

  &:hover .el-icon--right {
    transform: rotate(180deg);
  }
}
</style>

<style lang="less">
// 语言选择下拉菜单全局样式
.language-dropdown-popper {
  .el-dropdown-menu {
    background: linear-gradient(
      165deg,
      rgba(45, 38, 65, 0.98) 0%,
      rgba(35, 28, 55, 0.98) 100%
    ) !important;
    border: 1px solid rgba(139, 92, 246, 0.25) !important;
    border-radius: 14px !important;
    padding: 8px !important;
    box-shadow:
      0 12px 40px rgba(0, 0, 0, 0.5),
      0 4px 16px rgba(139, 92, 246, 0.15),
      inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
    backdrop-filter: blur(20px);
    min-width: 180px !important;

    .el-dropdown-menu__item {
      display: flex !important;
      align-items: center !important;
      gap: 12px !important;
      padding: 12px 16px !important;
      border-radius: 10px !important;
      color: rgba(248, 250, 252, 0.9) !important;
      font-size: 14px !important;
      font-weight: 500 !important;
      transition: all 0.2s ease !important;
      margin: 2px 0 !important;

      .lang-flag {
        font-size: 18px;
        flex-shrink: 0;
      }

      .lang-label {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .check-icon {
        color: #a78bfa;
        font-size: 14px;
        font-weight: 700;
        flex-shrink: 0;
      }

      &:hover {
        background: rgba(139, 92, 246, 0.2) !important;
        color: #ffffff !important;
        transform: translateX(2px);
      }

      &.selected-lang {
        background: rgba(139, 92, 246, 0.15) !important;
        color: #c4b5fd !important;

        &:hover {
          background: rgba(139, 92, 246, 0.25) !important;
        }
      }
    }
  }
}
</style>
