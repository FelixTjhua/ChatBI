/**
 * 数据预测功能验证工具
 * 用于检查数据是否满足预测条件
 */

export interface PredictionValidation {
  canPredict: boolean
  reason?: string
  suggestions?: string[]
  // 详细验证状态 - 用于 DataRequirementTooltip
  hasChart?: boolean
  hasData?: boolean
  validFormat?: boolean
  rowCount?: number
  hasTimeField?: boolean
  hasNumericField?: boolean
}

/**
 * 验证数据是否可以进行预测
 * @param record 聊天记录对象
 * @returns 验证结果
 */
export function validatePredictionData(record: any): PredictionValidation {
  // 初始化详细状态
  const hasChart = !!record?.chart
  const hasData = !!record?.data

  // 检查是否有图表
  if (!hasChart) {
    return {
      canPredict: false,
      reason: 'no_chart_data',
      hasChart: false,
      hasData: false,
      validFormat: false,
      rowCount: 0,
      hasTimeField: false,
      hasNumericField: false
    }
  }

  // 检查是否有数据 - 如果数据未加载，返回 loading 状态
  if (!hasData) {
    return {
      canPredict: false,
      reason: 'data_loading',
      hasChart: true,
      hasData: false,
      validFormat: false,
      rowCount: 0,
      hasTimeField: false,
      hasNumericField: false
    }
  }

  let data: any[] = []
  try {
    // 支持多种数据格式
    if (typeof record.data === 'string') {
      // 字符串格式：解析 JSON
      const parsed = JSON.parse(record.data)
      if (Array.isArray(parsed)) {
        data = parsed
      } else if (parsed && typeof parsed === 'object' && Array.isArray(parsed.data)) {
        // {fields: [...], data: [...]} 格式 - 需要转换
        if (Array.isArray(parsed.fields)) {
          const fields = parsed.fields
          const rows = parsed.data
          data = rows.map((row: any[]) => {
            const obj: any = {}
            fields.forEach((field: string, index: number) => {
              obj[field] = row[index]
            })
            return obj
          })
        } else {
          data = parsed.data
        }
      }
    } else if (Array.isArray(record.data)) {
      // 数组格式：直接使用
      data = record.data
    } else if (typeof record.data === 'object' && record.data !== null) {
      // 对象格式：提取 data 字段
      if (Array.isArray(record.data.data)) {
        // {fields: [...], data: [...]} 格式 - 需要转换为对象数组
        if (Array.isArray(record.data.fields)) {
          const fields = record.data.fields
          const rows = record.data.data
          data = rows.map((row: any[]) => {
            const obj: any = {}
            fields.forEach((field: string, index: number) => {
              obj[field] = row[index]
            })
            return obj
          })
        } else {
          data = record.data.data
        }
      } else {
        return {
          canPredict: false,
          reason: 'data_format_error',
          hasChart: true,
          hasData: true,
          validFormat: false,
          rowCount: 0,
          hasTimeField: false,
          hasNumericField: false
        }
      }
    } else {
      return {
        canPredict: false,
        reason: 'data_format_error',
        hasChart: true,
        hasData: true,
        validFormat: false,
        rowCount: 0,
        hasTimeField: false,
        hasNumericField: false
      }
    }
  } catch {
    return {
      canPredict: false,
      reason: 'data_format_error',
      hasChart: true,
      hasData: true,
      validFormat: false,
      rowCount: 0,
      hasTimeField: false,
      hasNumericField: false
    }
  }

  // 检查数据是否为空
  if (data.length === 0) {
    return {
      canPredict: false,
      reason: 'data_empty',
      suggestions: ['suggestion_query_returns_no_data'],
      hasChart: true,
      hasData: true,
      validFormat: true,
      rowCount: 0,
      hasTimeField: false,
      hasNumericField: false
    }
  }

  // 检查数据行数
  if (data.length < 3) {
    return {
      canPredict: false,
      reason: 'insufficient_rows',
      suggestions: ['suggestion_predict_more_data'],
      hasChart: true,
      hasData: true,
      validFormat: true,
      rowCount: data.length,
      hasTimeField: false,
      hasNumericField: false
    }
  }

  // 检查是否包含时间字段
  const firstRow = data[0]
  if (!firstRow || typeof firstRow !== 'object') {
    return {
      canPredict: false,
      reason: 'data_format_error',
      hasChart: true,
      hasData: true,
      validFormat: false,
      rowCount: data.length,
      hasTimeField: false,
      hasNumericField: false
    }
  }

  const hasTimeField = Object.keys(firstRow).some(key => {
    const value = firstRow[key]
    if (typeof value === 'string') {
      // 检查常见的日期格式
      // YYYY-MM-DD, YYYY/MM/DD, YYYY年MM月DD日, YYYY-MM, YYYY/MM, YYYY年MM月
      return /^\d{4}[-/]\d{1,2}([-/]\d{1,2})?/.test(value) || 
             /^\d{4}年\d{1,2}月(\d{1,2}日)?/.test(value) ||
             /^\d{1,2}[-/]\d{1,2}[-/]\d{4}/.test(value) // MM/DD/YYYY
    }
    return false
  })

  if (!hasTimeField) {
    return {
      canPredict: false,
      reason: 'no_time_field',
      suggestions: ['suggestion_need_time_field'],
      hasChart: true,
      hasData: true,
      validFormat: true,
      rowCount: data.length,
      hasTimeField: false,
      hasNumericField: false
    }
  }

  // 检查是否包含数值字段
  const hasNumericField = Object.keys(firstRow).some(key => {
    const value = firstRow[key]
    if (typeof value === 'number') {
      return true
    }
    if (typeof value === 'string') {
      // 尝试解析为数字
      const num = parseFloat(value)
      return !isNaN(num) && isFinite(num)
    }
    return false
  })

  if (!hasNumericField) {
    return {
      canPredict: false,
      reason: 'no_numeric_field',
      suggestions: ['suggestion_need_numeric_field'],
      hasChart: true,
      hasData: true,
      validFormat: true,
      rowCount: data.length,
      hasTimeField: true,
      hasNumericField: false
    }
  }

  // 所有条件都满足
  const suggestions: string[] = []
  if (data.length < 10) {
    suggestions.push('suggestion_predict_better_data')
  }

  return {
    canPredict: true,
    suggestions: suggestions.length > 0 ? suggestions : undefined,
    hasChart: true,
    hasData: true,
    validFormat: true,
    rowCount: data.length,
    hasTimeField: true,
    hasNumericField: true
  }
}

/**
 * 获取预测功能的友好提示信息
 * @param record 聊天记录对象
 * @param t 国际化函数
 * @returns 提示信息
 */
export function getPredictionTooltip(record: any, t: (key: string) => string): string {
  const validation = validatePredictionData(record)
  
  if (!validation.canPredict) {
    let message = `${t('chat.cannot_predict')}: ${t('chat.error_' + validation.reason)}`
    if (validation.suggestions && validation.suggestions.length > 0) {
      const translatedSuggestions = validation.suggestions.map(key => t('chat.' + key))
      message += `\n\n${t('chat.suggestions')}: ${translatedSuggestions.join('；')}`
    }
    return message
  }
  
  if (validation.suggestions && validation.suggestions.length > 0) {
    const translatedSuggestions = validation.suggestions.map(key => t('chat.' + key))
    return `${t('chat.data_predict_tip')}\n\n💡 ${translatedSuggestions.join('；')}`
  }
  
  return t('chat.data_predict_tip')
}
