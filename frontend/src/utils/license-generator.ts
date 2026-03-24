/**
 * ChatBI License Generator - 本地实现
 * 替代 chatbi_xpack_static 外部依赖
 * Copyright © 2025-2026 Felix Alvin Juandra (蔡威广)
 */

/**
 * Base64 编码
 */
const base64Encode = (text: string): string => {
  try {
    return btoa(
      encodeURIComponent(text).replace(/%([0-9A-F]{2})/g, (_, p1) =>
        String.fromCharCode(parseInt(p1, 16))
      )
    )
  } catch {
    return text
  }
}

/**
 * Base64 解码
 */
const base64Decode = (encoded: string): string => {
  try {
    return decodeURIComponent(
      atob(encoded)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
  } catch {
    return encoded
  }
}

/**
 * ChatBI License Generator 实现
 * 学术版 - 所有功能永久有效
 */
export const LicenseGeneratorImpl = {
  /**
   * 初始化
   */
  init: async (_baseUrl?: string): Promise<boolean> => {
    return true
  },

  /**
   * 获取 License 信息
   * 学术版始终返回有效状态
   */
  getLicense: () => {
    return {
      status: 'valid',
      type: 'academic',
      expireDate: '2099-12-31',
      features: ['all'],
    }
  },

  /**
   * 生成路由
   * 学术版无需额外路由处理
   */
  generateRouters: (_router: any) => {
    // 学术版无需处理
  },

  /**
   * 生成请求密钥
   */
  generate: (): string => {
    return `chatbi_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`
  },

  /**
   * 加密函数 - 使用 Base64 编码
   */
  chatbiEncrypt: (text: string): string => {
    if (!text) return ''
    return base64Encode(text)
  },

  /**
   * 解密函数 - 使用 Base64 解码
   */
  chatbiDecrypt: (encoded: string): string => {
    if (!encoded) return ''
    return base64Decode(encoded)
  },
}

// 初始化全局 LicenseGenerator
if (typeof window !== 'undefined') {
  ;(window as any).LicenseGenerator = LicenseGeneratorImpl
}

export default LicenseGeneratorImpl
