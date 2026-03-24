/**
 * 数据分析功能验证工具
 * 用于检查数据是否适合进行分析，并提供质量评估
 */

export interface AnalysisValidation {
  canAnalyze: boolean
  reason?: string
  suggestions?: string[]
  quality?: 'excellent' | 'good' | 'fair' | 'poor'
  dataQualityScore?: number  // 0-100
  // 详细验证状态 - 用于 DataRequirementTooltip
  hasChart?: boolean
  hasData?: boolean
  validFormat?: boolean
  rowCount?: number
}

/**
 * 验证数据是否可以进行分析
 * @param record 聊天记录对象
 * @returns 验证结果
 */
export function validateAnalysisData(record: any): AnalysisValidation {
  // 初始化详细状态
  const hasChart = !!record?.chart
  const hasData = !!record?.data

  // 检查是否有图表
  if (!hasChart) {
    return {
      canAnalyze: false,
      reason: 'no_chart_data',
      hasChart: false,
      hasData: false,
      validFormat: false,
      rowCount: 0
    }
  }

  // 检查是否有数据 - 如果数据未加载，返回 loading 状态
  if (!hasData) {
    return {
      canAnalyze: false,
      reason: 'data_loading',
      hasChart: true,
      hasData: false,
      validFormat: false,
      rowCount: 0
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
        // {fields: [...], data: [...]} 格式
        data = parsed.data
      }
    } else if (Array.isArray(record.data)) {
      // 数组格式：直接使用
      data = record.data
    } else if (typeof record.data === 'object' && record.data !== null) {
      // 对象格式：提取 data 字段
      if (Array.isArray(record.data.data)) {
        // {fields: [...], data: [...]} 格式
        data = record.data.data
      } else {
        return {
          canAnalyze: false,
          reason: 'data_format_error',
          hasChart: true,
          hasData: true,
          validFormat: false,
          rowCount: 0
        }
      }
    } else {
      return {
        canAnalyze: false,
        reason: 'data_format_error',
        hasChart: true,
        hasData: true,
        validFormat: false,
        rowCount: 0
      }
    }
  } catch {
    return {
      canAnalyze: false,
      reason: 'data_format_error',
      hasChart: true,
      hasData: true,
      validFormat: false,
      rowCount: 0
    }
  }

  // 检查数据是否为空
  if (data.length === 0) {
    return {
      canAnalyze: false,
      reason: 'data_empty',
      suggestions: ['suggestion_query_returns_no_data'],
      hasChart: true,
      hasData: true,
      validFormat: true,
      rowCount: 0
    }
  }

  // 数据质量评估
  let quality: 'excellent' | 'good' | 'fair' | 'poor' = 'poor'
  let dataQualityScore = 0
  const suggestions: string[] = []

  // 1. 数据行数评分（40分）
  let rowScore = 0
  if (data.length >= 100) {
    rowScore = 40
    quality = 'excellent'
  } else if (data.length >= 50) {
    rowScore = 35
    quality = 'good'
    suggestions.push('suggestion_data_good')
  } else if (data.length >= 20) {
    rowScore = 25
    quality = 'fair'
    suggestions.push('suggestion_more_data')
  } else if (data.length >= 5) {
    rowScore = 15
    quality = 'fair'
    suggestions.push('suggestion_few_data')
  } else {
    rowScore = 5
    quality = 'poor'
    suggestions.push('suggestion_very_few_data')
  }

  // 2. 数据维度评分（30分）
  const firstRow = data[0]
  if (!firstRow || typeof firstRow !== 'object') {
    return {
      canAnalyze: false,
      reason: 'data_format_error'
    }
  }

  const columnCount = Object.keys(firstRow).length
  let dimensionScore = 0
  if (columnCount >= 5) {
    dimensionScore = 30
  } else if (columnCount >= 3) {
    dimensionScore = 20
    suggestions.push('suggestion_dimension_ok')
  } else if (columnCount >= 2) {
    dimensionScore = 10
    suggestions.push('suggestion_more_fields')
  } else {
    dimensionScore = 5
    suggestions.push('suggestion_few_fields')
  }

  // 3. 数据类型多样性评分（30分）
  const dataTypes = new Set<string>()
  let hasNumeric = false
  let hasDate = false

  Object.keys(firstRow).forEach(key => {
    const value = firstRow[key]
    const type = typeof value

    if (type === 'number' || (type === 'string' && !isNaN(parseFloat(value)))) {
      dataTypes.add('numeric')
      hasNumeric = true
    } else if (type === 'string') {
      // 检查是否是日期
      if (/^\d{4}[-/]\d{1,2}([-/]\d{1,2})?/.test(value) || 
          /^\d{4}年\d{1,2}月/.test(value)) {
        dataTypes.add('date')
        hasDate = true
      } else {
        dataTypes.add('text')
      }
    }
  })

  let typeScore = 0
  if (dataTypes.size >= 3) {
    typeScore = 30
  } else if (dataTypes.size === 2) {
    typeScore = 20
  } else {
    typeScore = 10
    suggestions.push('suggestion_data_types')
  }

  // 计算总分
  dataQualityScore = rowScore + dimensionScore + typeScore

  // 根据总分调整质量等级
  if (dataQualityScore >= 85) {
    quality = 'excellent'
  } else if (dataQualityScore >= 65) {
    quality = 'good'
  } else if (dataQualityScore >= 40) {
    quality = 'fair'
  } else {
    quality = 'poor'
  }

  // 添加特定建议
  if (!hasNumeric) {
    suggestions.push('suggestion_no_numeric')
  }
  if (!hasDate && data.length > 10) {
    suggestions.push('suggestion_no_date')
  }

  // 检查数据完整性
  let nullCount = 0
  data.forEach(row => {
    Object.values(row).forEach(value => {
      if (value === null || value === undefined || value === '') {
        nullCount++
      }
    })
  })
  const totalCells = data.length * columnCount
  const nullPercentage = (nullCount / totalCells) * 100

  if (nullPercentage > 30) {
    suggestions.push('suggestion_poor_completeness')
  } else if (nullPercentage > 10) {
    suggestions.push('suggestion_some_nulls')
  }

  return {
    canAnalyze: true,
    quality,
    dataQualityScore,
    suggestions: suggestions.length > 0 ? suggestions : undefined,
    hasChart: true,
    hasData: true,
    validFormat: true,
    rowCount: data.length
  }
}

/**
 * 获取分析功能的友好提示信息
 * @param record 聊天记录对象
 * @param t 国际化函数
 * @returns 提示信息
 */
export function getAnalysisTooltip(record: any, t: (key: string) => string): string {
  const validation = validateAnalysisData(record)
  
  if (!validation.canAnalyze) {
    let message = `${t('chat.cannot_analyze')}: ${t('chat.error_' + validation.reason)}`
    if (validation.suggestions && validation.suggestions.length > 0) {
      const translatedSuggestions = validation.suggestions.map(key => t('chat.' + key))
      message += `\n\n${t('chat.suggestions')}: ${translatedSuggestions.join('；')}`
    }
    return message
  }
  
  // 构建质量提示
  let qualityText = ''
  switch (validation.quality) {
    case 'excellent':
      qualityText = t('chat.quality_excellent')
      break
    case 'good':
      qualityText = t('chat.quality_good')
      break
    case 'fair':
      qualityText = t('chat.quality_fair')
      break
    case 'poor':
      qualityText = t('chat.quality_poor')
      break
  }
  
  let message = `${t('chat.data_analysis_tip')}\n\n📊 ${qualityText}`
  if (validation.dataQualityScore) {
    message += ` (${validation.dataQualityScore}${t('chat.score')})`
  }
  
  if (validation.suggestions && validation.suggestions.length > 0) {
    const translatedSuggestions = validation.suggestions.map(key => t('chat.' + key))
    message += `\n\n💡 ${translatedSuggestions.join('；')}`
  }
  
  return message
}

/**
 * 获取数据质量徽章颜色
 * @param quality 质量等级
 * @returns CSS颜色类名
 */
export function getQualityBadgeClass(quality?: string): string {
  switch (quality) {
    case 'excellent':
      return 'quality-excellent'
    case 'good':
      return 'quality-good'
    case 'fair':
      return 'quality-fair'
    case 'poor':
      return 'quality-poor'
    default:
      return ''
  }
}

/**
 * 获取数据质量图标
 * @param quality 质量等级
 * @returns emoji图标
 */
export function getQualityIcon(quality?: string): string {
  switch (quality) {
    case 'excellent':
      return '✅'
    case 'good':
      return '👍'
    case 'fair':
      return '⚠️'
    case 'poor':
      return '❗'
    default:
      return '📊'
  }
}
