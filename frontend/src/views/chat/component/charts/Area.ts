import { BaseG2Chart } from '@/views/chat/component/BaseG2Chart.ts'
import type { ChartAxis, ChartData } from '@/views/chat/component/BaseChart.ts'
import type { G2Spec } from '@antv/g2'
import { checkIsPercent, formatCompactNumber, getAxesWithFilter, processMultiQuotaData } from '@/views/chat/component/charts/utils.ts'

export class Area extends BaseG2Chart {
  constructor(id: string) {
    super(id, 'area')
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
      type: 'view',
      data: _data.data,
      encode: {
        x: x[0].value,
        y: y[0].value,
        color: series.length > 0 ? series[0].value : () => y[0].name,
      },
      legend: series.length > 0 ? {} : { color: false },
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
        y: { nice: true, type: 'linear' },
      },
      children: [
        {
          type: 'area',
          style: { fillOpacity: 0.3 },
          tooltip: (d: any) => ({
            name: series.length > 0 ? d[series[0].value] : y[0].name,
            value: `${d[y[0].value] ?? '-'}${_data.isPercent ? '%' : ''}`,
          }),
        },
        {
          type: 'line',
          encode: { shape: 'smooth' },
          tooltip: false,
        },
      ],
    } as G2Spec

    this.chart.options(options)
  }
}
