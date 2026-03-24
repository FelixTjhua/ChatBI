/**
 * 高级数据预测验证工具
 * 提供智能的数据质量评估和预测准确度预估
 */

export interface CheckResult {
  passed: boolean
  status: 'success' | 'warning' | 'error'
  message: string
  suggestion?: string
  fieldName?: string
  fields?: string[]
}

export interface QueryExample {
  query: string
  description: string
  reason: string
}

export interface AdvancedPredictionValidation {
  // 基础验证
  canPredict: boolean
  quality: 'excellent' | 'good' | 'fair' | 'poor'
  
  // 详细信息
  dataCount: number
  timeFieldName?: string
  numericFields: string[]
  
  // 评估分数
  accuracyScore: number  // 0-100
  dataQualityScore: number  // 0-100
  
  // 状态检查
  checks: {
    dataCount: CheckResult
    timeSeries: CheckResult
    numericFields: CheckResult
  }
  
  // 建议和示例
  suggestions: string[]
  examples: QueryExample[]
  
  // 问题列表
  issues: string[]
}

/**
 * 解析数据
 */
function parseData(data: any): any[] {
  if (!data) return []
  
  try {
    if (typeof data === 'string') {
      const parsed = JSON.parse(data)
      return parseData(parsed)
    } else if (Array.isArray(data)) {
      return data
    } else if (typeof data === 'object' && data !== null) {
      if (Array.isArray(data.data) && Array.isArray(data.fields)) {
        const fields = data.fields
        const rows = data.data
        
        // 检查 data 是否已经是对象数组
        if (rows.length > 0 && typeof rows[0] === 'object' && !Array.isArray(rows[0])) {
          return rows
        }
        
        // 将 fields + data 转换为对象数组（data 是二维数组的情况）
        const result = rows.map((row: any[]) => {
          const obj: any = {}
          fields.forEach((field: string, index: number) => {
            obj[field] = row[index]
          })
          return obj
        })
        return result
      } else if (Array.isArray(data.data)) {
        return data.data
      }
    }
  } catch {
    // 数据解析失败
  }
  
  return []
}

/**
 * 检查数据量
 */
function checkDataCount(count: number): CheckResult {
  if (count >= 50) {
    return {
      passed: true,
      status: 'success',
      message: `数据量充足（${count}行）`,
      suggestion: undefined
    }
  } else if (count >= 10) {
    return {
      passed: true,
      status: 'warning',
      message: `数据量可用（${count}行）`,
      suggestion: '建议增加到50行以上以提高预测准确度'
    }
  } else if (count >= 3) {
    return {
      passed: true,
      status: 'warning',
      message: `数据量较少（${count}行）`,
      suggestion: '强烈建议增加到10行以上以获得可靠的预测结果'
    }
  } else {
    return {
      passed: false,
      status: 'error',
      message: `数据量不足（${count}行，至少需要3行）`,
      suggestion: '请尝试查询更多历史数据，例如："查询最近30天的销售数据"'
    }
  }
}

/**
 * 检查时间序列字段（与后端逻辑完全一致）
 */
function checkTimeSeries(data: any[]): CheckResult {
  if (data.length === 0) {
    return {
      passed: false,
      status: 'error',
      message: '数据为空',
      suggestion: undefined
    }
  }
  
  const firstRow = data[0]
  if (!firstRow || typeof firstRow !== 'object') {
    return {
      passed: false,
      status: 'error',
      message: '数据格式错误',
      suggestion: undefined
    }
  }
  
  // 同时检查字段名和字段值来检测时间列（与后端 extract_data_features 对齐）
  const timeFieldNamePattern = /date|time|日期|时间|年|月|week|quarter|季度/i
  let timeFieldName: string | undefined
  for (const key of Object.keys(firstRow)) {
    // 方式1：字段名匹配时间模式
    if (timeFieldNamePattern.test(key)) {
      timeFieldName = key
      break
    }
    // 方式2：字段值匹配日期格式
    const value = firstRow[key]
    if (typeof value === 'string') {
      const isDate1 = /^\d{4}[-/]\d{1,2}([-/]\d{1,2})?/.test(value)
      const isDate2 = /^\d{4}年\d{1,2}月(\d{1,2}日)?/.test(value)
      const isDate3 = /^\d{1,2}[-/]\d{1,2}[-/]\d{4}/.test(value)
      
      if (isDate1 || isDate2 || isDate3) {
        timeFieldName = key
        break
      }
    }
  }
  
  if (timeFieldName) {
    return {
      passed: true,
      status: 'success',
      message: `已检测到时间字段：${timeFieldName}`,
      fieldName: timeFieldName
    }
  } else {
    return {
      passed: false,
      status: 'error',
      message: '未检测到时间序列字段',
      suggestion: '数据必须包含日期或时间字段（如：2024-01、2024年1月、01-15-2024）。请尝试查询："查询每日销售额" 或 "按月统计订单量"'
    }
  }
}

/**
 * 检查数值字段
 */
function checkNumericFields(data: any[]): CheckResult {
  if (data.length === 0) {
    return {
      passed: false,
      status: 'error',
      message: '数据为空',
      fields: []
    }
  }
  
  const firstRow = data[0]
  if (!firstRow || typeof firstRow !== 'object') {
    return {
      passed: false,
      status: 'error',
      message: '数据格式错误',
      fields: []
    }
  }
  
  // 查找数值字段
  const numericFields: string[] = []
  for (const key of Object.keys(firstRow)) {
    const value = firstRow[key]
    
    if (typeof value === 'number') {
      numericFields.push(key)
    } else if (typeof value === 'string') {
      const num = parseFloat(value)
      if (!isNaN(num) && isFinite(num)) {
        numericFields.push(key)
      }
    }
  }
  
  if (numericFields.length > 0) {
    return {
      passed: true,
      status: 'success',
      message: `检测到${numericFields.length}个可预测字段`,
      fields: numericFields
    }
  } else {
    return {
      passed: false,
      status: 'error',
      message: '未检测到可预测的数值字段',
      suggestion: '在查询中包含数值字段，例如："销售额"、"数量"、"价格" 等',
      fields: []
    }
  }
}

/**
 * 计算预测准确度分数
 */
function calculateAccuracyScore(params: {
  dataCount: number
  hasTimeSeries: boolean
  numericFieldCount: number
}): number {
  let score = 0
  
  // 数据量贡献（最多50分）
  if (params.dataCount >= 100) score += 50
  else if (params.dataCount >= 50) score += 40
  else if (params.dataCount >= 20) score += 30
  else if (params.dataCount >= 10) score += 20
  else if (params.dataCount >= 5) score += 10
  else score += 5
  
  // 时间序列贡献（30分）
  if (params.hasTimeSeries) score += 30
  
  // 数值字段贡献（最多20分）
  score += Math.min(params.numericFieldCount * 5, 20)
  
  return Math.min(score, 100)
}

/**
 * 计算数据质量分数
 */
function calculateDataQuality(data: any[]): number {
  if (data.length === 0) return 0
  
  let score = 0
  
  // 数据量评分（40分）
  if (data.length >= 100) score += 40
  else if (data.length >= 50) score += 30
  else if (data.length >= 20) score += 20
  else if (data.length >= 10) score += 10
  else score += 5
  
  // 数据完整性评分（30分）
  const firstRow = data[0]
  if (firstRow && typeof firstRow === 'object') {
    const keys = Object.keys(firstRow)
    let nullCount = 0
    for (const row of data) {
      for (const key of keys) {
        if (row[key] === null || row[key] === undefined || row[key] === '') {
          nullCount++
        }
      }
    }
    const totalCells = data.length * keys.length
    const completeness = 1 - (nullCount / totalCells)
    score += completeness * 30
  }
  
  // 数据多样性评分（30分）
  if (firstRow && typeof firstRow === 'object') {
    const keys = Object.keys(firstRow)
    score += Math.min(keys.length * 5, 30)
  }
  
  return Math.min(Math.round(score), 100)
}

/**
 * 确定质量等级
 */
function determineQuality(accuracyScore: number): 'excellent' | 'good' | 'fair' | 'poor' {
  if (accuracyScore >= 80) return 'excellent'
  if (accuracyScore >= 60) return 'good'
  if (accuracyScore >= 40) return 'fair'
  return 'poor'
}

/**
 * 生成智能建议
 */
function generateSuggestions(checks: {
  dataCountCheck: CheckResult
  timeSeriesCheck: CheckResult
  numericFieldCheck: CheckResult
}): string[] {
  const suggestions: string[] = []
  
  if (!checks.dataCountCheck.passed && checks.dataCountCheck.suggestion) {
    suggestions.push(checks.dataCountCheck.suggestion)
  } else if (checks.dataCountCheck.status === 'warning' && checks.dataCountCheck.suggestion) {
    suggestions.push(checks.dataCountCheck.suggestion)
  }
  
  if (!checks.timeSeriesCheck.passed && checks.timeSeriesCheck.suggestion) {
    suggestions.push(checks.timeSeriesCheck.suggestion)
  }
  
  if (!checks.numericFieldCheck.passed && checks.numericFieldCheck.suggestion) {
    suggestions.push(checks.numericFieldCheck.suggestion)
  }
  
  return suggestions
}

/**
 * 收集问题列表
 */
function collectIssues(checks: CheckResult[]): string[] {
  return checks
    .filter(check => !check.passed)
    .map(check => check.message)
}

/**
 * 生成示例查询
 */
function generateExamples(params: {
  currentQuery?: string
  issues: CheckResult[]
}): QueryExample[] {
  const examples: QueryExample[] = []
  
  const hasTimeIssue = params.issues.some(issue => !issue.passed && issue.message.includes('时间'))
  const hasDataCountIssue = params.issues.some(issue => !issue.passed && issue.message.includes('数据量'))
  const hasNumericIssue = params.issues.some(issue => !issue.passed && issue.message.includes('数值'))
  
  if (hasTimeIssue && hasNumericIssue) {
    examples.push({
      query: '查询最近30天的每日销售额',
      description: '包含时间序列和数值数据',
      reason: '适合进行趋势预测'
    })
  } else if (hasTimeIssue) {
    examples.push({
      query: '按日期统计订单数量',
      description: '包含日期字段的时间序列数据',
      reason: '时间序列是预测的基础'
    })
  } else if (hasNumericIssue) {
    examples.push({
      query: '查询产品的销售额和数量',
      description: '包含可预测的数值字段',
      reason: '数值数据是预测的目标'
    })
  }
  
  if (hasDataCountIssue) {
    examples.push({
      query: '查询所有产品的月度销售数据',
      description: '获取更多历史数据',
      reason: '数据量充足可提高预测准确度'
    })
  }
  
  // 如果没有问题，提供优化建议
  if (examples.length === 0) {
    examples.push({
      query: '查询最近3个月的每日销售趋势',
      description: '增加数据量以提高准确度',
      reason: '更多的历史数据可以提供更准确的预测'
    })
  }
  
  return examples
}

/**
 * 高级预测验证（主函数）
 */
export function validatePredictionAdvanced(record: any): AdvancedPredictionValidation {
  const data = parseData(record?.data)
  
  // 1. 数据量检查
  const dataCountCheck = checkDataCount(data.length)
  
  // 2. 时间序列检查
  const timeSeriesCheck = checkTimeSeries(data)
  
  // 3. 数值字段检查
  const numericFieldCheck = checkNumericFields(data)
  
  // 4. 计算预测准确度
  const accuracyScore = calculateAccuracyScore({
    dataCount: data.length,
    hasTimeSeries: timeSeriesCheck.passed,
    numericFieldCount: numericFieldCheck.fields?.length || 0
  })
  
  // 5. 计算数据质量
  const dataQualityScore = calculateDataQuality(data)
  
  // 6. 生成建议
  const suggestions = generateSuggestions({
    dataCountCheck,
    timeSeriesCheck,
    numericFieldCheck
  })
  
  // 7. 收集问题
  const issues = collectIssues([dataCountCheck, timeSeriesCheck, numericFieldCheck])
  
  // 8. 生成示例查询
  const examples = generateExamples({
    currentQuery: record?.question,
    issues: [dataCountCheck, timeSeriesCheck, numericFieldCheck].filter(check => !check.passed)
  })
  
  // 9. 确定是否可以预测
  const canPredict = dataCountCheck.passed && timeSeriesCheck.passed && numericFieldCheck.passed
  
  return {
    canPredict,
    quality: determineQuality(accuracyScore),
    dataCount: data.length,
    timeFieldName: timeSeriesCheck.fieldName,
    numericFields: numericFieldCheck.fields || [],
    accuracyScore,
    dataQualityScore,
    checks: {
      dataCount: dataCountCheck,
      timeSeries: timeSeriesCheck,
      numericFields: numericFieldCheck
    },
    suggestions,
    examples,
    issues
  }
}

/**
 * 获取预测按钮的智能提示
 */
export function getAdvancedPredictionTooltip(validation: AdvancedPredictionValidation): string {
  if (validation.canPredict) {
    if (validation.quality === 'excellent') {
      return `✅ 数据质量优秀，预测准确度高

📊 数据量：${validation.dataCount}行（充足）
📅 时间序列：${validation.timeFieldName || '已检测到'}
🔢 可预测字段：${validation.numericFields.length}个
🎯 预测准确度：${validation.accuracyScore}%

点击开始预测`
    } else if (validation.quality === 'good') {
      return `⚠️ 数据可以预测，建议优化以提高准确度

📊 数据量：${validation.dataCount}行
📅 时间序列：${validation.timeFieldName || '已检测到'}
🔢 可预测字段：${validation.numericFields.length}个
🎯 预测准确度：${validation.accuracyScore}%

💡 ${validation.suggestions[0] || '建议增加数据量'}

点击查看详情或开始预测`
    } else {
      return `⚠️ 数据质量一般，预测结果可能不够准确

📊 数据量：${validation.dataCount}行
📅 时间序列：${validation.timeFieldName || '已检测到'}
🔢 可预测字段：${validation.numericFields.length}个
🎯 预测准确度：${validation.accuracyScore}%

💡 ${validation.suggestions.join('；')}

点击查看优化建议`
    }
  } else {
    return `💡 数据暂不支持预测，点击查看如何优化

当前状态：
${validation.issues.map(issue => `❌ ${issue}`).join('\n')}

点击获取优化建议和示例查询`
  }
}
