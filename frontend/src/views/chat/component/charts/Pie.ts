import { BaseG2Chart } from '@/views/chat/component/BaseG2Chart.ts'
import type { ChartAxis, ChartData } from '@/views/chat/component/BaseChart.ts'
import type { G2Spec } from '@antv/g2'
import { checkIsPercent, getAxesWithFilter } from '@/views/chat/component/charts/utils.ts'

export class Pie extends BaseG2Chart {
  constructor(id: string) {
    super(id, 'pie')
  }

  init(axis: Array<ChartAxis>, data: Array<ChartData>) {
    super.init(axis, data)
    const { y, series } = getAxesWithFilter(this.axis)

    if (series.length == 0 || y.length == 0) return

    const _data = checkIsPercent(y, data)

    const options: G2Spec = {
      ...this.chart.options(),
      type: 'interval',
      coordinate: { type: 'theta', outerRadius: 0.8 },
      transform: [{ type: 'stackY' }],
      data: _data.data,
      encode: {
        y: y[0].value,
        color: series[0].value,
      },
      scale: {
        x: { nice: true },
        y: { type: 'linear' },
      },
      legend: {
        color: { position: 'bottom', layout: { justifyContent: 'center' } },
      },
      animate: { enter: { type: 'waveIn' } },
      labels: this.showLabel ? [{
        position: 'spider',
        text: (data: any) => `${data[series[0].value]}: ${data[y[0].value]}${_data.isPercent ? '%' : ''}`,
        style: {
          fill: 'rgba(255, 255, 255, 0.85)',
          fontSize: 12,
          fontWeight: 500,
        },
        connectorStroke: 'rgba(255, 255, 255, 0.3)',
      }] : [],
      tooltip: {
        title: (data: any) => data[series[0].value],
        items: [
          (data: any) => ({
            name: y[0].name,
            value: `${data[y[0].value]}${_data.isPercent ? '%' : ''}`,
          }),
        ],
      },
    }

    this.chart.options(options)
  }
}
