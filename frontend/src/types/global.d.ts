// 全局类型声明

// LicenseGenerator（xpack 企业版功能）
declare global {
  interface Window {
    LicenseGenerator?: {
      chatbiEncrypt: (text: string) => string
      chatbiDecrypt: (text: string) => string
      getLicense: () => any
    }
  }
  
  var LicenseGenerator: {
    chatbiEncrypt: (text: string) => string
    chatbiDecrypt: (text: string) => string
    getLicense: () => any
  } | undefined
}

export {}
