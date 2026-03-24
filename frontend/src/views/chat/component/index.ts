import { BaseChart } from '@/views/chat/component/BaseChart.ts'
import { Bar } from '@/views/chat/component/charts/Bar.ts'
import { Column } from '@/views/chat/component/charts/Column.ts'
import { Line } from '@/views/chat/component/charts/Line.ts'
import { Table } from '@/views/chat/component/charts/Table.ts'
import { Pie } from '@/views/chat/component/charts/Pie.ts'
import { Kpi } from '@/views/chat/component/charts/Kpi.ts'
import { Area } from '@/views/chat/component/charts/Area.ts'
import { Box } from '@/views/chat/component/charts/Box.ts'
import { Heatmap } from '@/views/chat/component/charts/Heatmap.ts'
import { DualAxis } from '@/views/chat/component/charts/DualAxis.ts'

const CHART_TYPE_MAP: { [key: string]: any } = {
  table: Table,
  column: Column,
  bar: Bar,
  line: Line,
  pie: Pie,
  kpi: Kpi,
  area: Area,
  box: Box,
  heatmap: Heatmap,
  dual_axis: DualAxis,
  // sankey/funnel 降级为柱状图（AntV G2需要额外插件支持）
  sankey: Column,
  funnel: Bar,
}

const isParent = (type: any, parentType: any) => {
  let _type = type
  while (_type) {
    if (_type === parentType) {
      return true
    }
    _type = _type.__proto__
  }
  return false
}

export function getChartInstance(type: string, id: string): BaseChart | undefined {
  if (isParent(CHART_TYPE_MAP[type], BaseChart)) {
    return new CHART_TYPE_MAP[type](id) as BaseChart
  }
  return undefined
}
