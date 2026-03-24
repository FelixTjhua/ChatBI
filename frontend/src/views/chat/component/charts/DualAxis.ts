import { BaseG2Chart } from '@/views/chat/component/BaseG2Chart.ts'
import type { ChartAxis, ChartData } from '@/views/chat/component/BaseChart.ts'
import type { G2Spec } from '@antv/g2'
import { formatCompactNumber } from '@/views/chat/component/charts/utils.ts'

export class DualAxis extends BaseG2Chart {
  constructor(id: string) {
    super(id, 'dual_axis')
  }

  init(axis: Array<ChartAxis>, data: Array<ChartData>) {
    super.init(axis, data)

    const x = this.axis.filter((item) => item.type === 'x')
    const y = this.axis.filter((item) => item.type === 'y')

    if (x.length == 0 || y.length < 1) return

    // 双轴图需要至少2个y轴字段，否则两个轴展示同一字段无意义
    // 当只有1个y轴时，退化为单轴柱状图（避免柱状图和折线图重叠展示相同数据）
    if (y.length < 2) {
      // 退化为单轴柱状图
      const options: G2Spec = {
        ...this.chart.options(),
        type: 'interval',
        data: data,
        encode: {
          x: x[0].value,
          y: y[0].value,
          color: x[0].value,
        },
        legend: { color: false },
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
          y: { title: y[0].name, labelFormatter: formatCompactNumber },
        },
        scale: {
          y: { nice: true, type: 'linear' },
        },
        tooltip: (d: any) => ({ name: y[0].name, value: d[y[0].value] }),
      } as G2Spec
      this.chart.options(options)
      return
    }

    // 双轴图：第一个y轴用柱状图，第二个y轴用折线图
    const y1 = y[0]
    const y2 = y[1]

    const options: G2Spec = {
      ...this.chart.options(),
      type: 'view',
      data: data,
      encode: { x: x[0].value },
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
        y: { title: y1.name, labelFormatter: formatCompactNumber },
      },
      children: [
        {
          type: 'interval',
          encode: { y: y1.value, color: '#a78bfa' },
          style: { fillOpacity: 0.6 },
          axis: { y: { position: 'left', title: y1.name, labelFormatter: formatCompactNumber } },
          tooltip: (d: any) => ({ name: y1.name, value: d[y1.value] }),
        },
        {
          type: 'line',
          encode: { y: y2.value, color: '#f472b6' },
          style: { lineWidth: 2 },
          axis: { y: { position: 'right', title: y2.name, labelFormatter: formatCompactNumber } },
          tooltip: (d: any) => ({ name: y2.name, value: d[y2.value] }),
        },
      ],
    } as G2Spec

    this.chart.options(options)
  }
}
