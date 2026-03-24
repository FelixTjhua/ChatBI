/**
 * ChatBI 加密工具模块
 * Copyright © 2025-2026 Felix Alvin Juandra (蔡威广)
 */

/**
 * ChatBI 加密函数
 * @param text 要加密的文本
 * @returns 加密后的文本
 */
export const chatbiEncrypt = (text: string): string => {
  // 使用内部加密实现
  if (typeof LicenseGenerator !== 'undefined' && LicenseGenerator?.chatbiEncrypt) {
    return LicenseGenerator.chatbiEncrypt(text)
  }
  // 社区版使用 UTF-8 安全的 Base64 编码替代明文返回
  // 生产环境建议配合 HTTPS 使用
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
 * ChatBI 解密函数
 * @param text 要解密的文本
 * @returns 解密后的文本
 */
export const chatbiDecrypt = (text: string): string => {
  // 使用内部解密实现
  if (typeof LicenseGenerator !== 'undefined' && LicenseGenerator?.chatbiDecrypt) {
    return LicenseGenerator.chatbiDecrypt(text)
  }
  // 社区版 Base64 解码（与 chatbiEncrypt 对应，正确处理 UTF-8）
  try {
    return decodeURIComponent(
      atob(text)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
  } catch {
    // 兼容旧数据：如果解码失败，说明是旧版明文存储的数据，直接返回
    return text
  }
}
