// src/services/request.ts
import axios, {
  AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
  type CancelTokenSource,
} from 'axios'

import { useCache } from '@/utils/useCache'
import { getLocale } from './utils'
import { useRouter } from 'vue-router'

// 延迟访问：避免在模块顶层调用 useRouter/useStore（必须在 setup() 或组件上下文中）
const getWsCache = () => useCache().wsCache
const getRouter = () => {
  try {
    return useRouter()
  } catch {
    return null
  }
}
// Response data structure
export interface ApiResponse<T = unknown> {
  code: number
  data: T
  message: string
  success: boolean
  [key: string]: any // Allow additional fields
}

// Extended request options
export interface RequestOptions {
  silent?: boolean // Silent mode (no error alerts)
  rawResponse?: boolean // Return raw Axios response
  customError?: boolean // Custom error handling
  retryCount?: number // Number of retry attempts
}

// Merged request configuration
export interface FullRequestConfig extends AxiosRequestConfig {
  requestOptions?: RequestOptions
}

// Custom error type
export interface RequestError<T = any> extends Error {
  config: FullRequestConfig
  code?: string
  request?: any
  response?: AxiosResponse<T>
  isAxiosError: boolean
}

class HttpService {
  private instance: AxiosInstance
  private cancelTokenSource: CancelTokenSource

  constructor(config?: AxiosRequestConfig) {
    this.cancelTokenSource = axios.CancelToken.source()
    this.instance = axios.create({
      baseURL: import.meta.env.VITE_API_BASE_URL,
      timeout: 100000,
      headers: {
        'Content-Type': 'application/json',
        ...config?.headers,
      },
      ...config,
    })

    this.setupInterceptors()
  }

  /* private cancelCurrentRequest(message: string) {
    this.cancelTokenSource.cancel(message)
    this.cancelTokenSource = axios.CancelToken.source()
  } */

  private setupInterceptors() {
    // Request interceptor
    this.instance.interceptors.request.use(
      async (config: InternalAxiosRequestConfig) => {
        const wsCache = getWsCache()
        // Add auth token
        const token = wsCache.get('user.token')
        if (token && config.headers) {
          config.headers['X-CHATBI-TOKEN'] = `Bearer ${token}`
        }
        const locale = getLocale()
        if (locale) {
          /* const mapping = {
            'zh-CN': 'zh-CN',
            en: 'en-US',
            tw: 'zh-TW',
          } */
          /* const val = mapping[locale] || locale */
          config.headers['Accept-Language'] = locale
        }
        if (config.url?.includes('/xpack_static/') && config.baseURL) {
          config.baseURL = config.baseURL.replace('/api/v1', '')
          // Skip auth for xpack_static requests
          return config
        }

        /* try {
          const request_key = LicenseGenerator.generate()
          config.headers['X-CHATBI-KEY'] = request_key
        } catch (e: any) {
          if (e?.message?.includes('offline')) {
            this.cancelCurrentRequest('license-key error detected')
            showLicenseKeyError()
          }
        } */

        // Request logging
        // console.log(`[Request] ${config.method?.toUpperCase()} ${config.url}`)

        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )
    // Response interceptor
    this.instance.interceptors.response.use(
      (response: AxiosResponse) => {
        // console.log(`[Response] ${response.config.url}`, response.data)

        // Return raw response if configured
        if ((response.config as FullRequestConfig).requestOptions?.rawResponse) {
          return response
        }

        // Handle business logic
        /* if (response.data?.success !== true) {
          return Promise.reject(response.data)
        } */
        if (response.data?.code === 0) {
          return response.data.data
        } else if (response.data?.code) {
          return Promise.reject(response.data)
        }
        return response.data
      },
      async (error: AxiosError) => {
        const config = error.config as FullRequestConfig & { __retryCount?: number }
        const requestOptions = config?.requestOptions || {}

        // Retry logic for specific status codes
        const shouldRetry =
          error.response?.status === 502 &&
          (config.__retryCount || 0) < (requestOptions.retryCount || 3)

        if (shouldRetry) {
          config.__retryCount = (config.__retryCount || 0) + 1

          // Exponential backoff
          await new Promise((resolve) => setTimeout(resolve, 1000 * (config.__retryCount || 1)))

          return this.instance.request(config)
        }

        // Unified error handling
        if (!requestOptions.customError && !requestOptions.silent) {
          this.handleError(error)
        }

        return Promise.reject(error)
      }
    )
  }

  private handleError(error: AxiosError) {
    let errorMessage = 'Request error'
    const wsCache = getWsCache()
    const router = getRouter()

    if (error.response) {
      switch (error.response.status) {
        case 400:
          errorMessage = 'Invalid request parameters'
          break
        case 401:
          errorMessage = error.response?.data
            ? error.response.data.toString()
            : 'Unauthorized, please login again'
          ElMessage({
            message: errorMessage,
            type: 'error',
            showClose: true,
          })
          setTimeout(() => {
            wsCache.delete('user.token')
            window.location.reload()
          }, 2000)
          return
        // break
        case 403:
          errorMessage = 'Access denied'
          break
        case 404:
          errorMessage = 'Resource not found'
          break
        case 500:
          errorMessage = 'Server error'
          break
        default:
          errorMessage = `Server responded with error: ${error.response.status}`
      }
      if (error?.response?.data) {
        errorMessage = error.response.data.toString()
      }
    } else if (error.request) {
      errorMessage = 'No response from server'
    } else if (axios.isCancel(error)) {
      errorMessage = 'Request canceled'
      return // Skip showing cancel messages
    } else {
      errorMessage = error['message'] || 'Unknown error'
    }

    // 通过UI组件展示错误信息
    ElMessage({
      message: errorMessage,
      type: 'error',
      showClose: true,
    })
  }

  // Cancel all pending requests
  public cancelRequests(message?: string) {
    this.cancelTokenSource.cancel(message)
    // Create new token source for future requests
    this.cancelTokenSource = axios.CancelToken.source()
  }

  // Base request method
  public request<T = any>(config: FullRequestConfig): Promise<T> {
    return this.instance.request({
      cancelToken: this.cancelTokenSource.token,
      ...config,
    })
  }

  // GET request
  public get<T = any>(url: string, config?: FullRequestConfig): Promise<T> {
    return this.request({ ...config, method: 'GET', url })
  }

  // POST request
  public post<T = any>(url: string, data?: any, config?: FullRequestConfig): Promise<T> {
    return this.request({ ...config, method: 'POST', url, data })
  }

  public async fetchStream(url: string, data?: any, controller?: AbortController): Promise<any> {
    const wsCache = getWsCache()
    const token = wsCache.get('user.token')
    const heads: any = {
      'Content-Type': 'application/json',
    }
    if (token) {
      heads['X-CHATBI-TOKEN'] = `Bearer ${token}`
    }

    /* try {
      const request_key = LicenseGenerator.generate()
      heads['X-CHATBI-KEY'] = request_key
    } catch (e: any) {
      if (e?.message?.includes('offline')) {
        controller?.abort('license-key error detected')
        showLicenseKeyError()
      }
    } */

    const real_url = import.meta.env.VITE_API_BASE_URL

    // fetchStream 添加超时控制（默认 5 分钟）
    // 原代码无超时，长时间无响应的请求会永远挂起，占用连接资源
    const STREAM_TIMEOUT_MS = 5 * 60 * 1000
    let timeoutId: ReturnType<typeof setTimeout> | null = null
    const internalController = controller || new AbortController()

    if (!controller) {
      // 仅在外部未提供 controller 时设置超时（外部 controller 由调用方管理生命周期）
      timeoutId = setTimeout(() => {
        internalController.abort('Stream request timeout')
      }, STREAM_TIMEOUT_MS)
    }

    let response: Response
    try {
      response = await fetch(real_url + url, {
        method: 'POST',
        headers: heads,
        body: JSON.stringify(data),
        signal: internalController.signal,
      })
    } catch (err: any) {
      if (timeoutId) clearTimeout(timeoutId)
      if (err?.name === 'AbortError' && !controller) {
        throw new Error('Stream request timeout: no response within 5 minutes')
      }
      throw err
    }
    if (timeoutId) clearTimeout(timeoutId)

    // fetchStream 处理 401 响应，重定向到登录页
    if (response.status === 401) {
      const wsCache = getWsCache()
      wsCache.delete('user.token')
      // 使用路由跳转替代 window.location.reload()
      try {
        const router = getRouter()
        router.push('/login')
      } catch {
        window.location.href = '/#/login'
      }
      throw new Error('Unauthorized')
    }

    // 处理非 401 的 HTTP 错误（如 500、502、503）
    // 原代码只处理了 401，其他错误码会静默返回，调用方无法感知失败
    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`)
    }

    return response
  }

  // PUT request
  public put<T = any>(url: string, data?: any, config?: FullRequestConfig): Promise<T> {
    return this.request({ ...config, method: 'PUT', url, data })
  }

  // DELETE request
  public delete<T = any>(url: string, config?: FullRequestConfig): Promise<T> {
    return this.request({ ...config, method: 'DELETE', url })
  }

  // PATCH request
  public patch<T = any>(url: string, data?: any, config?: FullRequestConfig): Promise<T> {
    return this.request({ ...config, method: 'PATCH', url, data })
  }

  // File upload
  public upload<T = any>(
    url: string,
    file: File,
    fieldName = 'file',
    config?: FullRequestConfig
  ): Promise<T> {
    const formData = new FormData()
    formData.append(fieldName, file)

    return this.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      ...config,
    })
  }

  // Download file
  public download(url: string, config?: FullRequestConfig): Promise<Blob> {
    return this.request<Blob>({
      ...config,
      method: 'GET',
      url,
      responseType: 'blob',
    })
  }

  public loadRemoteScript(url: string, id?: string, cb?: any): Promise<HTMLElement> {
    if (!url) {
      return Promise.reject(new Error('URL is required to load remote script'))
    }
    if (id && document.getElementById(id)) {
      return Promise.resolve(document.getElementById(id) as HTMLElement)
    }
    if (url.startsWith('/')) {
      const real_url = import.meta.env.VITE_API_BASE_URL.replace('/api/v1', '')
      url = real_url + url
    }

    // URL 白名单校验，防止加载恶意第三方脚本（XSS 风险）
    const allowedOrigins = [
      window.location.origin,
      import.meta.env.VITE_API_BASE_URL?.replace('/api/v1', '') || '',
    ].filter(Boolean)
    try {
      const parsedUrl = new URL(url, window.location.origin)
      if (!allowedOrigins.some((origin) => parsedUrl.href.startsWith(origin))) {
        return Promise.reject(
          new Error(`Blocked: script URL "${url}" is not in the allowed origins whitelist`)
        )
      }
    } catch {
      return Promise.reject(new Error(`Invalid script URL: "${url}"`))
    }

    return new Promise<HTMLElement>((resolve, reject) => {
      // 改用传统的script标签加载方式
      const script = document.createElement('script')
      script.src = url
      script.id = id || `remote-script-${Date.now()}`

      script.onload = () => {
        if (cb) cb()
        resolve(script)
      }

      script.onerror = () => {
        reject(new Error(`Failed to load script from ${url}`))
      }

      document.head.appendChild(script)
    })
  }
  /* public loadRemoteScript(url: string, id?: string, cb?: any): Promise<HTMLElement> {
    if (!url) {
      return Promise.reject(new Error('URL is required to load remote script'))
    }
    if (id && document.getElementById(id)) {
      return Promise.resolve(document.getElementById(id) as HTMLElement)
    }
    return new Promise<HTMLElement>((resolve, reject) => {
      this.get(url, {
        responseType: 'text',
        headers: {
          'Content-Type': 'application/javascript',
        },
      })
        .then((response: any) => {
          const script = document.createElement('script')
          script.textContent = response
          script.id = id || `remote-script-${Date.now()}`
          // Append script to head
          document.head.appendChild(script)
          if (cb) {
            cb()
          }
          resolve(script)
        })
        .catch((error: any) => {
          console.error(`Failed to load script from ${url}:`, error)
          reject(new Error(`Failed to load script from ${url}: ${error.message}`))
        })
    })
  } */
}

// Create singleton instance
export const request = new HttpService({
  baseURL: import.meta.env.VITE_API_BASE_URL,
})
/* 
const showLicenseKeyError = (msg?: string) => {
  ElMessageBox.confirm(t('license.error_tips'), {
    confirmButtonType: 'primary',
    tip: msg || t('license.offline_tips'),
    confirmButtonText: t('common.refresh'),
    cancelButtonText: t('common.cancel'),
    customClass: 'confirm-no_icon',
    autofocus: false,
    callback: (value: string) => {
      if (value === 'confirm') {
        window.location.reload()
      }
    },
  })
}
 */
