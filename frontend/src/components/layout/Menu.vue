<script lang="ts" setup>
import { computed } from 'vue'
import { ElMenu } from 'element-plus-secondary'
import { useRoute, useRouter } from 'vue-router'
import MenuItem from './MenuItem.vue'
import { useUserStore } from '@/stores/user'
import { routes } from '@/router'
const userStore = useUserStore()
const router = useRouter()
defineProps({
  collapse: Boolean,
})

const route = useRoute()
// const menuList = computed(() => route.matched[0]?.children || [])
const activeMenu = computed(() => route.path)
/* const activeIndex = computed(() => {
  const arr = route.path.split('/')
  return arr[arr.length - 1]
}) */
const showSysmenu = computed(() => {
  return route.path.includes('/system')
})

const formatRoute = (arr: any, parentPath = '') => {
  return arr.map((element: any) => {
    let children: any = []
    const path = `${parentPath ? parentPath + '/' : ''}${element.path}`
    if (element.children?.length) {
      children = formatRoute(element.children, path)
    }
    return {
      ...element,
      path,
      children,
    }
  })
}

const routerList = computed(() => {
  if (showSysmenu.value) {
    const [sysRouter] = formatRoute(routes.filter((route) => route.path.includes('/system')))
    // 显示系统管理菜单项（只有管理员能访问）
    const allowedPaths = ['user', 'prompt', 'sql-example', 'terminology']
    return sysRouter.children.filter((child: any) => {
      return allowedPaths.includes(child.path.split('/').pop())
    })
  }
  
  // 只显示4个主要菜单：智能对话、数据源、仪表板、模型配置
  const mainMenuPaths = ['/chat/index', '/ds/index', '/dashboard/index', '/model/index']
  
  const list = router.getRoutes().filter((route) => {
    return mainMenuPaths.includes(route.path) && !route.meta?.hidden
  })

  return list
})
</script>

<template>
  <el-menu 
    :default-active="activeMenu" 
    class="el-menu-demo ed-menu-vertical" 
    :collapse="collapse"
    :collapse-transition="false"
    :popper-append-to-body="false"
    :popper-offset="0"
    :show-timeout="999999"
    :hide-timeout="0"
  >
    <MenuItem v-for="menu in routerList" :key="menu.path" :menu="menu"></MenuItem>
  </el-menu>
</template>

<style lang="less">
.ed-menu-vertical {
  --ed-menu-item-height: 52px;
  --ed-menu-bg-color: transparent;
  --ed-menu-base-level-padding: 8px;
  border-right: none;
  list-style: none !important;
  
  .ed-menu-item {
    height: 52px !important;
    line-height: 52px !important;
    border-radius: 14px !important;
    margin-bottom: 6px;
    padding: 0 16px !important;
    display: flex !important;
    align-items: center !important;
    color: rgba(255, 255, 255, 0.85) !important;
    transition: background-color 0.3s ease, color 0.3s ease;
    list-style: none !important;
    
    &:hover {
      background-color: rgba(168, 85, 247, 0.15) !important;
      color: #fff !important;
    }
    
    &.is-active {
      background: linear-gradient(135deg, rgba(168, 85, 247, 0.25) 0%, rgba(147, 51, 234, 0.25) 100%) !important;
      border: 1px solid rgba(168, 85, 247, 0.3) !important;
      box-shadow: 0 4px 12px rgba(168, 85, 247, 0.2) !important;
      color: #fff !important;
      font-weight: 600;
      
      .ed-icon {
        color: #a855f7 !important;
      }
    }
    
    .ed-icon {
      margin-right: 12px;
      font-size: 20px;
      color: rgba(168, 85, 247, 0.9) !important;
    }
    
    span {
      font-size: 15px;
      font-weight: 500;
    }
  }

  .ed-sub-menu {
    list-style: none !important;
    
    .ed-sub-menu__title {
      height: 52px !important;
      line-height: 52px !important;
      border-radius: 14px !important;
      padding: 0 16px !important;
      display: flex !important;
      align-items: center !important;
      color: rgba(255, 255, 255, 0.85) !important;
      transition: background-color 0.3s ease, color 0.3s ease;
      margin-bottom: 6px;
      list-style: none !important;
      
      &:hover {
        background-color: rgba(168, 85, 247, 0.15) !important;
        color: #fff !important;
      }
      
      .ed-icon {
        margin-right: 12px;
        font-size: 20px;
        color: rgba(168, 85, 247, 0.9) !important;
      }
      
      span {
        font-size: 15px;
        font-weight: 500;
      }
    }
    
    &.is-active:not(.is-opened) {
      .ed-sub-menu__title {
        background: linear-gradient(135deg, rgba(168, 85, 247, 0.25) 0%, rgba(147, 51, 234, 0.25) 100%) !important;
        border: 1px solid rgba(168, 85, 247, 0.3) !important;
        box-shadow: 0 4px 12px rgba(168, 85, 247, 0.2) !important;
        color: #fff !important;
        font-weight: 600;
        
        .ed-icon {
          color: #a855f7 !important;
        }
      }
    }

    &.is-active.is-opened {
      .ed-sub-menu__title {
        color: #fff !important;
        font-weight: 600;
        background-color: rgba(168, 85, 247, 0.1) !important;
        
        .ed-icon {
          color: #a855f7 !important;
        }
      }
    }
  }

  // Element Plus 折叠状态 - 保持与展开状态相同的大小 - 使用更强的选择器
  &.ed-menu--collapse,
  &.el-menu--collapse {
    width: 64px !important;
    
    .ed-menu-item,
    .el-menu-item,
    .ed-sub-menu__title,
    .el-sub-menu__title {
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
      
      .ed-icon,
      .el-icon {
        margin: 0 auto !important;
        font-size: 20px !important;
      }
      
      span {
        display: none !important;
        width: 0 !important;
        height: 0 !important;
        opacity: 0 !important;
        visibility: hidden !important;
      }
    }
    
    .ed-sub-menu__icon-arrow,
    .el-sub-menu__icon-arrow {
      display: none !important;
    }
    
    // 禁用 tooltip
    .ed-tooltip__trigger,
    .el-tooltip__trigger {
      pointer-events: none !important;
    }
  }
}

// 全局隐藏折叠菜单的 tooltip 和 popper
.ed-menu--collapse {
  // 禁用所有 popper 触发
  .ed-menu-item,
  .ed-sub-menu__title {
    pointer-events: auto !important;
    
    // 禁用 tooltip
    &::before,
    &::after {
      display: none !important;
    }
  }
  
  // 禁用子菜单的 popper - 更强的规则
  .ed-sub-menu {
    .ed-sub-menu__title {
      cursor: pointer !important;
    }
    
    // 完全禁用子菜单展开 - 无论何时
    .ed-menu--popup {
      display: none !important;
      visibility: hidden !important;
      opacity: 0 !important;
      pointer-events: none !important;
    }
  }
}

// 全局隐藏所有菜单相关的 popper - 更强的选择器
.ed-popper.is-light.ed-menu--popup,
.el-popper.is-light.el-menu--popup,
.ed-menu--popup-container {
  display: none !important;
  visibility: hidden !important;
  opacity: 0 !important;
  pointer-events: none !important;
  z-index: -9999 !important;
}

// 针对折叠状态的菜单，完全禁用 popper
.ed-menu--collapse + .ed-popper,
.ed-menu--collapse + .el-popper {
  display: none !important;
  visibility: hidden !important;
  opacity: 0 !important;
  pointer-events: none !important;
}

// 隐藏所有菜单相关的 tooltip
.ed-tooltip__popper[role="tooltip"] {
  &:has(.ed-menu-item),
  &:has(.ed-sub-menu__title) {
    display: none !important;
  }
}

.ed-popper.is-light:has(.ed-menu--popup) {
  border: 1px solid rgba(168, 85, 247, 0.2);
  border-radius: 14px;
  box-shadow: 0px 8px 24px rgba(168, 85, 247, 0.15);
  background: rgba(30, 27, 75, 0.98);
  backdrop-filter: blur(10px);
  overflow: hidden;
}

.ed-menu--popup {
  padding: 8px;
  background: transparent;
  list-style: none !important;

  .ed-menu-item {
    padding: 12px 16px !important;
    height: 48px !important;
    line-height: 48px !important;
    border-radius: 12px;
    color: rgba(255, 255, 255, 0.85) !important;
    list-style: none !important;
    display: flex !important;
    align-items: center !important;
    
    &:hover {
      background-color: rgba(168, 85, 247, 0.15) !important;
      color: #fff !important;
    }
    
    &.is-active {
      background: linear-gradient(135deg, rgba(168, 85, 247, 0.25) 0%, rgba(147, 51, 234, 0.25) 100%) !important;
      border: 1px solid rgba(168, 85, 247, 0.3) !important;
      color: #fff !important;
      font-weight: 600;
    }
  }
}

.ed-sub-menu {
  .subTitleMenu {
    display: none;
  }
}

.ed-menu--popup-container .subTitleMenu {
  color: rgba(255, 255, 255, 0.6) !important;
  pointer-events: none;
}
</style>
