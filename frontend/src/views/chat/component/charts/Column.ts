import { BaseG2Chart } from '@/views/chat/component/BaseG2Chart.ts'
import type { ChartAxis, ChartData } from '@/views/chat/component/BaseChart.ts'
import type { G2Spec } from '@antv/g2'
import { checkIsPercent, formatCompactNumber, getAxesWithFilter, processMultiQuotaData } from '@/views/chat/component/charts/utils.ts'

export class Column extends BaseG2Chart {
  constructor(id: string) {
    super(id, 'column')
  }

  init(axis: Array<ChartAxis>, data: Array<ChartData>) {
    super.init(axis, data)

    const axes = getAxesWithFilter(this.axis)
    if (axes.x.length == 0 || axes.y.length == 0) return

    let config = { data, y: axes.y, series: axes.series }
    if (axes.multiQuota.length > 0) {
      config = processMultiQuotaData(axes.x, config.y, axes.multiQuota, axes.multiQuotaName, config.data)
    }

    const x = axes.x
    const y = config.y
    const series = config.series
    const _data = checkIsPercent(y, config.data)

    const options: G2Spec = {
      ...this.chart.options(),
      type: 'interval',
      data: _data.data,
      encode: {
        x: x[0].value,
        y: y[0].value,
        color: series.length > 0 ? series[0].value : x[0].value,
      },
      legend: series.length > 0 ? {} : { color: false },
      style: {
        radiusTopLeft: (d: ChartData) => (d[y[0].value] > 0 ? 4 : 0),
        radiusTopRight: (d: ChartData) => (d[y[0].value] > 0 ? 4 : 0),
        radiusBottomLeft: (d: ChartData) => (d[y[0].value] < 0 ? 4 : 0),
        radiusBottomRight: (d: ChartData) => (d[y[0].value] < 0 ? 4 : 0),
      },
      axis: {
        x: {
          title: false,
          labelFontSize: 12,
          labelAutoHide: { type: 'hide', keepHeader: true, keepTail: true },
          labelAutoRotate: false,
          labelAutoWrap: true,
          labelAutoEllipsis: true,
        },
        y: {
          title: false,
          labelFormatter: (v: number | string) => _data.isPercent ? `${v}%` : formatCompactNumber(v),
        },
      },
      scale: {
        x: { nice: true },
        y: { nice: true, type: 'linear' },
      },
      interaction: {
        elementHighlight: { background: true, region: true },
        tooltip: { series: series.length > 0, shared: true },
      },
      tooltip: (data: any) => {
        if (series.length > 0) {
          return { name: data[series[0].value], value: `${data[y[0].value]}${_data.isPercent ? '%' : ''}` }
        }
        return { name: y[0].name, value: `${data[y[0].value]}${_data.isPercent ? '%' : ''}` }
      },
      labels: this.showLabel ? [{
        text: (data: any) => {
          const value = data[y[0].value]
          return value !== undefined && value !== null ? `${value}${_data.isPercent ? '%' : ''}` : ''
        },
        position: (data: any) => (data[y[0].value] < 0 ? 'bottom' : 'top'),
        transform: [{ type: 'contrastReverse' }, { type: 'exceedAdjust' }, { type: 'overlapHide' }],
      }] : [],
    } as G2Spec

    if (series.length > 0) {
      options.transform = [{ type: 'stackY' }]
    }

    this.chart.options(options)
  }
}
