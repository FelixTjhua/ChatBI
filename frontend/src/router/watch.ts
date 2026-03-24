import { useCache } from '@/utils/useCache'
import { useAppearanceStoreWithOut } from '@/stores/appearance'
import { useUserStore } from '@/stores/user'
import type { Router } from 'vue-router'

const appearanceStore = useAppearanceStoreWithOut()
const userStore = useUserStore()
const { wsCache } = useCache()
// 移除未使用的 whiteList 变量
export const watchRouter = (router: Router) => {
  router.beforeEach(async (to: any, _from: any, next: any) => {
    await appearanceStore.setAppearance()
    
    // 获取token
    const token = wsCache.get('user.token')
    
    // 检查 token 过期时间，过期则清除并跳转登录页
    // 原代码只检查 token 是否存在，不检查有效性，
    const tokenExp = wsCache.get('user.exp')
    const isTokenExpired = tokenExp && Number(tokenExp) > 0 && Date.now() / 1000 > Number(tokenExp)
    
    // 如果访问登录页
    if (to.path.startsWith('/login')) {
      // 已登录且 token 未过期则跳转到chat
      if (token && !isTokenExpired && userStore.getUid) {
        next('/chat/index')
        return
      }
      // 未登录则正常访问登录页
      next()
      return
    }
    
    // 如果没有token或token已过期，跳转到登录页
    if (!token || isTokenExpired) {
      if (isTokenExpired) {
        wsCache.delete('user.token')
      }
      next('/login')
      return
    }
    
    // 如果有token但没有用户信息，获取用户信息
    if (!userStore.getUid) {
      try {
        await userStore.info()
      } catch (e) {
        // 获取用户信息失败，清除token并跳转到登录页
        wsCache.delete('user.token')
        next('/login')
        return
      }
    }
    
    // 如果访问根路径，跳转到chat
    if (to.path === '/') {
      next('/chat/index')
      return
    }
    
    // 权限检查：非管理员访问系统页面，或非空间管理员访问设置页面
    if (accessCrossPermission(to)) {
      next('/chat/index')
      return
    }
    
    // 其他情况正常放行
    next()
  })
}

const accessCrossPermission = (to: any) => {
  if (!to?.path) return false
  // /system 路由下包含用户管理、模型配置、设置等子页面
  if (to.path.startsWith('/system')) {
    // 设置页面（外观、认证）需要空间管理员权限
    if (to.path.startsWith('/system/setting')) {
      return !userStore.isSpaceAdmin
    }
    // 其他系统页面（用户管理、模型配置等）需要管理员权限
    return !userStore.isAdmin
  }
  return false
}
