import type { ChartAxis, ChartData } from '@/views/chat/component/BaseChart.ts'
import { endsWith, filter, replace } from 'lodash-es'

/**
 * 格式化大数值为紧凑形式，防止坐标轴标签溢出
 * 例: 20000000 → "2000万", 150000 → "15万", 1200 → "1200"
 */
export function formatCompactNumber(value: number | string): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (!isFinite(num)) return String(value)
  const abs = Math.abs(num)
  if (abs >= 1_0000_0000) {
    const v = num / 1_0000_0000
    return `${parseFloat(v.toPrecision(4))}亿`
  }
  if (abs >= 1_0000) {
    const v = num / 1_0000
    return `${parseFloat(v.toPrecision(4))}万`
  }
  return String(num)
}

/**
 * 修正浮点精度问题（如 86.91000000000001 → 86.91）
 * 对数据中所有数值字段做 toPrecision 修正，消除 IEEE 754 浮点误差。
 */
export function fixFloatPrecision(data: Array<ChartData>): Array<ChartData> {
  return data.map((row) => {
    const fixed: ChartData = {}
    for (const [k, v] of Object.entries(row)) {
      if (typeof v === 'number' && isFinite(v)) {
        // parseFloat(v.toPrecision(12)) 可消除尾部噪声位
        fixed[k] = parseFloat(v.toPrecision(12))
      } else {
        fixed[k] = v
      }
    }
    return fixed
  })
}

interface CheckedData {
  isPercent: boolean
  data: Array<ChartData>
}

export function getAxesWithFilter(axes: ChartAxis[]): {
  x: ChartAxis[]
  y: ChartAxis[]
  series: ChartAxis[]
  multiQuota: string[]
  multiQuotaName?: string
} {
  const groups = {
    x: [] as ChartAxis[],
    y: [] as ChartAxis[],
    series: [] as ChartAxis[],
    multiQuota: [] as string[],
    multiQuotaName: undefined as string | undefined,
  }

  axes.forEach((axis) => {
    if (axis.type === 'x') groups.x.push(axis)
    else if (axis.type === 'y') groups.y.push(axis)
    else if (axis.type === 'series') groups.series.push(axis)
    else if (axis.type === 'other-info') groups.multiQuotaName = axis.value
  })

  if (groups.series.length > 0) {
    groups.y = groups.y.slice(0, 1)
  } else {
    const multiQuotaY = groups.y.filter((item) => item['multi-quota'] === true)
    groups.multiQuota = multiQuotaY.map((item) => item.value)
    if (multiQuotaY.length > 0) {
      groups.y = multiQuotaY
    }
  }

  return groups
}

export function processMultiQuotaData(
  x: Array<ChartAxis>,
  y: Array<ChartAxis>,
  multiQuota: Array<string>,
  multiQuotaName: string = 'sqlbot_auto_series',
  data: Array<ChartData>
) {
  const _list: Array<ChartData> = []
  const _map: { [propName: string]: string } = {}
  y.forEach((axis) => {
    _map[axis.value] = axis.name
  })
  for (const datum of data) {
    multiQuota.forEach((quota) => {
      const _data: { [propName: string]: any } = {}
      for (const xAxis of x) {
        _data[xAxis.value] = datum[xAxis.value]
      }
      _data['sqlbot_auto_quota'] = datum[quota]
      _data['sqlbot_auto_series'] = _map[quota]
      _list.push(_data)
    })
  }

  return {
    data: _list,
    y: [{ name: 'sqlbot_auto_quota', value: 'sqlbot_auto_quota', type: 'y' } as ChartAxis],
    series: [{ name: multiQuotaName, value: 'sqlbot_auto_series', type: 'series' } as ChartAxis],
  }
}

export function checkIsPercent(valueAxes: Array<ChartAxis>, data: Array<ChartData>): CheckedData {
  const result: CheckedData = {
    isPercent: false,
    data: [],
  }

  for (let i = 0; i < data.length; i++) {
    result.data.push({ ...data[i] })
  }

  for (const valueAxis of valueAxes) {
    const notEmptyData = filter(
      data,
      (d) =>
        d &&
        d[valueAxis.value] !== null &&
        d[valueAxis.value] !== undefined &&
        d[valueAxis.value] !== '' &&
        d[valueAxis.value] !== 0 &&
        d[valueAxis.value] !== '0'
    )

    if (notEmptyData.length > 0) {
      const v = notEmptyData[0][valueAxis.value] + ''
      if (endsWith(v.trim(), '%')) {
        result.isPercent = true
        break
      }
    }
  }

  if (result.isPercent) {
    for (let i = 0; i < data.length; i++) {
      for (const valueAxis of valueAxes) {
        const value = data[i][valueAxis.value]
        if (value !== null && value !== undefined && value !== '') {
          const strValue = String(value).trim()
          if (endsWith(strValue, '%')) {
            const formatValue = replace(strValue, '%', '')
            const numValue = Number(formatValue)
            result.data[i][valueAxis.value] = isNaN(numValue) ? 0 : numValue
          }
        }
      }
    }
  }

  return result
}
