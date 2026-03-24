import { BaseG2Chart } from '@/views/chat/component/BaseG2Chart.ts'
import type { ChartAxis, ChartData } from '@/views/chat/component/BaseChart.ts'
import type { G2Spec } from '@antv/g2'

export class Box extends BaseG2Chart {
  constructor(id: string) {
    super(id, 'box')
  }

  init(axis: Array<ChartAxis>, data: Array<ChartData>) {
    super.init(axis, data)

    const x = this.axis.filter((item) => item.type === 'x')
    const y = this.axis.filter((item) => item.type === 'y')

    if (y.length == 0) return
    if (!data || data.length === 0) return

    const options: G2Spec = {
      ...this.chart.options(),
      type: 'boxplot',
      data: data,
      encode: {
        x: x.length > 0 ? x[0].value : undefined,
        y: y[0].value,
        color: x.length > 0 ? x[0].value : undefined,
      },
      legend: { color: false },
      axis: {
        x: x.length > 0 ? {
          title: x[0].name,
          labelFontSize: 12,
          labelAutoHide: {
            type: 'hide',
            keepHeader: true,
            keepTail: true,
          },
          labelAutoRotate: false,
          labelAutoWrap: true,
          labelAutoEllipsis: true,
        } : undefined,
        y: { title: y[0].name },
      },
      style: {
        boxFillOpacity: 0.6,
      },
    } as G2Spec

    this.chart.options(options)
  }
}
