/**
 * 错误类型检测工具
 * 统一处理各种 API 错误的类型识别
 */

export type ErrorType =
  | 'quota'
  | 'timeout'
  | 'network'
  | 'api'
  | 'db'
  | 'sql'
  | 'parse'
  | 'datasource'
  | 'model'
  | 'unknown'
  | null

export interface ErrorInfo {
  type: ErrorType
  message: string
  isRetryable: boolean
}

/**
 * 检测错误类型
 * @param error 错误对象或错误消息
 * @returns 错误类型
 */
export function detectErrorType(error: any): ErrorType {
  if (!error) return null

  const errorStr = String(error?.message || error || '').toLowerCase()

  // 尝试解析 JSON 格式的错误
  let errorType: string | undefined
  try {
    if (typeof error === 'string' && error.trim().startsWith('{')) {
      const parsed = JSON.parse(error)
      errorType = parsed.type
    }
  } catch (e) {
    // 忽略解析错误
  }

  // 优先使用后端返回的错误类型
  if (errorType === 'db-connection-err') return 'db'
  if (errorType === 'exec-sql-err') return 'sql'
  if (errorType === 'api-quota-err') return 'quota'

  // API 余额/额度不足
  if (
    errorStr.includes('quota') ||
    errorStr.includes('insufficient') ||
    errorStr.includes('余额') ||
    errorStr.includes('额度') ||
    errorStr.includes('balance') ||
    errorStr.includes('预扣费') ||
    errorStr.includes('insufficient_user_quota') ||
    errorStr.includes('credit') ||
    errorStr.includes('billing')
  ) {
    return 'quota'
  }

  // 超时
  if (
    errorStr.includes('timeout') ||
    errorStr.includes('超时') ||
    errorStr.includes('timed out') ||
    errorStr.includes('deadline') ||
    errorStr.includes('request timeout')
  ) {
    return 'timeout'
  }

  // 网络错误
  if (
    errorStr.includes('network') ||
    errorStr.includes('fetch') ||
    errorStr.includes('connection refused') ||
    errorStr.includes('网络') ||
    errorStr.includes('econnrefused') ||
    errorStr.includes('enotfound') ||
    errorStr.includes('socket') ||
    errorStr.includes('unreachable')
  ) {
    return 'network'
  }

  // 数据源错误
  if (
    errorStr.includes('datasource') ||
    errorStr.includes('数据源') ||
    errorStr.includes('no available datasource')
  ) {
    return 'datasource'
  }

  // 模型错误
  // 'model' 匹配过于宽泛，'data model' 等也会误判
  // 改为更精确的匹配模式
  if (
    errorStr.includes('llm') ||
    errorStr.includes('模型') ||
    errorStr.includes('model not found') ||
    errorStr.includes('model error') ||
    errorStr.includes('no model') ||
    errorStr.includes('default model') ||
    (errorStr.includes('chat with id') && errorStr.includes('not found'))
  ) {
    return 'model'
  }

  // API 权限/认证错误
  if (
    errorStr.includes('permissiondenied') ||
    errorStr.includes('403') ||
    errorStr.includes('401') ||
    errorStr.includes('unauthorized') ||
    errorStr.includes('authentication') ||
    errorStr.includes('rate limit') ||
    errorStr.includes('ratelimit') ||
    (errorStr.includes('api') && errorStr.includes('error'))
  ) {
    return 'api'
  }

  // 数据库连接错误
  // 'connect db failed' 从 network 移到 db 分类
  // 数据库连接失败不是网络错误，应显示数据库相关的错误提示
  if (
    errorStr.includes('db-connection') ||
    errorStr.includes('database connection') ||
    errorStr.includes('数据库连接') ||
    errorStr.includes('connect db failed')
  ) {
    return 'db'
  }

  // SQL 执行错误
  if (
    errorStr.includes('exec-sql') ||
    errorStr.includes('execute sql') ||
    errorStr.includes('sql error') ||
    errorStr.includes('sql执行') ||
    errorStr.includes('cannot parse sql')
  ) {
    return 'sql'
  }

  // 解析错误
  if (
    errorStr.includes('parse') ||
    errorStr.includes('解析') ||
    errorStr.includes('cannot parse')
  ) {
    return 'parse'
  }

  return 'unknown'
}

/**
 * 获取错误的详细信息
 * @param error 错误对象或错误消息
 * @returns 错误详细信息
 */
export function getErrorInfo(error: any): ErrorInfo {
  const type = detectErrorType(error)
  const message = String(error?.message || error || '')

  // 判断是否可重试 - 大部分错误都可以重试
  const nonRetryableTypes: ErrorType[] = ['quota', 'api', 'datasource']
  const isRetryable = !nonRetryableTypes.includes(type)

  return {
    type,
    message,
    isRetryable,
  }
}

/**
 * 获取错误对应的图标
 * @param type 错误类型
 * @returns emoji 图标
 */
export function getErrorIcon(type: ErrorType): string {
  switch (type) {
    case 'quota':
      return '⚠️'
    case 'timeout':
      return '⏱️'
    case 'network':
      return '🌐'
    case 'api':
      return '🔑'
    case 'db':
      return '🔌'
    case 'sql':
      return '📝'
    case 'parse':
      return '🔍'
    case 'datasource':
      return '💾'
    case 'model':
      return '🤖'
    default:
      return '❌'
  }
}

/**
 * 获取错误对应的颜色主题类名
 * @param type 错误类型
 * @returns CSS 类名
 */
export function getErrorThemeClass(type: ErrorType): string {
  switch (type) {
    case 'quota':
      return 'error-quota'
    case 'timeout':
      return 'error-timeout'
    case 'network':
      return 'error-network'
    case 'api':
      return 'error-api'
    case 'db':
      return 'error-db'
    case 'sql':
      return 'error-sql'
    case 'parse':
      return 'error-parse'
    case 'datasource':
      return 'error-datasource'
    case 'model':
      return 'error-model'
    default:
      return 'error-unknown'
  }
}
