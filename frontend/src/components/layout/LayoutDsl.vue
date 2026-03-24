<script lang="ts" setup>
import { ref, computed, onUnmounted } from 'vue'
import { HomeFilled } from '@element-plus/icons-vue'
import Menu from './Menu.vue'
// import custom_small from '@/assets/svg/logo-custom_small.svg'
import Person from './Person.vue'
import LOGO_fold from '@/assets/LOGO-fold.svg'
import icon_side_fold_outlined from '@/assets/svg/icon_side-fold_outlined.svg'
import icon_side_expand_outlined from '@/assets/svg/icon_side-expand_outlined.svg'
import HelpButton from '@/components/tutorial/HelpButton.vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppearanceStoreWithOut } from '@/stores/appearance'
import { useEmitt } from '@/utils/useEmitt'

const router = useRouter()
const collapse = ref(false)
const collapseCopy = ref(false)
const appearanceStore = useAppearanceStoreWithOut()
let time: any
onUnmounted(() => {
  clearTimeout(time)
})
const handleCollapseChange = (val: any = true) => {
  collapseCopy.value = val
  clearTimeout(time)
  time = setTimeout(() => {
    collapse.value = val
  }, 100)
}
useEmitt({
  name: 'collapse-change',
  callback: handleCollapseChange,
})
const handleFoldExpand = () => {
  handleCollapseChange(!collapse.value)
}

const toWorkspace = () => {
  router.push('/')
}

const toChatIndex = () => {
  router.push('/chat/index')
}

const route = useRoute()
const showSysmenu = computed(() => {
  return route.path.includes('/system')
})
</script>

<template>
  <div class="system-layout">
    <div class="left-side" :class="collapse && 'left-side-collapse'">
      <div class="brand-identity" :class="{ collapsed: collapse }" @click="toChatIndex">
        <div class="logo-badge">
          <div class="badge-glow"></div>
          <div class="badge-inner">
            <LOGO_fold class="logo-svg"></LOGO_fold>
          </div>
        </div>
        <transition name="brand-fade">
          <div v-if="!collapse" class="brand-title">
            <span class="title-text">{{ showSysmenu ? 'ChatBI' : appearanceStore.name }}</span>
          </div>
        </transition>
      </div>
      <Menu :collapse="collapseCopy"></Menu>
      <div class="bottom">
        <div
          v-if="showSysmenu"
          class="back-to_workspace"
          :class="collapse && 'collapse'"
          @click="toWorkspace"
        >
          <el-icon :size="20">
            <HomeFilled />
          </el-icon>
          <span v-if="!collapse">{{ $t('workspace.return_to_workspace') }}</span>
        </div>
        <div class="personal-info">
          <Person :collapse="collapse" :in-sysmenu="showSysmenu"></Person>
          <el-icon size="20" class="fold" @click="handleFoldExpand">
            <icon_side_expand_outlined v-if="collapse"></icon_side_expand_outlined>
            <icon_side_fold_outlined v-else></icon_side_fold_outlined>
          </el-icon>
        </div>
      </div>
    </div>
    <div class="main-content">
      <router-view />
    </div>
  </div>
  <HelpButton />
</template>

<style lang="less" scoped>
.system-layout {
  width: 100vw;
  height: 100vh;
  background: #0f0a1a;
  display: flex;

  @keyframes rotate {
    0% {
      width: 240px;
    }
    100% {
      width: 64px;
    }
  }

  .left-side {
    width: 240px;
    height: 100%;
    padding: 16px;
    position: relative;
    min-width: 240px;
    background: linear-gradient(180deg, #0f0a1a 0%, #1a1033 40%, #1e1245 100%);
    overflow: hidden;

    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background:
        radial-gradient(ellipse 120% 80% at 0% 0%, rgba(139, 92, 246, 0.12) 0%, transparent 50%),
        radial-gradient(ellipse 80% 60% at 100% 100%, rgba(168, 85, 247, 0.08) 0%, transparent 50%);
      pointer-events: none;
    }

    &::after {
      content: '';
      position: absolute;
      top: 0;
      right: 0;
      width: 1px;
      height: 100%;
      background: linear-gradient(
        180deg,
        rgba(139, 92, 246, 0.2) 0%,
        rgba(139, 92, 246, 0.05) 50%,
        rgba(139, 92, 246, 0.2) 100%
      );
      pointer-events: none;
    }

    /* 品牌标识区域 - 完美平衡设计 */
    .brand-identity {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 10px 12px;
      margin-bottom: 20px;
      cursor: pointer;
      border-radius: 14px;
      background: rgba(139, 92, 246, 0.04);
      border: 1px solid rgba(139, 92, 246, 0.08);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      z-index: 1;

      &::before {
        content: '';
        position: absolute;
        inset: 0;
        border-radius: 14px;
        background: linear-gradient(
          135deg,
          rgba(139, 92, 246, 0.1) 0%,
          rgba(168, 85, 247, 0.05) 100%
        );
        opacity: 0;
        transition: opacity 0.3s ease;
      }

      /* Logo 徽章 */
      .logo-badge {
        position: relative;
        width: 40px;
        height: 40px;
        flex-shrink: 0;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);

        .badge-glow {
          position: absolute;
          inset: -6px;
          background: radial-gradient(
            circle,
            rgba(139, 92, 246, 0.4) 0%,
            rgba(139, 92, 246, 0.2) 40%,
            transparent 70%
          );
          border-radius: 50%;
          opacity: 0;
          filter: blur(10px);
          transition: all 0.3s ease;
        }

        .badge-inner {
          position: relative;
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(
            135deg,
            rgba(139, 92, 246, 0.15) 0%,
            rgba(168, 85, 247, 0.1) 100%
          );
          border-radius: 11px;
          box-shadow: 0 2px 8px rgba(139, 92, 246, 0.2);
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

          &::before {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(
              135deg,
              rgba(255, 255, 255, 0.1) 0%,
              transparent 60%
            );
            border-radius: 11px;
          }

          .logo-svg {
            position: relative;
            width: 24px;
            height: 24px;
            filter: drop-shadow(0 1px 4px rgba(139, 92, 246, 0.3));
            transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
            z-index: 1;
          }
        }
      }

      /* 品牌文字 */
      .brand-title {
        flex: 1;
        min-width: 0;
        margin-left: 12px;
        margin-right: 0;
        opacity: 1;
        transform: translateX(0);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        display: flex;
        align-items: center;

        .title-text {
          display: block;
          font-size: 18px;
          font-weight: 600;
          color: #fff;
          letter-spacing: -0.2px;
          line-height: 1.3;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          transition: all 0.3s ease;
        }
      }

      /* 悬停 - 展开状态 */
      &:not(.collapsed):hover {
        background: rgba(139, 92, 246, 0.06);
        border-color: rgba(139, 92, 246, 0.15);
        transform: translateY(-1px);

        &::before {
          opacity: 1;
        }

        .logo-badge {
          transform: scale(1.05);

          .badge-glow {
            opacity: 1;
          }

          .badge-inner {
            background: linear-gradient(
              135deg,
              rgba(139, 92, 246, 0.22) 0%,
              rgba(168, 85, 247, 0.15) 100%
            );
            box-shadow: 0 4px 12px rgba(139, 92, 246, 0.35);

            .logo-svg {
              transform: rotate(-5deg) scale(1.08);
            }
          }
        }

        .brand-title .title-text {
          color: #e9d5ff;
        }
      }

      /* 点击 - 展开状态 */
      &:not(.collapsed):active {
        transform: translateY(0);
      }

      /* ========== 折叠状态 ========== */
      &.collapsed {
        justify-content: center;
        width: 52px;
        height: 52px;
        padding: 0;
        margin-bottom: 16px;
        border-radius: 14px;

        &::before {
          border-radius: 14px;
        }

        .logo-badge {
          width: 52px;
          height: 52px;

          .badge-inner {
            border-radius: 14px;

            .logo-svg {
              width: 30px;
              height: 30px;
            }
          }
        }

        .brand-title {
          opacity: 0;
          transform: translateX(-8px);
          pointer-events: none;
          margin-left: 0;
          margin-right: 0;
          width: 0;
        }

        /* 悬停 - 折叠状态 */
        &:hover {
          background: rgba(139, 92, 246, 0.08);
          border-color: rgba(139, 92, 246, 0.2);
          transform: translateY(-1px) scale(1.02);

          &::before {
            opacity: 1;
          }

          .logo-badge {
            .badge-glow {
              opacity: 1;
            }

            .badge-inner {
              background: linear-gradient(
                135deg,
                rgba(139, 92, 246, 0.25) 0%,
                rgba(168, 85, 247, 0.18) 100%
              );
              box-shadow: 0 4px 16px rgba(139, 92, 246, 0.4);

              .logo-svg {
                transform: rotate(360deg) scale(1.1);
              }
            }
          }
        }

        /* 点击 - 折叠状态 */
        &:active {
          transform: translateY(0) scale(1);
        }
      }
    }

    /* 品牌文字动画 */
    .brand-fade-enter-active {
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) 0.05s;
    }

    .brand-fade-leave-active {
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .brand-fade-enter-from,
    .brand-fade-leave-to {
      opacity: 0;
      transform: translateX(-8px);
    }

    .bottom {
      position: absolute;
      bottom: 20px;
      left: 16px;
      font-weight: 400;
      font-size: 14px;
      line-height: 22px;
      width: calc(100% - 32px);
      z-index: 1;

      .back-to_workspace {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        padding: 0 16px;
        border-radius: 14px;
        height: 52px;
        width: 100%;
        max-width: 100%;
        box-sizing: border-box;
        cursor: pointer;
        color: rgba(255, 255, 255, 0.9);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        background: rgba(139, 92, 246, 0.1);
        border: 1px solid rgba(139, 92, 246, 0.15);
        font-size: 15px;
        font-weight: 500;
        white-space: nowrap;
        margin-bottom: 16px;

        &:hover {
          background: rgba(139, 92, 246, 0.2);
          border-color: rgba(139, 92, 246, 0.3);
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(139, 92, 246, 0.25);
        }

        &:active {
          background: rgba(139, 92, 246, 0.25);
          transform: translateY(0);
        }

        .ed-icon,
        .el-icon {
          flex-shrink: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          color: rgba(168, 85, 247, 0.95);
        }

        span {
          line-height: 1;
          display: flex;
          align-items: center;
        }

        &.collapse {
          width: 52px !important;
          max-width: 52px !important;
          padding: 0;
          justify-content: center;
          
          .ed-icon,
          .el-icon {
            margin: 0;
          }
        }
      }

      .personal-info {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 16px;
        padding: 0;
        background: transparent;
        border-radius: 0;
        border: none;
        position: relative;
        overflow: visible;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

        .fold {
          cursor: pointer;
          flex-shrink: 0;
          border-radius: 14px;
          width: 52px;
          height: 52px;
          min-width: 52px;
          color: rgba(196, 181, 253, 0.85);
          background: linear-gradient(
            135deg,
            rgba(139, 92, 246, 0.15) 0%,
            rgba(168, 85, 247, 0.1) 100%
          );
          border: none;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
          z-index: 1;

          .ed-icon {
            font-size: 20px;
          }

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

          &:hover,
          &:focus {
            background: linear-gradient(
              135deg,
              rgba(139, 92, 246, 0.22) 0%,
              rgba(168, 85, 247, 0.15) 100%
            );
            color: #e9d5ff;
            transform: translateY(-2px) scale(1.05);
            box-shadow: 0 4px 16px rgba(139, 92, 246, 0.35);

            &::before {
              opacity: 1;
            }
          }

          &:active {
            background: rgba(139, 92, 246, 0.3);
            transform: translateY(0) scale(0.98);
          }
        }
      }
    }

    &.left-side-collapse {
      width: 64px;
      min-width: 64px;
      padding: 16px 6px;

      .ed-menu--collapse {
        --ed-menu-icon-width: 52px;
        --ed-menu-item-height: 52px;
        width: 100% !important;
      }

      .bottom {
        left: 6px;
        width: calc(100% - 12px);
        display: flex;
        flex-direction: column;
        align-items: center;

        .ed-icon {
          margin-right: 0;
        }

        .back-to_workspace {
          width: 52px;
          height: 52px;
          padding: 0;
          justify-content: center;
          border-radius: 14px;
        }
      }

      .personal-info {
        flex-direction: column;
        gap: 8px;
        padding: 0;
        align-items: center;
        width: 100%;

        .default-avatar {
          margin: 0;
        }

        .fold {
          margin: 0;
          width: 52px;
          height: 52px;
          border-radius: 14px;
        }
      }
    }
  }

  /* 主内容区域 - 全深色，无白色卡片 */
  .main-content {
    flex: 1;
    height: 100%;
    background: #0f0a1a;
    overflow: auto;

    /* 深色滚动条 */
    &::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }

    &::-webkit-scrollbar-track {
      background: rgba(139, 92, 246, 0.05);
      border-radius: 3px;
    }

    &::-webkit-scrollbar-thumb {
      background: rgba(139, 92, 246, 0.3);
      border-radius: 3px;

      &:hover {
        background: rgba(139, 92, 246, 0.5);
      }
    }
  }
}
</style>

<style lang="less">
/* 全局样式 - 深色主题 */
.system-layout {
  background: #0f0a1a;
}

/* 只在折叠状态下强制统一按钮大小 */
.system-layout .left-side-collapse .ed-menu-vertical .ed-menu-item,
.system-layout .left-side-collapse .ed-menu-vertical .ed-sub-menu__title {
  width: 52px !important;
  height: 52px !important;
  min-width: 52px !important;
  max-width: 52px !important;
  min-height: 52px !important;
  max-height: 52px !important;
  line-height: 52px !important;
  padding: 0 !important;
  margin: 0 auto 6px !important;
  border-radius: 14px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  overflow: hidden !important;
}

/* 只在折叠状态下隐藏文字 */
.system-layout .left-side-collapse .ed-menu-vertical .ed-menu-item span,
.system-layout .left-side-collapse .ed-menu-vertical .ed-sub-menu__title span {
  display: none !important;
  width: 0 !important;
  height: 0 !important;
  opacity: 0 !important;
  visibility: hidden !important;
}

/* 只在折叠状态下图标居中 */
.system-layout .left-side-collapse .ed-menu-vertical .ed-menu-item .ed-icon,
.system-layout .left-side-collapse .ed-menu-vertical .ed-sub-menu__title .ed-icon {
  margin: 0 auto !important;
}

/* 只在折叠状态下统一底部按钮大小 */
.system-layout .left-side-collapse .bottom .fold,
.system-layout .left-side-collapse .bottom .back-to_workspace,
.system-layout .left-side-collapse .bottom .personal-info .person {
  width: 52px !important;
  height: 52px !important;
  min-width: 52px !important;
  max-width: 52px !important;
  min-height: 52px !important;
  max-height: 52px !important;
  border-radius: 14px !important;
}

</style>
