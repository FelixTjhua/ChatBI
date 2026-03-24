import { BaseG2Chart } from '@/views/chat/component/BaseG2Chart.ts'
import type { ChartAxis, ChartData } from '@/views/chat/component/BaseChart.ts'
import type { G2Spec } from '@antv/g2'

export class Heatmap extends BaseG2Chart {
  constructor(id: string) {
    super(id, 'heatmap')
  }

  init(axis: Array<ChartAxis>, data: Array<ChartData>) {
    super.init(axis, data)

    const x = this.axis.filter((item) => item.type === 'x')
    const y = this.axis.filter((item) => item.type === 'y')
    const series = this.axis.filter((item) => item.type === 'series')

    if (x.length == 0 || y.length == 0) return
    if (!data || data.length === 0) return

    // 热力图：x=维度1, y=维度2, color=数值
    // 当有series时：x=维度1, y=series(维度2), color=y(数值)
    // 当无series时：x=维度1, y需要第二个维度（退化为单维度色块）
    const yField = series.length > 0 ? series[0].value : (y.length > 1 ? y[1].value : y[0].value)
    const yTitle = series.length > 0 ? series[0].name : (y.length > 1 ? y[1].name : y[0].name)
    const colorField = y[0].value

    const options: G2Spec = {
      ...this.chart.options(),
      type: 'cell',
      data: data,
      encode: {
        x: x[0].value,
        y: yField,
        color: colorField,
      },
      axis: {
        x: {
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
        },
        y: { title: yTitle },
      },
      style: {
        inset: 1,
      },
      scale: {
        color: { palette: 'ylGnBu' },
      },
      legend: {
        color: {
          position: 'bottom',
          layout: { justifyContent: 'center' },
        },
      },
      tooltip: (d: any) => ({
        name: `${d[x[0].value]} × ${d[yField]}`,
        value: d[colorField] ?? '-',
      }),
    } as G2Spec

    this.chart.options(options)
  }
}
