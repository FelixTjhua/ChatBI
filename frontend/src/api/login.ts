import { request } from '@/utils/request'
import { LicenseGeneratorImpl } from '@/utils/license-generator'
import { i18n } from '@/i18n'

const t = i18n.global.t

const encrypt = (val: string) => {
  return (
    (window as any).LicenseGenerator?.chatbiEncrypt?.(val) ||
    LicenseGeneratorImpl.chatbiEncrypt(val)
  )
}

// 友好的错误消息映射
const getErrorMessage = (error: any, defaultMessage: string): string => {
  // 超时错误
  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
    return t('common.request_timeout')
  }
  
  // HTTP 状态码错误
  if (error.response) {
    const status = error.response.status
    const detail = error.response.data?.detail
    
    switch (status) {
      case 400:
        return detail || t('common.param_error')
      case 401:
        return t('common.auth_error')
      case 403:
        return t('common.access_denied')
      case 404:
        return t('common.service_not_found')
      case 409:
        return detail || t('common.conflict_error')
      case 422:
        return detail || t('common.validation_error')
      case 500:
        return t('common.server_error')
      case 502:
        return t('common.gateway_error')
      case 503:
        return t('common.service_unavailable')
      default:
        return detail || defaultMessage
    }
  }
  
  // 网络错误
  if (error.message === 'Network Error') {
    return t('common.network_error')
  }
  
  // 其他错误
  return error.message || defaultMessage
}

export const AuthApi = {
  login: async (credentials: { username: string; password: string }) => {
    try {
      const entryCredentials = {
        username: encrypt(credentials.username),
        password: encrypt(credentials.password),
      }
      
      const response = await request.post<{
        data: any
        token: string
      }>('/login/access-token', entryCredentials, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        timeout: 10000, // 10秒超时
      })
      
      return response
    } catch (error: any) {
      const message = getErrorMessage(error, t('common.login_failed'))
      throw new Error(message)
    }
  },

  register: async (data: { username: string; password: string; email: string; name: string }) => {
    try {
      const response = await request.post('/login/register', {
        username: encrypt(data.username),
        password: encrypt(data.password),
        email: encrypt(data.email),
        name: encrypt(data.name),
      }, {
        timeout: 10000, // 10秒超时
      })
      
      return response
    } catch (error: any) {
      const message = getErrorMessage(error, t('common.register_failed'))
      throw new Error(message)
    }
  },

  logout: (data: any) => request.post('/login/logout', data),
  info: () => request.get('/user/info'),
}
